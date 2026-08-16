from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Literal

import httpx

from app.services.signal_time import format_signal_time
from app.telegram.client import send_message, send_photo

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMAGES_DIR = PROJECT_ROOT / "images"

SignalDirection = Literal["BUY", "SELL"]
SignalResult = Literal["WIN", "LOSS"]


@dataclass(frozen=True)
class SignalAsset:
    symbol: str
    market_type: str
    flag_1: str = ""
    flag_2: str = ""


@dataclass(frozen=True)
class SignalEntry:
    asset: SignalAsset
    direction: SignalDirection
    entry_time: datetime
    expiry_seconds: int
    entry_price: float | None = None


@dataclass(frozen=True)
class SignalOutcome:
    asset: SignalAsset
    direction: SignalDirection
    result: SignalResult
    entry_time: datetime
    expiry_seconds: int
    entry_price: float | None = None
    close_price: float | None = None
    chart_image_path: Path | None = None


def format_time(value: datetime) -> str:
    return format_signal_time(value)


def format_session_time(value: datetime) -> str:
    return format_signal_time(value, seconds=False)


def format_expiry(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} секунд"
    minutes = seconds // 60
    if minutes == 1:
        return "1 минута"
    if minutes in {2, 3, 4}:
        return f"{minutes} минуты"
    return f"{minutes} минут"


def format_price(price: float | None) -> str:
    if price is None:
        return "—"
    return f"{price:.6f}".rstrip("0").rstrip(".")


def market_label(asset_or_market: SignalAsset | str) -> str:
    value = asset_or_market.market_type if isinstance(asset_or_market, SignalAsset) else asset_or_market
    return (value or "FOREX").strip().upper()


def display_symbol(asset: SignalAsset) -> str:
    symbol = asset.symbol.strip()
    market = market_label(asset)
    if market == "OTC" and symbol.upper().endswith(" OTC"):
        return symbol[:-4].strip()
    if market != "OTC" and symbol.upper().endswith(f" {market}"):
        return symbol[: -len(market)].strip()
    return symbol


def market_symbol(asset: SignalAsset) -> str:
    return f"{display_symbol(asset)} {market_label(asset)}".strip()


def asset_line(asset: SignalAsset) -> str:
    return " ".join(part for part in [asset.flag_1, display_symbol(asset), asset.flag_2] if part)


def asset_market_line(asset: SignalAsset) -> str:
    return f"{asset_line(asset)} · {market_label(asset)}"


def direction_label(direction: SignalDirection) -> str:
    return "Купить (BUY)" if direction == "BUY" else "Продать (SELL)"


def direction_emoji(direction: SignalDirection) -> str:
    return "🟢" if direction == "BUY" else "🔴"


def image_path(name: str) -> Path | None:
    path = IMAGES_DIR / name
    return path if path.exists() else None


def send_channel_html(
    client: httpx.Client,
    chat_id: int,
    text: str,
    *,
    photo_path: Path | None = None,
) -> int | None:
    if photo_path is not None and photo_path.exists():
        try:
            response = send_photo(client, chat_id, photo_path, caption=text, parse_mode="HTML")
        finally:
            if photo_path.parent.name.startswith("tmp") and photo_path.name.startswith("paradox_trade_result_"):
                photo_path.unlink(missing_ok=True)
    else:
        response = send_message(client, chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, dict) and isinstance(result.get("message_id"), int):
        return result["message_id"]
    return None


def send_session_soon(
    client: httpx.Client,
    *,
    chat_id: int,
    market_type: str,
    session_start_time: datetime,
    minutes_before: int = 60,
) -> int | None:
    market = escape(market_label(market_type))
    text = (
        f"🚨 <b>ТОРГОВАЯ СЕССИЯ ЧЕРЕЗ {minutes_before} МИНУТ</b> 🚨\n\n"
        f"{market} · старт в <b>{format_session_time(session_start_time)}</b>\n\n"
        "🎯 Проверьте заранее:\n"
        "— баланс для торговли 💵\n"
        "— стабильное соединение 📶\n\n"
        "Готовьтесь — скоро начинаем! 🔥"
    )
    return send_channel_html(client, chat_id, text, photo_path=image_path("1-HOUR-SESSION.png"))


