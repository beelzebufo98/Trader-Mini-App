from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from app.config import settings

QUOTE_CATEGORIES = {"forex", "otc", "commodities", "stocks", "crypto"}
OTC_ASSET_CATEGORIES = {"commodities", "stocks", "crypto"}
MARKETS = {"forex", "otc"}


class DevsbiteConfigError(RuntimeError):
    pass


class DevsbiteRequestError(RuntimeError):
    pass


class DevsbiteApiError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _client_token() -> str:
    token = settings.devsbite_client_token.strip()
    if not token:
        raise DevsbiteConfigError("Devsbite client token is not configured")
    return token


def _base_url() -> str:
    return settings.devsbite_api_base_url.rstrip("/")


def _websocket_base_url() -> str:
    parsed = urlparse(_base_url())
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "", "", "", ""))


def _headers() -> dict[str, str]:
    return {"X-Client-Token": _client_token()}


def _json_headers() -> dict[str, str]:
    return {**_headers(), "Content-Type": "application/json"}


def _request_json(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    headers = kwargs.pop("headers", _headers())
    try:
        with httpx.Client(timeout=20) as client:
            response = client.request(method, f"{_base_url()}{path}", headers=headers, **kwargs)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as error:
        raise DevsbiteApiError(
            message=f"Devsbite API returned {error.response.status_code}",
            status_code=error.response.status_code,
        ) from error
    except (httpx.RequestError, ValueError) as error:
        raise DevsbiteRequestError("Devsbite API request failed") from error

    if not isinstance(payload, dict):
        raise DevsbiteRequestError("Devsbite API returned an unexpected payload")

    if payload.get("ok") is False:
        message = payload.get("message") or payload.get("detail") or "Devsbite API returned an error"
        if not isinstance(message, str):
            message = "Devsbite API returned an error"
        raise DevsbiteApiError(message=message)

    return payload


def normalize_category(category: str) -> str:
    category_key = category.strip().lower()
    if category_key not in QUOTE_CATEGORIES:
        raise DevsbiteApiError("Unsupported quote category")
    return category_key


def normalize_market(market: str) -> str:
    market_key = market.strip().lower()
    if market_key not in MARKETS:
        raise DevsbiteApiError("Unsupported market")
    return market_key


def normalize_forex_symbol(symbol: str) -> str:
    value = symbol.strip().upper().replace(" ", "")
    if "/" in value:
        return value
    if len(value) == 6 and value.isalpha():
        return f"{value[:3]}/{value[3:]}"
    return symbol.strip()


def normalize_symbol_for_category(category: str, symbol: str) -> str:
    category_key = normalize_category(category)
    if category_key == "forex":
        return normalize_forex_symbol(symbol)
    return " ".join(symbol.strip().split())


def extract_instruments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    instruments = payload.get("pairs")
    if instruments is None:
        instruments = payload.get("assets")
    if not isinstance(instruments, list):
        return []
    return [item for item in instruments if isinstance(item, dict)]


def extract_latest_price(payload: dict[str, Any]) -> float | None:
    price = payload.get("price")
    if isinstance(price, (int, float)):
        return float(price)
    return None


def has_fresh_price(payload: dict[str, Any]) -> bool:
    return bool(payload.get("ok")) and extract_latest_price(payload) is not None


def get_pairs(market: str, min_payout: int = 80, category: str | None = None) -> dict[str, Any]:
    market_key = normalize_market(market)

    path = f"/pairs/{market_key}"
    if category is not None:
        category_key = category.strip().lower()
        if market_key != "otc" or category_key not in OTC_ASSET_CATEGORIES:
            raise DevsbiteApiError("Unsupported pairs category")
        path = f"{path}/{category_key}"

    return _request_json(
        "GET",
        path,
        params={"min_payout": min_payout},
    )


def get_quote(category: str, symbol: str, history_seconds: int | None = None) -> dict[str, Any]:
    category_key = normalize_category(category)

    params: dict[str, Any] = {
        "category": category_key,
        "symbol": normalize_symbol_for_category(category_key, symbol),
    }
    path = "/quotes/price"
    if history_seconds is not None:
        if history_seconds < 1:
            raise DevsbiteApiError("History window must be at least 1 second")
        params["history_seconds"] = history_seconds
        path = "/quotes/quote"

    return _request_json("GET", path, params=params)


def get_combined_analysis(symbol: str, expiry_min: int) -> dict[str, Any]:
    if expiry_min < 1 or expiry_min > 60:
        raise DevsbiteApiError("Expiration must be between 1 and 60 minutes")

    request_payload = {
        "symbol": symbol,
        "expiry_min": expiry_min,
    }

    return _request_json("POST", "/analysis/combined", headers=_json_headers(), json=request_payload)


def get_tv_analysis(
    symbol: str,
    exchange: str = "FX_IDC",
    screener: str = "forex",
    interval: str = "1m",
) -> dict[str, Any]:
    request_payload = {
        "symbol": symbol.strip(),
        "exchange": exchange.strip(),
        "screener": screener.strip(),
        "interval": interval.strip(),
    }
    return _request_json("POST", "/analysis/tv", headers=_json_headers(), json=request_payload)


def get_advanced_analysis(
    symbol: str,
    interval: str = "5min",
    category: str = "forex",
) -> dict[str, Any]:
    category_key = normalize_category(category)
    request_payload = {
        "symbol": normalize_symbol_for_category(category_key, symbol),
        "interval": interval.strip(),
        "category": category_key,
    }
    return _request_json("POST", "/analysis/advanced", headers=_json_headers(), json=request_payload)


def build_live_quote_ws_url(
    category: str,
    symbol: str,
    history_seconds: int = 60,
    interval_ms: int = 1000,
) -> str:
    category_key = normalize_category(category)
    if history_seconds < 1:
        raise DevsbiteApiError("History window must be at least 1 second")
    if interval_ms < 250:
        raise DevsbiteApiError("WebSocket interval is too small")

    params = urlencode(
        {
            "client_token": _client_token(),
            "category": category_key,
            "symbol": normalize_symbol_for_category(category_key, symbol),
            "history_seconds": history_seconds,
            "interval_ms": interval_ms,
        }
    )
    return f"{_websocket_base_url()}/ws/quotes/live?{params}"


def build_multi_quote_ws_url() -> str:
    return f"{_websocket_base_url()}/ws/quotes/live/multi?{urlencode({'client_token': _client_token()})}"


def build_subscribe_payload(category: str, symbol: str, history_seconds: int = 60) -> dict[str, Any]:
    category_key = normalize_category(category)
    if history_seconds < 1:
        raise DevsbiteApiError("History window must be at least 1 second")

    return {
        "action": "subscribe",
        "category": category_key,
        "symbol": normalize_symbol_for_category(category_key, symbol),
        "history_seconds": history_seconds,
    }


def build_subscribe_many_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        category = normalize_category(str(item.get("category", "")))
        symbol = normalize_symbol_for_category(category, str(item.get("symbol", "")))
        history_seconds = int(item.get("history_seconds", 60))
        if history_seconds < 1:
            raise DevsbiteApiError("History window must be at least 1 second")
        normalized_items.append(
            {
                "category": category,
                "symbol": symbol,
                "history_seconds": history_seconds,
            }
        )

    return {
        "action": "subscribe_many",
        "items": normalized_items,
    }
