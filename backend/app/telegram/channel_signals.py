from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx

from app.config import settings
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


def signals_channel_id() -> int:
    value = settings.telegram_signals_channel_id.strip()
    if not value:
        raise RuntimeError("TELEGRAM_SIGNALS_CHANNEL_ID is not configured")
    return int(value)


def format_time(value: datetime) -> str:
    return value.strftime("%H:%M:%S")


def format_session_time(value: datetime) -> str:
    return value.strftime("%H:%M")


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


def asset_line(asset: SignalAsset) -> str:
    flags = " ".join(part for part in [asset.flag_1, asset.symbol, asset.flag_2] if part)
    return flags or asset.symbol


def image_path(name: str) -> Path | None:
    path = IMAGES_DIR / name
    return path if path.exists() else None


def send_channel_html(
    client: httpx.Client,
    text: str,
    *,
    photo_path: Path | None = None,
) -> int | None:
    chat_id = signals_channel_id()
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
    market_type: str,
    session_start_time: datetime,
    minutes_before: int = 60,
) -> int | None:
    text = (
        f"🚨 <b>ТОРГОВАЯ СЕССИЯ ЧЕРЕЗ {minutes_before} МИНУТ</b> 🚨\n"
        f"{market_type.upper()} · старт в <b>{format_session_time(session_start_time)}</b>\n"
        "🎯 Проверьте заранее:\n"
        "— баланс для торговли 💵\n"
        "— стабильное соединение 📶\n"
        "Готовьтесь — скоро начинаем! 🔥"
    )
    return send_channel_html(client, text, photo_path=image_path("1-HOUR-SESSION.png"))


def send_signal_countdown(
    client: httpx.Client,
    *,
    asset: SignalAsset,
    entry_time: datetime,
    expiry_seconds: int,
    seconds_before: int = 60,
) -> int | None:
    text = (
        f"⌛ До нового сигнала осталось <b>{seconds_before} секунд</b>\n"
        f"💱 Актив: {asset_line(asset)} {asset.market_type.upper()}\n"
        f"🕘 Время входа: <b>{format_time(entry_time)}</b>\n"
        f"⏱ Экспирация: <b>{format_expiry(expiry_seconds)}</b>\n"
        "⚠️ Подготовьте терминал. Направление сделки будет опубликовано через 60 секунд."
    )
    return send_channel_html(client, text)


def send_signal_entry(client: httpx.Client, signal: SignalEntry) -> int | None:
    is_buy = signal.direction == "BUY"
    action_ru = "Купить"
    if not is_buy:
        action_ru = "Продать"
    direction_emoji = "🟢" if is_buy else "🔴"
    text = (
        f"⚡ <b>СИГНАЛ ПО {signal.asset.symbol} {signal.asset.market_type.upper()}</b>\n"
        f"{asset_line(signal.asset)}\n"
        f"🕘 Время входа: <b>{format_time(signal.entry_time)}</b>\n"
        f"⏱ Экспирация: <b>{format_expiry(signal.expiry_seconds)}</b>\n"
        f"{direction_emoji} <b>{action_ru} ({signal.direction})</b>\n"
        f"💲 Цена входа: <b>{format_price(signal.entry_price)}</b>"
    )
    photo_name = "SESSION-BUY.png" if is_buy else "SESSION-SELL.jpg"
    return send_channel_html(client, text, photo_path=image_path(photo_name))


def send_overlap(
    client: httpx.Client,
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
    direction_emoji = "🟢" if signal.direction == "BUY" else "🔴"
    action_ru = "Купить" if signal.direction == "BUY" else "Продать"
    text = (
        f"❌ {title}\n"
        f"🔄 <b>{overlap}</b>\n"
        f"{asset_line(signal.asset)} {signal.asset.market_type.upper()}\n"
        f"🕘 Новый вход: <b>{format_time(signal.entry_time)}</b>\n"
        f"⏱ Экспирация: <b>{format_expiry(signal.expiry_seconds)}</b>\n"
        f"💲 Цена входа: <b>{format_price(signal.entry_price)}</b>\n"
        f"{direction_emoji} <b>{action_ru} ({signal.direction})</b>"
    )
    return send_channel_html(client, text)


def send_refund(client: httpx.Client, signal: SignalEntry) -> int | None:
    text = (
        "🔄 <b>Возврат средств</b>\n"
        f"{asset_line(signal.asset)} {signal.asset.market_type.upper()}\n"
        "Фиксируем возврат и повторяем вход без повышения уровня."
    )
    return send_channel_html(client, text)


def send_signal_result(client: httpx.Client, outcome: SignalOutcome) -> int | None:
    if outcome.result == "WIN":
        text = (
            "✅ <b>СИГНАЛ ОТРАБОТАН В ПЛЮС</b>\n"
            f"{asset_line(outcome.asset)} {outcome.asset.market_type.upper()}\n"
            f"{'🟢' if outcome.direction == 'BUY' else '🔴'} <b>{outcome.direction}</b>\n"
            "💸 Сделка успешно закрылась в прибыль."
        )
    else:
        text = (
            "❌ <b>Серия закрыта в минус</b>\n"
            f"{asset_line(outcome.asset)} {outcome.asset.market_type.upper()} — все уровни отработаны.\n"
            "Фиксируем результат, идём дальше."
        )

    return send_channel_html(client, text, photo_path=outcome.chart_image_path)


def send_session_finished(
    client: httpx.Client,
    *,
    market_type: str,
    session_start_time: datetime,
    session_end_time: datetime,
    total_series: int,
    wins: int,
    losses: int,
) -> int | None:
    text = (
        "🌙 <b>ТОРГОВАЯ СЕССИЯ ЗАВЕРШЕНА</b>\n"
        f"{format_session_time(session_start_time)}–{format_session_time(session_end_time)} · {market_type.upper()}\n"
        f"📊 Отработано сигналов: <b>{total_series}</b>\n"
        f"✅ Плюсы: <b>{wins}</b>\n"
        f"❌ Минусы: <b>{losses}</b>"
    )
    return send_channel_html(client, text, photo_path=image_path("SESSION-FINISH.png"))