def send_signal_countdown(
    client: httpx.Client,
    *,
    chat_id: int,
    asset: SignalAsset,
    entry_time: datetime,
    expiry_seconds: int,
    seconds_before: int = 60,
) -> int | None:
    text = (
        f"⏳ До нового сигнала осталось <b>{seconds_before} секунд</b>\n\n"
        f"💱 Актив: {escape(asset_market_line(asset))}\n"
        f"🕘 Время входа: <b>{format_time(entry_time)}</b>\n"
        f"⏱ Экспирация: <b>{format_expiry(expiry_seconds)}</b>\n\n"
        "⚠️ Подготовьте терминал. Направление сделки будет опубликовано через 60 секунд."
    )
    return send_channel_html(client, chat_id, text)


def send_signal_entry(client: httpx.Client, chat_id: int, signal: SignalEntry) -> int | None:
    text = (
        f"⚡ <b>СИГНАЛ ПО {escape(market_symbol(signal.asset))}</b>\n\n"
        f"{escape(asset_market_line(signal.asset))}\n"
        f"🕘 Время входа: <b>{format_time(signal.entry_time)}</b>\n"
        f"⏱ Экспирация: <b>{format_expiry(signal.expiry_seconds)}</b>\n"
        f"{direction_emoji(signal.direction)} <b>{direction_label(signal.direction)}</b>\n"
        f"💲 Цена входа: <b>{format_price(signal.entry_price)}</b>"
    )
    photo_name = "SESSION-BUY.png" if signal.direction == "BUY" else "SESSION-SELL.jpg"
    return send_channel_html(client, chat_id, text, photo_path=image_path(photo_name))


def send_overlap(
    client: httpx.Client,
    chat_id: int,
    signal: SignalEntry,
    *,
    attempt_no: int,
) -> int | None:
    if attempt_no == 1:
        title = "Первый вход закрылся в минус."
        overlap = "ПЕРВОЕ ПЕРЕКРЫТИЕ"
    elif attempt_no == 2:
        title = "Второе перекрытие закрылось в минус."
        overlap = "ВТОРОЕ ПЕРЕКРЫТИЕ"
    else:
        title = "Третье перекрытие закрылось в минус."
        overlap = "ТРЕТЬЕ ПЕРЕКРЫТИЕ"

    text = (
        f"❌ {title}\n"
        f"🔄 <b>{overlap}</b>\n\n"
        f"{escape(asset_market_line(signal.asset))}\n"
        f"🕘 Новый вход: <b>{format_time(signal.entry_time)}</b>\n"
        f"⏱ Экспирация: <b>{format_expiry(signal.expiry_seconds)}</b>\n"
        f"💲 Цена входа: <b>{format_price(signal.entry_price)}</b>\n"
        f"{direction_emoji(signal.direction)} <b>{direction_label(signal.direction)}</b>"
    )
    return send_channel_html(client, chat_id, text)


def send_refund(client: httpx.Client, chat_id: int, signal: SignalEntry) -> int | None:
    text = (
        "🔄 <b>Возврат средств</b>\n\n"
        f"{escape(asset_market_line(signal.asset))}\n\n"
        "Фиксируем возврат и повторяем вход без повышения уровня."
    )
    return send_channel_html(client, chat_id, text)


def send_signal_result(client: httpx.Client, chat_id: int, outcome: SignalOutcome) -> int | None:
    if outcome.result == "WIN":
        text = (
            "✅ <b>СИГНАЛ ОТРАБОТАН В ПЛЮС</b>\n\n"
            f"{escape(asset_market_line(outcome.asset))}\n"
            f"{direction_emoji(outcome.direction)} <b>{outcome.direction}</b>\n"
            "💸 Сделка успешно закрылась в прибыль."
        )
    else:
        text = (
            "❌ <b>Серия закрыта в минус</b>\n\n"
            f"{escape(asset_market_line(outcome.asset))} — все уровни отработаны.\n"
            "Фиксируем результат, идём дальше."
        )

    return send_channel_html(client, chat_id, text, photo_path=outcome.chart_image_path)


def send_session_finished(
    client: httpx.Client,
    *,
    chat_id: int,
    market_type: str,
    session_start_time: datetime,
    session_end_time: datetime,
    total_series: int,
    wins: int,
    losses: int,
) -> int | None:
    market = escape(market_label(market_type))
    text = (
        "🌙 <b>ТОРГОВАЯ СЕССИЯ ЗАВЕРШЕНА</b>\n\n"
        f"{format_session_time(session_start_time)}–{format_session_time(session_end_time)} · {market}\n\n"
        f"📊 Отработано сигналов: <b>{total_series}</b>\n"
        f"✅ Плюсы: <b>{wins}</b>\n"
        f"❌ Минусы: <b>{losses}</b>"
    )
    return send_channel_html(client, chat_id, text, photo_path=image_path("SESSION-FINISH.png"))
