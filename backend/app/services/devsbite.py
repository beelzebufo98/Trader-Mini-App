from typing import Any

import httpx

from app.config import settings


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


def _headers() -> dict[str, str]:
    return {"X-Client-Token": _client_token()}


def _request_json(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=20) as client:
            response = client.request(method, f"{_base_url()}{path}", headers=_headers(), **kwargs)
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


def get_pairs(market: str, min_payout: int = 80, category: str | None = None) -> dict[str, Any]:
    market_key = market.strip().lower()
    if market_key not in {"forex", "otc"}:
        raise DevsbiteApiError("Unsupported market")

    path = f"/pairs/{market_key}"
    if category is not None:
        category_key = category.strip().lower()
        if market_key != "otc" or category_key not in {"commodities", "stocks", "crypto"}:
            raise DevsbiteApiError("Unsupported pairs category")
        path = f"{path}/{category_key}"

    return _request_json(
        "GET",
        path,
        params={"min_payout": min_payout},
    )


def get_quote(category: str, symbol: str, history_seconds: int | None = None) -> dict[str, Any]:
    category_key = category.strip().lower()
    if category_key not in {"forex", "otc", "commodities", "stocks", "crypto"}:
        raise DevsbiteApiError("Unsupported quote category")

    params: dict[str, Any] = {
        "category": category_key,
        "symbol": symbol,
    }
    path = "/quotes/price"
    if history_seconds is not None:
        params["history_seconds"] = history_seconds
        path = "/quotes/quote"

    return _request_json("GET", path, params=params)


def get_combined_analysis(symbol: str, expiry_min: int) -> dict[str, Any]:
    if expiry_min < 1:
        raise DevsbiteApiError("Expiration must be at least 1 minute")

    request_payload = {
        "symbol": symbol,
        "expiry_min": expiry_min,
    }

    return _request_json("POST", "/analysis/combined", json=request_payload)
