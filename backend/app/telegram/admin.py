from datetime import datetime, timedelta
from html import escape
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.funnel_session import FunnelSession
from app.models.telegram_user import TelegramUser as TelegramUserModel
from app.models.trading import TradingSession
from app.services.devsbite import DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError
from app.services.trading_mvp import (
    ACTIVE_SESSION_STATUSES,
    MVP_EXPIRY_MINUTE_OPTIONS,
    MVP_MARKET_MODES,
    MVP_MIN_PAYOUT,
    TradingMvpConfigError,
    cancel_trading_session,
    create_mvp_trading_session,
    format_mvp_session_summary,
    get_mvp_pair_option,
    get_mvp_pair_options,
    get_mvp_pair_options_with_payout,
    normalize_mvp_market_mode,
    preview_mvp_trading_signal,
)
from app.services.signal_time import format_signal_time
from app.telegram.client import answer_callback_query, copy_message, edit_message_text, send_message, set_chat_menu_button

ADMIN_SIGNAL_PREVIEWS: dict[str, dict[str, Any]] = {}
MVP_PAYOUT_THRESHOLD_OPTIONS = (70, 75, 80, 85, 90)
MVP_CONFIDENCE_THRESHOLD_OPTIONS = (0, 30, 40, 50, 60, 70)


def telegram_error_detail(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.text
    if isinstance(error, HTTPException):
        return str(error.detail)
    return repr(error)


def is_telegram_admin(user: dict[str, Any]) -> bool:
    telegram_id = user.get("id")
    return isinstance(telegram_id, int) and telegram_id in settings.telegram_admin_user_id_set


def get_broadcast_target_chat_ids(db: Session, segment: str = "all") -> list[int]:
    normalized_segment = segment.strip().lower()
    users = db.query(TelegramUserModel).order_by(TelegramUserModel.id.asc()).all()
    if normalized_segment == "all":
        return [int(user.telegram_id) for user in users if user.telegram_id]

    sessions = {
        int(session.telegram_id): session
        for session in db.query(FunnelSession).all()
        if session.telegram_id
    }
    target_chat_ids: list[int] = []
    for user in users:
        telegram_id = int(user.telegram_id)
        session = sessions.get(telegram_id)
        if session is None:
            continue

        has_access = bool(session.access_granted)
        has_trader_id = bool((session.trader_id or "").strip())
        route = (session.route or "").upper()
        reminder_kind = (session.reminder_kind or "").upper()

        matches = (
            (normalized_segment == "bot" and route == "BOT")
            or (normalized_segment == "team" and route == "TEAM")
            or (normalized_segment == "access" and has_access)
            or (normalized_segment == "no_access" and not has_access)
            or (normalized_segment == "need_id" and route in {"BOT", "TEAM"} and not has_access and not has_trader_id)
            or (normalized_segment == "need_topup" and route in {"BOT", "TEAM"} and not has_access and has_trader_id)
            or (normalized_segment == "bot_need_id" and route == "BOT" and not has_access and not has_trader_id)
            or (normalized_segment == "team_need_id" and route == "TEAM" and not has_access and not has_trader_id)
            or (normalized_segment == "bot_need_topup" and route == "BOT" and not has_access and has_trader_id)
            or (normalized_segment == "team_need_topup" and route == "TEAM" and not has_access and has_trader_id)
            or (normalized_segment.startswith("reminder:") and reminder_kind == normalized_segment.removeprefix("reminder:").upper())
        )
        if matches:
            target_chat_ids.append(telegram_id)

    return target_chat_ids


def broadcast_segment_counts(db: Session) -> dict[str, int]:
    segments = [
        "all",
        "bot",
        "team",
        "no_access",
        "access",
        "need_id",
        "need_topup",
        "bot_need_id",
        "team_need_id",
        "bot_need_topup",
        "team_need_topup",
    ]
    return {segment: len(get_broadcast_target_chat_ids(db, segment)) for segment in segments}


def reset_funnel_session(db: Session, telegram_id: int) -> tuple[bool, bool]:
    telegram_user_exists = (
        db.query(TelegramUserModel.id)
        .filter(TelegramUserModel.telegram_id == telegram_id)
        .first()
        is not None
    )
    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    if funnel_session is None:
        return telegram_user_exists, False

    db.delete(funnel_session)
    db.commit()
    return telegram_user_exists, True


def reset_funnel_menu_button(client: httpx.Client, telegram_id: int) -> bool:
    try:
        set_chat_menu_button(client, telegram_id, {"type": "commands"}).raise_for_status()
        return True
    except Exception as error:
        print(f"telegram_funnel_reset_menu_failed telegram_id={telegram_id} detail={telegram_error_detail(error)}")
        return False


def format_admin_help(total_users: int, segment_counts: dict[str, int]) -> str:
    lines = [
        "<b>Админ-команды</b>",
        "",
        "/admin - показать команды и число пользователей в базе",
        "/segments - показать доступные сегменты и количество пользователей",
        "/broadcast текст - отправить HTML-текст всем пользователям",
        "/broadcast ответом на сообщение - скопировать это сообщение всем пользователям",
        "/broadcast_segment segment текст - отправить HTML-текст по сегменту",
        "/broadcast_segment segment ответом на сообщение - скопировать сообщение по сегменту",
        "/broadcast_test текст - отправить тест только себе",
        "/funnel_reset TELEGRAM_ID - сбросить состояние воронки пользователя для повторного теста",
        "",
        "<b>Торговые сессии MVP</b>",
        "/signal_mvp - открыть inline-мастер: рынок -> пороги payout/confidence -> пара -> экспирация -> предпросмотр Devsbite -> подтверждение",
        "/signal_mvp now - тот же мастер, но после подтверждения старт будет через 15 секунд для быстрой проверки воркера",
        "",
        "<b>Управление торговыми сессиями</b>",
        "/signal_sessions - показать запланированные и активные торговые сессии с ID",
        "/signal_cancel ID - отменить scheduled-сессию до старта",
        "/signal_stop ID - остановить running-сессию и отменить будущие jobs",
        "Отмена/остановка не удаляет уже опубликованные сообщения в канале, но прекращает дальнейшие публикации по этой сессии.",
        "",
        "Сейчас MVP работает по Forex/OTC/MIXED-парам из ТЗ. После выбора рынка админ выбирает минимальные payout и confidence. Затем бот показывает пары, отфильтрованные по payout, и предпросмотр Devsbite: signal, API confidence, payout, цену входа, decision_source/reason и TV/TD. В канал сообщение уходит только после кнопки подтверждения. Кнопка «Назад» возвращает к выбору пары.",
        "",
        "<b>Как отправлять рассылки</b>",
        "<b>1. HTML-текст:</b>",
        "<code>/broadcast &lt;b&gt;Заголовок&lt;/b&gt;\n&lt;i&gt;Текст рассылки&lt;/i&gt;</code>",
        "Бот отправит новый текст с parse_mode=HTML. Теги пользователь не увидит.",
        "",
        "<b>2. Ответом на сообщение:</b>",
        "Ответь командой <code>/broadcast</code> на любое сообщение в чате с ботом.",
        "Бот скопирует это сообщение пользователям через copyMessage: сохраняются медиа, форматирование и premium emoji.",
        "",
        "<b>Premium emoji:</b>",
        "Если делаешь рассылку ответом на готовое сообщение, emoji сохраняются автоматически.",
        "Если пишешь HTML вручную, premium emoji нужно вставлять так:",
        "<code>&lt;tg-emoji emoji-id=\"123\"&gt;🔥&lt;/tg-emoji&gt;</code>",
        "ID premium emoji можно получить через @userinfobot.",
        "",
        "<b>3. По сегменту:</b>",
        "<code>/broadcast_segment need_topup &lt;b&gt;Напоминание&lt;/b&gt;</code>",
        "или ответь <code>/broadcast_segment need_topup</code> на готовое сообщение.",
        "",
        "<b>4. Тест себе:</b>",
        "<code>/broadcast_test &lt;b&gt;Проверка&lt;/b&gt;</code>",
        "или ответь <code>/broadcast_test</code> на сообщение.",
        "",
        "<b>Сброс тестового пользователя</b>",
        "<code>/funnel_reset 123456789</code>",
        "Команда удаляет состояние воронки: route, Trader ID, выданный доступ и pending reminders. Пользователь остается в базе Telegram-пользователей.",
        "",
        "<b>Основные сегменты</b>",
        "all - все пользователи",
        "bot - ветка получения бота",
        "team - ветка команды",
        "no_access - доступ еще не выдан",
        "access - доступ уже выдан",
        "need_id - ждем Trader ID",
        "need_topup - Trader ID есть, ждем пополнение",
        "bot_need_id / team_need_id - ждем Trader ID по конкретной ветке",
        "bot_need_topup / team_need_topup - ждем пополнение по конкретной ветке",
        "",
        f"Пользователей в базе: <b>{total_users}</b>",
        f"Без доступа: <b>{segment_counts['no_access']}</b>",
        f"Нужно ID: <b>{segment_counts['need_id']}</b>",
        f"Нужно пополнение: <b>{segment_counts['need_topup']}</b>",
    ]
    return "\n".join(lines)

def send_admin_message(client: httpx.Client, chat_id: int, text: str) -> None:
    send_message(client, chat_id, text, parse_mode="HTML", disable_web_page_preview=True).raise_for_status()


def format_trading_session_admin_line(session: TradingSession) -> str:
    return (
        f"#{session.id} <b>{escape(session.status)}</b> "
        f"{escape(session.market_mode)} "
        f"{format_signal_time(session.starts_at)}-{format_signal_time(session.ends_at)} MSK\n"
        f"Signals: <b>{session.total_series}</b>, wins: <b>{session.wins}</b>, losses: <b>{session.losses}</b>"
    )


def send_signal_sessions(client: httpx.Client, chat_id: int, db: Session) -> None:
    sessions = (
        db.query(TradingSession)
        .filter(TradingSession.status.in_(ACTIVE_SESSION_STATUSES))
        .order_by(TradingSession.starts_at.asc(), TradingSession.id.asc())
        .limit(20)
        .all()
    )
    if not sessions:
        send_admin_message(client, chat_id, "Открытых торговых сессий нет.")
        return

    lines = [
        "<b>Открытые торговые сессии</b>",
        "",
        *[format_trading_session_admin_line(session) for session in sessions],
        "",
        "Команды:",
        "<code>/signal_cancel ID</code> - отменить запланированную сессию до старта",
        "<code>/signal_stop ID</code> - остановить уже активную сессию",
    ]
    send_admin_message(client, chat_id, "\n\n".join(lines))


def handle_signal_session_control(
    client: httpx.Client,
    chat_id: int,
    db: Session,
    *,
    command_name: str,
    command_body: str,
    admin_telegram_id: int | None,
) -> None:
    session_id_text = command_body.strip().split(maxsplit=1)[0] if command_body.strip() else ""
    if not session_id_text.isdigit():
        usage = "/signal_cancel ID" if command_name == "/signal_cancel" else "/signal_stop ID"
        send_admin_message(client, chat_id, f"Укажи ID сессии: <code>{usage}</code>")
        return

    session_id = int(session_id_text)
    is_stop = command_name == "/signal_stop"
    allowed_statuses = ("running",) if is_stop else ("scheduled",)
    action_text = "остановлена" if is_stop else "отменена"
    reason = (
        f"Stopped by admin {admin_telegram_id}."
        if is_stop
        else f"Cancelled before start by admin {admin_telegram_id}."
    )

    try:
        session = cancel_trading_session(
            db,
            session_id,
            reason=reason,
            allowed_statuses=allowed_statuses,
        )
    except TradingMvpConfigError as error:
        send_admin_message(client, chat_id, f"Не удалось выполнить команду: <code>{escape(str(error))}</code>")
        return

    send_admin_message(
        client,
        chat_id,
        (
            f"Торговая сессия #{session.id} {action_text}.\n"
            f"Status: <b>{escape(session.status)}</b>\n"
            f"Window: <b>{format_signal_time(session.starts_at)}-{format_signal_time(session.ends_at)} MSK</b>"
        ),
    )


def signal_callback(action: str, *parts: object) -> str:
    return ":".join(["admin_signal", action, *[str(part) for part in parts]])


def signal_market_keyboard(fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    return {
        "inline_keyboard": [
            [
                {"text": "FOREX", "callback_data": signal_callback("market", "FOREX", fast_token)},
                {"text": "OTC", "callback_data": signal_callback("market", "OTC", fast_token)},
                {"text": "MIXED", "callback_data": signal_callback("market", "MIXED", fast_token)},
            ]
        ]
    }


def signal_payout_keyboard(market_mode: str, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    rows: list[list[dict[str, str]]] = []
    current_row: list[dict[str, str]] = []
    for payout in MVP_PAYOUT_THRESHOLD_OPTIONS:
        current_row.append(
            {
                "text": f"{payout}%",
                "callback_data": signal_callback("payout", market_mode, payout, fast_token),
            }
        )
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([{"text": "⬅️ Назад к выбору рынка", "callback_data": signal_callback("markets", fast_token)}])
    return {"inline_keyboard": rows}


def signal_confidence_keyboard(market_mode: str, min_payout: int, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    rows: list[list[dict[str, str]]] = []
    current_row: list[dict[str, str]] = []
    for confidence in MVP_CONFIDENCE_THRESHOLD_OPTIONS:
        current_row.append(
            {
                "text": f"{confidence}%",
                "callback_data": signal_callback("confidence", market_mode, min_payout, confidence, fast_token),
            }
        )
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([{"text": "⬅️ Назад к payout", "callback_data": signal_callback("market", market_mode, fast_token)}])
    return {"inline_keyboard": rows}


def signal_pair_keyboard(market_mode: str, fast: bool, min_payout: int = MVP_MIN_PAYOUT, min_confidence: int = MVP_MIN_CONFIDENCE) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    current_row: list[dict[str, str]] = []
    fast_token = "1" if fast else "0"
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    pairs_with_payout = get_mvp_pair_options_with_payout(normalized_market_mode, min_payout=min_payout)
    for pair, payout in pairs_with_payout:
        current_row.append(
            {
                "text": f"{pair.flag_1}{pair.flag_2} {pair.symbol} · {payout}%",
                "callback_data": signal_callback(
                    "pair",
                    normalized_market_mode,
                    min_payout,
                    min_confidence,
                    pair.code,
                    fast_token,
                ),
            }
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    if not rows:
        rows.append(
            [
                {
                    "text": f"Нет пар с payout >= {min_payout}%",
                    "callback_data": signal_callback("noop"),
                }
            ]
        )
    rows.append([{"text": "⬅️ Назад к confidence", "callback_data": signal_callback("payout", normalized_market_mode, min_payout, fast_token)}])
    return {"inline_keyboard": rows}


def signal_expiry_keyboard(
    market_mode: str,
    pair_code: str,
    fast: bool,
    min_payout: int = MVP_MIN_PAYOUT,
    min_confidence: int = MVP_MIN_CONFIDENCE,
) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    rows: list[list[dict[str, str]]] = []
    current_row: list[dict[str, str]] = []
    for expiry in MVP_EXPIRY_MINUTE_OPTIONS:
        current_row.append(
            {
                "text": f"{expiry}m",
                "callback_data": signal_callback(
                    "expiry",
                    normalized_market_mode,
                    min_payout,
                    min_confidence,
                    pair_code,
                    expiry,
                    fast_token,
                ),
            }
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append(
        [
            {
                "text": "⬅️ Назад к выбору пар",
                "callback_data": signal_callback("back", normalized_market_mode, min_payout, min_confidence, fast_token),
            }
        ]
    )
    return {"inline_keyboard": rows}


def send_signal_market_menu(client: httpx.Client, chat_id: int, *, fast: bool) -> None:
    mode_text = "быстрый тест: старт через 15 секунд" if fast else "обычный режим: старт через 60 минут"
    send_message(
        client,
        chat_id,
        (
            "<b>MVP торговая сессия</b>\n\n"
            f"Режим: <b>{mode_text}</b>\n"
            "Выберите режим рынка из списка."
        ),
        parse_mode="HTML",
        reply_markup=signal_market_keyboard(fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_payout_menu(client: httpx.Client, chat_id: int, *, market_mode: str, fast: bool) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP торговая сессия</b>\n\n"
            f"Режим рынка: <b>{normalized_market_mode}</b>\n"
            "Выберите минимальный payout для фильтрации пар."
        ),
        parse_mode="HTML",
        reply_markup=signal_payout_keyboard(normalized_market_mode, fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_confidence_menu(
    client: httpx.Client,
    chat_id: int,
    *,
    market_mode: str,
    min_payout: int,
    fast: bool,
) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP торговая сессия</b>\n\n"
            f"Режим рынка: <b>{normalized_market_mode}</b>\n"
            f"Min payout: <b>{min_payout}%</b>\n"
            "Выберите минимальный confidence от Devsbite."
        ),
        parse_mode="HTML",
        reply_markup=signal_confidence_keyboard(normalized_market_mode, min_payout, fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_pair_menu(
    client: httpx.Client,
    chat_id: int,
    *,
    market_mode: str = "FOREX",
    fast: bool,
    min_payout: int = MVP_MIN_PAYOUT,
    min_confidence: int = MVP_MIN_CONFIDENCE,
) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP торговая сессия</b>\n\n"
            f"Режим рынка: <b>{normalized_market_mode}</b>\n"
            f"Min payout: <b>{min_payout}%</b>\n"
            f"Min confidence: <b>{min_confidence}%</b>\n"
            "Выберите пару. Список уже отфильтрован через Devsbite по выбранному payout."
        ),
        parse_mode="HTML",
        reply_markup=signal_pair_keyboard(normalized_market_mode, fast, min_payout, min_confidence),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_expiry_menu(
    client: httpx.Client,
    chat_id: int,
    market_mode: str,
    pair_code: str,
    *,
    fast: bool,
    min_payout: int = MVP_MIN_PAYOUT,
    min_confidence: int = MVP_MIN_CONFIDENCE,
) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    pair = get_mvp_pair_option(pair_code)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP торговая сессия</b>\n\n"
            f"Режим рынка: <b>{normalized_market_mode}</b>\n"
            f"Min payout: <b>{min_payout}%</b>\n"
            f"Min confidence: <b>{min_confidence}%</b>\n"
            f"Пара: <b>{escape(pair.symbol)}</b>\n"
            "Выберите экспирацию для предпросмотра Devsbite."
        ),
        parse_mode="HTML",
        reply_markup=signal_expiry_keyboard(normalized_market_mode, pair_code, fast, min_payout, min_confidence),
        disable_web_page_preview=True,
    ).raise_for_status()


def signal_error_keyboard(market_mode: str | None, fast: bool) -> dict[str, Any] | None:
    fast_token = "1" if fast else "0"
    if market_mode is None:
        return {
            "inline_keyboard": [
                [{"text": "⬅️ Назад к выбору рынка", "callback_data": signal_callback("markets", fast_token)}]
            ]
        }

    return {
        "inline_keyboard": [
            [{"text": "⬅️ Назад к выбору пар", "callback_data": signal_callback("back", market_mode, fast_token)}]
        ]
    }


def send_signal_callback_error(
    client: httpx.Client,
    chat_id: int,
    message_id: int | None,
    error: Exception,
    *,
    market_mode: str | None = None,
    fast: bool = False,
) -> None:
    detail = escape(str(error))
    if len(detail) > 900:
        detail = f"{detail[:900]}..."

    text = (
        "<b>MVP торговая сессия</b>\n\n"
        "Не удалось получить данные Devsbite.\n"
        f"Причина: <code>{detail}</code>\n\n"
        "Выбери другую пару или вернись назад."
    )
    reply_markup = signal_error_keyboard(market_mode, fast)

    if message_id is None:
        send_message(
            client,
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        ).raise_for_status()
        return

    try:
        edit_message_text(
            client,
            chat_id,
            message_id,
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        ).raise_for_status()
    except httpx.HTTPStatusError as edit_error:
        print(f"telegram_admin_signal_error_edit_failed detail={telegram_error_detail(edit_error)}")


def safe_answer_admin_callback(
    client: httpx.Client,
    callback_id: str | None,
    text: str,
    *,
    show_alert: bool = False,
) -> None:
    if not callback_id:
        return

    try:
        answer_callback_query(client, callback_id, text, show_alert=show_alert).raise_for_status()
    except httpx.HTTPStatusError as error:
        print(f"telegram_admin_answer_callback_failed detail={telegram_error_detail(error)}")


def format_signal_preview(preview: dict) -> str:
    pair = preview["pair"]
    analysis = preview["analysis"]
    price = preview["entry_price"]
    api_signal = escape(str(analysis.get("signal") or "-"))
    api_confidence = escape(str(analysis.get("confidence") if analysis.get("confidence") is not None else "-"))
    payout = escape(str(preview.get("payout") if preview.get("payout") is not None else "-"))
    decision_source = escape(str(analysis.get("decision_source") or "-"))
    decision_reason = escape(str(analysis.get("decision_reason") or "-"))
    tv_recommendation = escape(str(analysis.get("tv_recommendation") or "-"))
    td_recommendation = escape(str(analysis.get("td_recommendation") or "-"))
    price_text = escape(str(price)) if price is not None else "-"
    market_mode = escape(str(preview.get("market_mode") or pair.market_type))
    analysis_symbol = escape(str(preview.get("analysis_symbol") or pair.symbol))
    min_payout = escape(str(preview.get("min_payout", MVP_MIN_PAYOUT)))
    min_confidence = escape(str(preview.get("min_confidence", MVP_MIN_CONFIDENCE)))

    return (
        "<b>Предпросмотр Devsbite</b>\n\n"
        f"Режим рынка: <b>{market_mode}</b>\n"
        f"Тип пары: <b>{escape(pair.market_type)}</b>\n"
        f"Пара: <b>{escape(pair.symbol)}</b>\n"
        f"Analysis symbol: <code>{analysis_symbol}</code>\n"
        f"Экспирация: <b>{preview['expiry_minutes']}m</b>\n"
        f"Min payout: <b>{min_payout}%</b>\n"
        f"Min confidence: <b>{min_confidence}%</b>\n"
        f"Цена входа: <code>{price_text}</code>\n\n"
        f"API signal: <b>{api_signal}</b>\n"
        f"API confidence: <b>{api_confidence}%</b>\n"
        f"Payout: <b>{payout}%</b>\n"
        f"Направление для канала: <b>{preview['direction']}</b>\n\n"
        f"Источник решения: <code>{decision_source}</code>\n"
        f"Причина: <code>{decision_reason}</code>\n"
        f"TV / TD: <code>{tv_recommendation}</code> / <code>{td_recommendation}</code>\n\n"
        "Если данные подходят, подтверди отправку. Если нет — вернись к выбору пары."
    )


def signal_confirm_keyboard(preview_token: str, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Подтвердить отправку",
                    "callback_data": signal_callback("confirm", preview_token, fast_token),
                }
            ],
            [{"text": "⬅️ Назад к выбору пар", "callback_data": signal_callback("preview_back", preview_token, fast_token)}],
        ]
    }


def send_signal_preview(
    client: httpx.Client,
    chat_id: int,
    market_mode: str,
    pair_code: str,
    expiry_minutes: int,
    *,
    fast: bool,
    min_payout: int = MVP_MIN_PAYOUT,
    min_confidence: int = MVP_MIN_CONFIDENCE,
) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    pair = get_mvp_pair_option(pair_code)
    if pair not in get_mvp_pair_options(normalized_market_mode):
        raise ValueError(f"Pair {pair.symbol} is not allowed for market mode {normalized_market_mode}")
    preview = preview_mvp_trading_signal(
        pair,
        expiry_minutes,
        min_payout=min_payout,
        min_confidence=min_confidence,
    )
    preview["market_mode"] = normalized_market_mode
    preview_token = uuid4().hex
    ADMIN_SIGNAL_PREVIEWS[preview_token] = preview
    send_message(
        client,
        chat_id,
        format_signal_preview(preview),
        parse_mode="HTML",
        reply_markup=signal_confirm_keyboard(preview_token, fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def broadcast_text(client: httpx.Client, target_chat_ids: list[int], text: str) -> tuple[int, int]:
    sent = 0
    failed = 0
    for target_chat_id in target_chat_ids:
        try:
            send_message(client, target_chat_id, text, parse_mode="HTML", disable_web_page_preview=True).raise_for_status()
            sent += 1
        except Exception as error:
            failed += 1
            print(f"telegram_broadcast_text_failed chat_id={target_chat_id} detail={telegram_error_detail(error)}")
    return sent, failed


def broadcast_copy_message(
    client: httpx.Client,
    target_chat_ids: list[int],
    source_chat_id: int,
    source_message_id: int,
) -> tuple[int, int]:
    sent = 0
    failed = 0
    for target_chat_id in target_chat_ids:
        try:
            copy_message(client, target_chat_id, source_chat_id, source_message_id).raise_for_status()
            sent += 1
        except Exception as error:
            failed += 1
            print(f"telegram_broadcast_copy_failed chat_id={target_chat_id} detail={telegram_error_detail(error)}")
    return sent, failed


def handle_admin_callback_query(db: Session, callback_query: dict[str, Any]) -> bool:
    data = callback_query.get("data") or ""
    if not data.startswith("admin_signal:"):
        return False

    callback_id = callback_query.get("id")
    user = callback_query.get("from") or {}
    message = callback_query.get("message") or {}
    message_id = message.get("message_id")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return True

    with httpx.Client(timeout=30) as client:
        if not is_telegram_admin(user):
            safe_answer_admin_callback(client, callback_id, "Недостаточно прав", show_alert=True)
            print(f"telegram_admin_callback_denied telegram_id={user.get('id')} data={data}")
            return True

        callback_text = "Ок"
        callback_alert = False
        action = ""
        parts: list[str] = []
        error_market_mode: str | None = None
        error_fast = False
        try:
            _, action, *parts = data.split(":")
            if action == "noop":
                callback_text = "Нет доступных пар"
            elif action == "markets":
                fast = bool(parts and parts[0] == "1")
                send_signal_market_menu(client, chat_id, fast=fast)
            elif action == "back":
                if len(parts) >= 4 and parts[0] in MVP_MARKET_MODES:
                    market_mode = parts[0]
                    min_payout = int(parts[1])
                    min_confidence = int(parts[2])
                    fast = parts[3] == "1"
                    error_market_mode = market_mode
                    error_fast = fast
                    send_signal_pair_menu(
                        client,
                        chat_id,
                        market_mode=market_mode,
                        fast=fast,
                        min_payout=min_payout,
                        min_confidence=min_confidence,
                    )
                else:
                    fast = bool(parts and parts[0] == "1")
                    error_fast = fast
                    send_signal_market_menu(client, chat_id, fast=fast)
            elif action == "market":
                market_mode = normalize_mvp_market_mode(parts[0])
                fast = len(parts) > 1 and parts[1] == "1"
                error_market_mode = market_mode
                error_fast = fast
                send_signal_payout_menu(client, chat_id, market_mode=market_mode, fast=fast)
            elif action == "payout":
                market_mode = normalize_mvp_market_mode(parts[0])
                min_payout = int(parts[1])
                fast = len(parts) > 2 and parts[2] == "1"
                error_market_mode = market_mode
                error_fast = fast
                send_signal_confidence_menu(
                    client,
                    chat_id,
                    market_mode=market_mode,
                    min_payout=min_payout,
                    fast=fast,
                )
            elif action == "confidence":
                market_mode = normalize_mvp_market_mode(parts[0])
                min_payout = int(parts[1])
                min_confidence = int(parts[2])
                fast = len(parts) > 3 and parts[3] == "1"
                error_market_mode = market_mode
                error_fast = fast
                send_signal_pair_menu(
                    client,
                    chat_id,
                    market_mode=market_mode,
                    fast=fast,
                    min_payout=min_payout,
                    min_confidence=min_confidence,
                )
            elif action == "pair":
                if len(parts) >= 5 and parts[0] in MVP_MARKET_MODES:
                    market_mode = normalize_mvp_market_mode(parts[0])
                    min_payout = int(parts[1])
                    min_confidence = int(parts[2])
                    pair_code = parts[3]
                    fast = parts[4] == "1"
                else:
                    market_mode = "FOREX"
                    min_payout = MVP_MIN_PAYOUT
                    min_confidence = MVP_MIN_CONFIDENCE
                    pair_code = parts[0]
                    fast = len(parts) > 1 and parts[1] == "1"
                send_signal_expiry_menu(
                    client,
                    chat_id,
                    market_mode,
                    pair_code,
                    fast=fast,
                    min_payout=min_payout,
                    min_confidence=min_confidence,
                )
            elif action == "expiry":
                if len(parts) >= 6 and parts[0] in MVP_MARKET_MODES:
                    market_mode = normalize_mvp_market_mode(parts[0])
                    min_payout = int(parts[1])
                    min_confidence = int(parts[2])
                    pair_code = parts[3]
                    expiry_minutes = int(parts[4])
                    fast = parts[5] == "1"
                else:
                    market_mode = "FOREX"
                    min_payout = MVP_MIN_PAYOUT
                    min_confidence = MVP_MIN_CONFIDENCE
                    pair_code = parts[0]
                    expiry_minutes = int(parts[1])
                    fast = len(parts) > 2 and parts[2] == "1"
                error_market_mode = market_mode
                error_fast = fast
                send_signal_preview(
                    client,
                    chat_id,
                    market_mode,
                    pair_code,
                    expiry_minutes,
                    fast=fast,
                    min_payout=min_payout,
                    min_confidence=min_confidence,
                )
            elif action == "preview_back":
                preview_token = parts[0]
                fast = len(parts) > 1 and parts[1] == "1"
                preview = ADMIN_SIGNAL_PREVIEWS.get(preview_token)
                market_mode = preview.get("market_mode", "FOREX") if preview else "FOREX"
                min_payout = int(preview.get("min_payout", MVP_MIN_PAYOUT)) if preview else MVP_MIN_PAYOUT
                min_confidence = int(preview.get("min_confidence", MVP_MIN_CONFIDENCE)) if preview else MVP_MIN_CONFIDENCE
                send_signal_pair_menu(
                    client,
                    chat_id,
                    market_mode=market_mode,
                    fast=fast,
                    min_payout=min_payout,
                    min_confidence=min_confidence,
                )
            elif action == "confirm":
                preview_token = parts[0]
                fast = len(parts) > 1 and parts[1] == "1"
                preview = ADMIN_SIGNAL_PREVIEWS.pop(preview_token, None)
                if preview is None:
                    send_admin_message(client, chat_id, "Предпросмотр устарел. Запусти /signal_mvp заново.")
                    callback_text = "Предпросмотр устарел"
                    safe_answer_admin_callback(client, callback_id, callback_text, show_alert=True)
                    return True
                start_at = datetime.utcnow() + timedelta(seconds=15) if fast else None
                session = create_mvp_trading_session(
                    db,
                    created_by_telegram_id=user.get("id"),
                    start_at=start_at,
                    pair=preview["pair"],
                    market_mode=preview.get("market_mode", "FOREX"),
                    expiry_minutes=preview["expiry_minutes"],
                    min_payout=int(preview.get("min_payout", MVP_MIN_PAYOUT)),
                    min_confidence=int(preview.get("min_confidence", MVP_MIN_CONFIDENCE)),
                    preview=preview,
                )
                send_admin_message(client, chat_id, format_mvp_session_summary(session))
                callback_text = "Сессия создана"
            else:
                callback_text = "Неизвестное действие"
        except (
            DevsbiteApiError,
            DevsbiteConfigError,
            DevsbiteRequestError,
            TradingMvpConfigError,
            ValueError,
            IndexError,
        ) as error:
            callback_text = "Ошибка"
            callback_alert = True
            if action == "expiry" and error_market_mode is None and parts:
                if parts[0] in MVP_MARKET_MODES:
                    error_market_mode = normalize_mvp_market_mode(parts[0])
                    error_fast = len(parts) > 3 and parts[3] == "1"
                else:
                    error_market_mode = "FOREX"
                    error_fast = len(parts) > 2 and parts[2] == "1"
            send_signal_callback_error(
                client,
                chat_id,
                message_id if isinstance(message_id, int) else None,
                error,
                market_mode=error_market_mode,
                fast=error_fast,
            )

        safe_answer_admin_callback(client, callback_id, callback_text, show_alert=callback_alert)
    return True


def handle_admin_command_message(db: Session, user: dict[str, Any], chat_id: int, message: dict[str, Any], text: str) -> bool:
    if (
        not text.startswith("/admin")
        and not text.startswith("/broadcast")
        and not text.startswith("/segments")
        and not text.startswith("/signal_mvp")
        and not text.startswith("/signal_sessions")
        and not text.startswith("/signal_cancel")
        and not text.startswith("/signal_stop")
        and not text.startswith("/funnel_reset")
    ):
        return False

    with httpx.Client(timeout=30) as client:
        if not is_telegram_admin(user):
            print(f"telegram_admin_command_denied telegram_id={user.get('id')} command={text.split(maxsplit=1)[0]}")
            return True

        command, _, command_body = text.partition(" ")
        command_name = command.split("@", 1)[0]
        target_chat_ids = get_broadcast_target_chat_ids(db)

        if command_name == "/admin":
            segment_counts = broadcast_segment_counts(db)
            send_admin_message(client, chat_id, format_admin_help(len(target_chat_ids), segment_counts))
            return True

        if command_name == "/segments":
            counts = broadcast_segment_counts(db)
            lines = ["<b>Сегменты рассылки</b>"]
            lines.extend(f"{segment}: <b>{count}</b>" for segment, count in counts.items())
            send_admin_message(client, chat_id, "\n".join(lines))
            return True

        if command_name == "/signal_mvp":
            send_signal_market_menu(client, chat_id, fast=command_body.strip() == "now")
            return True

        if command_name == "/signal_sessions":
            send_signal_sessions(client, chat_id, db)
            return True

        if command_name in {"/signal_cancel", "/signal_stop"}:
            handle_signal_session_control(
                client,
                chat_id,
                db,
                command_name=command_name,
                command_body=command_body,
                admin_telegram_id=user.get("id") if isinstance(user.get("id"), int) else None,
            )
            return True

        if command_name == "/funnel_reset":
            telegram_id_text = command_body.strip().split(maxsplit=1)[0] if command_body.strip() else ""
            if not telegram_id_text.isdigit():
                send_admin_message(client, chat_id, "Укажи Telegram ID: <code>/funnel_reset 123456789</code>")
                return True

            telegram_id = int(telegram_id_text)
            user_exists, session_deleted = reset_funnel_session(db, telegram_id)
            menu_reset = reset_funnel_menu_button(client, telegram_id) if user_exists or session_deleted else False
            if session_deleted:
                send_admin_message(
                    client,
                    chat_id,
                    (
                        "Состояние воронки сброшено.\n"
                        f"Telegram ID: <code>{telegram_id}</code>\n"
                        f"Mini App menu: <b>{'сброшено' if menu_reset else 'не удалось сбросить'}</b>\n"
                        "Теперь пользователь может заново открыть deep-link или отправить /start."
                    ),
                )
                return True

            if user_exists:
                send_admin_message(
                    client,
                    chat_id,
                    (
                        "У пользователя нет активного состояния воронки.\n"
                        f"Telegram ID: <code>{telegram_id}</code>\n"
                        f"Mini App menu: <b>{'сброшено' if menu_reset else 'не удалось сбросить'}</b>\n"
                        "Telegram-пользователь в базе есть, но сбрасывать нечего."
                    ),
                )
                return True

            send_admin_message(
                client,
                chat_id,
                (
                    "Пользователь не найден в базе.\n"
                    f"Telegram ID: <code>{telegram_id}</code>"
                ),
            )
            return True

        if command_name == "/broadcast_test":
            reply_to_message = message.get("reply_to_message")
            if reply_to_message:
                sent, failed = broadcast_copy_message(client, [chat_id], chat_id, reply_to_message["message_id"])
            elif command_body.strip():
                sent, failed = broadcast_text(client, [chat_id], command_body.strip())
            else:
                send_admin_message(client, chat_id, "Ответь командой на сообщение или добавь текст после /broadcast_test.")
                return True

            send_admin_message(client, chat_id, f"Тестовая рассылка: отправлено {sent}, ошибок {failed}.")
            return True

        if command_name == "/broadcast_segment":
            segment, _, segment_text = command_body.strip().partition(" ")
            if not segment:
                send_admin_message(client, chat_id, "Укажи сегмент: <code>/broadcast_segment need_id текст</code>")
                return True

            segment_target_chat_ids = get_broadcast_target_chat_ids(db, segment)
            reply_to_message = message.get("reply_to_message")
            if reply_to_message:
                sent, failed = broadcast_copy_message(client, segment_target_chat_ids, chat_id, reply_to_message["message_id"])
            elif segment_text.strip():
                sent, failed = broadcast_text(client, segment_target_chat_ids, segment_text.strip())
            else:
                send_admin_message(client, chat_id, "Ответь /broadcast_segment segment на сообщение или добавь текст после сегмента.")
                return True

            send_admin_message(
                client,
                chat_id,
                (
                    f"Сегментная рассылка завершена.\n"
                    f"Сегмент: <b>{escape(segment)}</b>\n"
                    f"Отправлено: <b>{sent}</b>\n"
                    f"Ошибок: <b>{failed}</b>\n"
                    f"Всего целей: <b>{len(segment_target_chat_ids)}</b>"
                ),
            )
            return True

        if command_name != "/broadcast":
            send_admin_message(client, chat_id, "Неизвестная админ-команда. Используй /admin.")
            return True

        reply_to_message = message.get("reply_to_message")
        if reply_to_message:
            sent, failed = broadcast_copy_message(client, target_chat_ids, chat_id, reply_to_message["message_id"])
        elif command_body.strip():
            sent, failed = broadcast_text(client, target_chat_ids, command_body.strip())
        else:
            send_admin_message(client, chat_id, "Ответь /broadcast на сообщение или напиши текст после команды.")
            return True

        send_admin_message(
            client,
            chat_id,
            f"Рассылка завершена.\nОтправлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>\nВсего целей: <b>{len(target_chat_ids)}</b>",
        )
        return True
