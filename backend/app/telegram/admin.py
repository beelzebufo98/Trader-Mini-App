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
    TradingMvpConfigError,
    cancel_trading_session,
    create_mvp_trading_session,
    format_mvp_session_summary,
    get_mvp_pair_option,
    get_mvp_pair_options,
    normalize_mvp_market_mode,
    preview_mvp_trading_signal,
)
from app.services.signal_time import format_signal_time
from app.telegram.client import answer_callback_query, copy_message, send_message

ADMIN_SIGNAL_PREVIEWS: dict[str, dict[str, Any]] = {}


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


def format_admin_help(total_users: int, segment_counts: dict[str, int]) -> str:
    # This help uses ASCII unicode escapes to avoid mojibake from Windows console encodings.
    lines = [
        '<b>\u0410\u0434\u043c\u0438\u043d-\u043a\u043e\u043c\u0430\u043d\u0434\u044b</b>\\n',
        '\\n',
        '/admin - \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043a\u043e\u043c\u0430\u043d\u0434\u044b \u0438 \u0447\u0438\u0441\u043b\u043e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439 \u0432 \u0431\u0430\u0437\u0435\\n',
        '/segments - \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u044b \u0438 \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439\\n',
        '/broadcast \u0442\u0435\u043a\u0441\u0442 - \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c HTML-\u0442\u0435\u043a\u0441\u0442 \u0432\u0441\u0435\u043c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f\u043c\\n',
        '/broadcast \u043e\u0442\u0432\u0435\u0442\u043e\u043c \u043d\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 - \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u044d\u0442\u043e \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0432\u0441\u0435\u043c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f\u043c\\n',
        '/broadcast_segment segment \u0442\u0435\u043a\u0441\u0442 - \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c HTML-\u0442\u0435\u043a\u0441\u0442 \u043f\u043e \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u0443\\n',
        '/broadcast_segment segment \u043e\u0442\u0432\u0435\u0442\u043e\u043c \u043d\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 - \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043f\u043e \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u0443\\n',
        '/broadcast_test \u0442\u0435\u043a\u0441\u0442 - \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0442\u0435\u0441\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0441\u0435\u0431\u0435\\n',
        '\\n',
        '<b>\u0422\u043e\u0440\u0433\u043e\u0432\u044b\u0435 \u0441\u0435\u0441\u0441\u0438\u0438 MVP</b>\\n',
        '/signal_mvp - \u043e\u0442\u043a\u0440\u044b\u0442\u044c inline-\u043c\u0430\u0441\u0442\u0435\u0440: \u043f\u0430\u0440\u0430 -> \u044d\u043a\u0441\u043f\u0438\u0440\u0430\u0446\u0438\u044f -> \u043f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 Devsbite -> \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435\\n',
        '/signal_mvp now - \u0442\u043e\u0442 \u0436\u0435 \u043c\u0430\u0441\u0442\u0435\u0440, \u043d\u043e \u043f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u0441\u0442\u0430\u0440\u0442 \u0431\u0443\u0434\u0435\u0442 \u0447\u0435\u0440\u0435\u0437 15 \u0441\u0435\u043a\u0443\u043d\u0434 \u0434\u043b\u044f \u0431\u044b\u0441\u0442\u0440\u043e\u0439 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0432\u043e\u0440\u043a\u0435\u0440\u0430\\n',
        '\\n',
        '<b>\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0442\u043e\u0440\u0433\u043e\u0432\u044b\u043c\u0438 \u0441\u0435\u0441\u0441\u0438\u044f\u043c\u0438</b>\\n',
        '/signal_sessions - \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0437\u0430\u043f\u043b\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0435 \u0438 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0435 \u0442\u043e\u0440\u0433\u043e\u0432\u044b\u0435 \u0441\u0435\u0441\u0441\u0438\u0438 \u0441 ID\\n',
        '/signal_cancel ID - \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c scheduled-\u0441\u0435\u0441\u0441\u0438\u044e \u0434\u043e \u0441\u0442\u0430\u0440\u0442\u0430\\n',
        '/signal_stop ID - \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c running-\u0441\u0435\u0441\u0441\u0438\u044e \u0438 \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c \u0431\u0443\u0434\u0443\u0449\u0438\u0435 jobs\\n',
        '\u041e\u0442\u043c\u0435\u043d\u0430/\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430 \u043d\u0435 \u0443\u0434\u0430\u043b\u044f\u0435\u0442 \u0443\u0436\u0435 \u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d\u043d\u044b\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u0432 \u043a\u0430\u043d\u0430\u043b\u0435, \u043d\u043e \u043f\u0440\u0435\u043a\u0440\u0430\u0449\u0430\u0435\u0442 \u0434\u0430\u043b\u044c\u043d\u0435\u0439\u0448\u0438\u0435 \u043f\u0443\u0431\u043b\u0438\u043a\u0430\u0446\u0438\u0438 \u043f\u043e \u044d\u0442\u043e\u0439 \u0441\u0435\u0441\u0441\u0438\u0438.\\n',
        '\\n',
        '\u0421\u0435\u0439\u0447\u0430\u0441 MVP \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 \u043f\u043e <b>Forex-\u043f\u0430\u0440\u0430\u043c \u0438\u0437 \u0422\u0417</b>. \u041f\u043e\u0441\u043b\u0435 \u0432\u044b\u0431\u043e\u0440\u0430 \u043f\u0430\u0440\u044b \u0438 \u044d\u043a\u0441\u043f\u0438\u0440\u0430\u0446\u0438\u0438 \u0431\u043e\u0442 \u0441\u043d\u0430\u0447\u0430\u043b\u0430 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442, \u0447\u0442\u043e \u0432\u0435\u0440\u043d\u0443\u043b Devsbite: signal, API confidence, \u0446\u0435\u043d\u0443 \u0432\u0445\u043e\u0434\u0430, decision_source/reason \u0438 TV/TD. \u0412 \u043a\u0430\u043d\u0430\u043b \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0443\u0445\u043e\u0434\u0438\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u043e\u0441\u043b\u0435 \u043a\u043d\u043e\u043f\u043a\u0438 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f. \u041a\u043d\u043e\u043f\u043a\u0430 \xab\u041d\u0430\u0437\u0430\u0434\xbb \u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u0442 \u043a \u0432\u044b\u0431\u043e\u0440\u0443 \u043f\u0430\u0440\u044b.\\n',
        '\\n',
        '<b>\u041a\u0430\u043a \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0442\u044c \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438</b>\\n',
        '<b>1. HTML-\u0442\u0435\u043a\u0441\u0442:</b>\\n',
        '<code>/broadcast &lt;b&gt;\u0417\u0430\u0433\u043e\u043b\u043e\u0432\u043e\u043a&lt;/b&gt;\\n',
        '&lt;i&gt;\u0422\u0435\u043a\u0441\u0442 \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0438&lt;/i&gt;</code>\\n',
        '\u0411\u043e\u0442 \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442 \u043d\u043e\u0432\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 \u0441 parse_mode=HTML. \u0422\u0435\u0433\u0438 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u043d\u0435 \u0443\u0432\u0438\u0434\u0438\u0442.\\n',
        '\\n',
        '<b>2. \u041e\u0442\u0432\u0435\u0442\u043e\u043c \u043d\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435:</b>\\n',
        '\u041e\u0442\u0432\u0435\u0442\u044c \u043a\u043e\u043c\u0430\u043d\u0434\u043e\u0439 <code>/broadcast</code> \u043d\u0430 \u043b\u044e\u0431\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u0432 \u0447\u0430\u0442\u0435 \u0441 \u0431\u043e\u0442\u043e\u043c.\\n',
        '\u0411\u043e\u0442 \u0441\u043a\u043e\u043f\u0438\u0440\u0443\u0435\u0442 \u044d\u0442\u043e \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f\u043c \u0447\u0435\u0440\u0435\u0437 copyMessage: \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u044e\u0442\u0441\u044f \u043c\u0435\u0434\u0438\u0430, \u0444\u043e\u0440\u043c\u0430\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u0438 premium emoji.\\n',
        '\\n',
        '<b>Premium emoji:</b>\\n',
        '\u0415\u0441\u043b\u0438 \u0434\u0435\u043b\u0430\u0435\u0448\u044c \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0443 \u043e\u0442\u0432\u0435\u0442\u043e\u043c \u043d\u0430 \u0433\u043e\u0442\u043e\u0432\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435, emoji \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u044e\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.\\n',
        '\u0415\u0441\u043b\u0438 \u043f\u0438\u0448\u0435\u0448\u044c HTML \u0432\u0440\u0443\u0447\u043d\u0443\u044e, premium emoji \u043d\u0443\u0436\u043d\u043e \u0432\u0441\u0442\u0430\u0432\u043b\u044f\u0442\u044c \u0442\u0430\u043a:\\n',
        '<code>&lt;tg-emoji emoji-id="123"&gt;\U0001f525&lt;/tg-emoji&gt;</code>\\n',
        'ID premium emoji \u043c\u043e\u0436\u043d\u043e \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0447\u0435\u0440\u0435\u0437 @userinfobot.\\n',
        '\\n',
        '<b>3. \u041f\u043e \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u0443:</b>\\n',
        '<code>/broadcast_segment need_topup &lt;b&gt;\u041d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u0435&lt;/b&gt;</code>\\n',
        '\u0438\u043b\u0438 \u043e\u0442\u0432\u0435\u0442\u044c <code>/broadcast_segment need_topup</code> \u043d\u0430 \u0433\u043e\u0442\u043e\u0432\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435.\\n',
        '\\n',
        '<b>4. \u0422\u0435\u0441\u0442 \u0441\u0435\u0431\u0435:</b>\\n',
        '<code>/broadcast_test &lt;b&gt;\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430&lt;/b&gt;</code>\\n',
        '\u0438\u043b\u0438 \u043e\u0442\u0432\u0435\u0442\u044c <code>/broadcast_test</code> \u043d\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435.\\n',
        '\\n',
        '<b>\u041e\u0441\u043d\u043e\u0432\u043d\u044b\u0435 \u0441\u0435\u0433\u043c\u0435\u043d\u0442\u044b</b>\\n',
        'all - \u0432\u0441\u0435 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438\\n',
        'bot - \u0432\u0435\u0442\u043a\u0430 \u043f\u043e\u043b\u0443\u0447\u0435\u043d\u0438\u044f \u0431\u043e\u0442\u0430\\n',
        'team - \u0432\u0435\u0442\u043a\u0430 \u043a\u043e\u043c\u0430\u043d\u0434\u044b\\n',
        'no_access - \u0434\u043e\u0441\u0442\u0443\u043f \u0435\u0449\u0435 \u043d\u0435 \u0432\u044b\u0434\u0430\u043d\\n',
        'access - \u0434\u043e\u0441\u0442\u0443\u043f \u0443\u0436\u0435 \u0432\u044b\u0434\u0430\u043d\\n',
        'need_id - \u0436\u0434\u0435\u043c Trader ID\\n',
        'need_topup - Trader ID \u0435\u0441\u0442\u044c, \u0436\u0434\u0435\u043c \u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435\\n',
        'bot_need_id / team_need_id - \u0436\u0434\u0435\u043c Trader ID \u043f\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0439 \u0432\u0435\u0442\u043a\u0435\\n',
        'bot_need_topup / team_need_topup - \u0436\u0434\u0435\u043c \u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435 \u043f\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e\u0439 \u0432\u0435\u0442\u043a\u0435\\n'
    ]
    lines.extend([
        f"Пользователей в базе: <b>{total_users}</b>\n",
        f"Без доступа: <b>{segment_counts['no_access']}</b>\n",
        f"Нужно ID: <b>{segment_counts['need_id']}</b>\n",
        f"Нужно пополнение: <b>{segment_counts['need_topup']}</b>",
    ])
    return "".join(lines)

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


def signal_pair_keyboard(market_mode: str, fast: bool) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    current_row: list[dict[str, str]] = []
    fast_token = "1" if fast else "0"
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    for pair in get_mvp_pair_options(normalized_market_mode):
        current_row.append(
            {
                "text": f"{pair.flag_1}{pair.flag_2} {pair.symbol}",
                "callback_data": signal_callback("pair", normalized_market_mode, pair.code, fast_token),
            }
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([{"text": "Back to markets", "callback_data": signal_callback("markets", fast_token)}])
    return {"inline_keyboard": rows}


def signal_expiry_keyboard(market_mode: str, pair_code: str, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    rows = [
        [
            {
                "text": f"{expiry}m",
                "callback_data": signal_callback("expiry", normalized_market_mode, pair_code, expiry, fast_token),
            }
            for expiry in MVP_EXPIRY_MINUTE_OPTIONS[:2]
        ],
        [
            {
                "text": f"{expiry}m",
                "callback_data": signal_callback("expiry", normalized_market_mode, pair_code, expiry, fast_token),
            }
            for expiry in MVP_EXPIRY_MINUTE_OPTIONS[2:]
        ],
        [{"text": "в¬…пёЏ РќР°Р·Р°Рґ Рє РїР°СЂР°Рј", "callback_data": signal_callback("back", fast_token)}],
    ]
    return {"inline_keyboard": rows}


def signal_expiry_keyboard(market_mode: str, pair_code: str, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    rows: list[list[dict[str, str]]] = []
    current_row: list[dict[str, str]] = []
    for expiry in MVP_EXPIRY_MINUTE_OPTIONS:
        current_row.append(
            {
                "text": f"{expiry}m",
                "callback_data": signal_callback("expiry", normalized_market_mode, pair_code, expiry, fast_token),
            }
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([{"text": "Back to pairs", "callback_data": signal_callback("back", normalized_market_mode, fast_token)}])
    return {"inline_keyboard": rows}


def signal_confirm_keyboard(preview_token: str, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    return {
        "inline_keyboard": [
            [
                {
                    "text": "вњ… РџРѕРґС‚РІРµСЂРґРёС‚СЊ РѕС‚РїСЂР°РІРєСѓ",
                    "callback_data": signal_callback("confirm", preview_token, fast_token),
                }
            ],
            [{"text": "в¬…пёЏ РќР°Р·Р°Рґ Рє РІС‹Р±РѕСЂСѓ РїР°СЂ", "callback_data": signal_callback("back", fast_token)}],
        ]
    }


def send_signal_pair_menu(client: httpx.Client, chat_id: int, *, fast: bool) -> None:
    mode_text = "Р±С‹СЃС‚СЂС‹Р№ С‚РµСЃС‚: СЃС‚Р°СЂС‚ С‡РµСЂРµР· 15 СЃРµРєСѓРЅРґ" if fast else "РѕР±С‹С‡РЅС‹Р№ СЂРµР¶РёРј: СЃС‚Р°СЂС‚ С‡РµСЂРµР· 60 РјРёРЅСѓС‚"
    send_message(
        client,
        chat_id,
        (
            "<b>MVP С‚РѕСЂРіРѕРІР°СЏ СЃРµСЃСЃРёСЏ</b>\n\n"
            f"Р РµР¶РёРј: <b>{mode_text}</b>\n"
            "Р’С‹Р±РµСЂРё РїР°СЂСѓ. РЎРїРёСЃРѕРє РІР·СЏС‚ РёР· РўР— РїРѕ Forex-РїР°СЂР°Рј. "
            "Р’ Devsbite Рё РІ РєР°РЅР°Р» РѕС‚РїСЂР°РІР»СЏРµРј Forex-СЃРёРјРІРѕР»."
        ),
        parse_mode="HTML",
        reply_markup=signal_pair_keyboard(fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_expiry_menu(client: httpx.Client, chat_id: int, pair_code: str, *, fast: bool) -> None:
    pair = get_mvp_pair_option(pair_code)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP С‚РѕСЂРіРѕРІР°СЏ СЃРµСЃСЃРёСЏ</b>\n\n"
            f"РџР°СЂР°: <b>{escape(pair.symbol)}</b>\n"
            "РўРµРїРµСЂСЊ РІС‹Р±РµСЂРё СЌРєСЃРїРёСЂР°С†РёСЋ РґР»СЏ РїСЂРѕРІРµСЂРєРё Devsbite."
        ),
        parse_mode="HTML",
        reply_markup=signal_expiry_keyboard(pair_code, fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_market_menu(client: httpx.Client, chat_id: int, *, fast: bool) -> None:
    mode_text = "fast test: start in 15 seconds" if fast else "normal mode: start in 60 minutes"
    send_message(
        client,
        chat_id,
        (
            "<b>MVP trading session</b>\n\n"
            f"Mode: <b>{mode_text}</b>\n"
            "Choose market mode from the РўР— list."
        ),
        parse_mode="HTML",
        reply_markup=signal_market_keyboard(fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_pair_menu(client: httpx.Client, chat_id: int, *, market_mode: str = "FOREX", fast: bool) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP trading session</b>\n\n"
            f"Market mode: <b>{normalized_market_mode}</b>\n"
            "Choose a pair from the whitelist."
        ),
        parse_mode="HTML",
        reply_markup=signal_pair_keyboard(normalized_market_mode, fast),
        disable_web_page_preview=True,
    ).raise_for_status()


def send_signal_expiry_menu(
    client: httpx.Client,
    chat_id: int,
    market_mode: str,
    pair_code: str,
    *,
    fast: bool,
) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    pair = get_mvp_pair_option(pair_code)
    send_message(
        client,
        chat_id,
        (
            "<b>MVP trading session</b>\n\n"
            f"Market mode: <b>{normalized_market_mode}</b>\n"
            f"Pair: <b>{escape(pair.symbol)}</b>\n"
            "Choose expiry for Devsbite preview."
        ),
        parse_mode="HTML",
        reply_markup=signal_expiry_keyboard(normalized_market_mode, pair_code, fast),
        disable_web_page_preview=True,
    ).raise_for_status()


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

    return (
        "<b>Devsbite preview</b>\n\n"
        f"Market mode: <b>{market_mode}</b>\n"
        f"Pair type: <b>{escape(pair.market_type)}</b>\n"
        f"Pair: <b>{escape(pair.symbol)}</b>\n"
        f"Expiry: <b>{preview['expiry_minutes']}m</b>\n"
        f"Entry price: <code>{price_text}</code>\n\n"
        f"API signal: <b>{api_signal}</b>\n"
        f"API confidence: <b>{api_confidence}%</b>\n"
        f"Payout: <b>{payout}%</b>\n"
        f"Channel direction: <b>{preview['direction']}</b>\n\n"
        f"Decision source: <code>{decision_source}</code>\n"
        f"Reason: <code>{decision_reason}</code>\n"
        f"TV / TD: <code>{tv_recommendation}</code> / <code>{td_recommendation}</code>\n\n"
        "If the data is suitable, confirm sending. Otherwise go back to pair selection."
    )


def signal_confirm_keyboard(preview_token: str, fast: bool) -> dict[str, Any]:
    fast_token = "1" if fast else "0"
    return {
        "inline_keyboard": [
            [
                {
                    "text": "вњ… Confirm sending",
                    "callback_data": signal_callback("confirm", preview_token, fast_token),
                }
            ],
            [{"text": "в¬…пёЏ Back to pair selection", "callback_data": signal_callback("preview_back", preview_token, fast_token)}],
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
) -> None:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    pair = get_mvp_pair_option(pair_code)
    if pair not in get_mvp_pair_options(normalized_market_mode):
        raise ValueError(f"Pair {pair.symbol} is not allowed for market mode {normalized_market_mode}")
    preview = preview_mvp_trading_signal(pair, expiry_minutes)
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
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return True

    with httpx.Client(timeout=30) as client:
        if not is_telegram_admin(user):
            if callback_id:
                answer_callback_query(client, callback_id, "РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РїСЂР°РІ").raise_for_status()
            print(f"telegram_admin_callback_denied telegram_id={user.get('id')} data={data}")
            return True

        callback_text = "РћРє"
        try:
            _, action, *parts = data.split(":")
            if action == "markets":
                fast = bool(parts and parts[0] == "1")
                send_signal_market_menu(client, chat_id, fast=fast)
            elif action == "back":
                if parts and parts[0] in MVP_MARKET_MODES:
                    market_mode = parts[0]
                    fast = len(parts) > 1 and parts[1] == "1"
                    send_signal_pair_menu(client, chat_id, market_mode=market_mode, fast=fast)
                else:
                    fast = bool(parts and parts[0] == "1")
                    send_signal_market_menu(client, chat_id, fast=fast)
            elif action == "market":
                market_mode = normalize_mvp_market_mode(parts[0])
                fast = len(parts) > 1 and parts[1] == "1"
                send_signal_pair_menu(client, chat_id, market_mode=market_mode, fast=fast)
            elif action == "pair":
                if parts and parts[0] in MVP_MARKET_MODES:
                    market_mode = normalize_mvp_market_mode(parts[0])
                    pair_code = parts[1]
                    fast = len(parts) > 2 and parts[2] == "1"
                else:
                    market_mode = "FOREX"
                    pair_code = parts[0]
                    fast = len(parts) > 1 and parts[1] == "1"
                send_signal_expiry_menu(client, chat_id, market_mode, pair_code, fast=fast)
            elif action == "expiry":
                if parts and parts[0] in MVP_MARKET_MODES:
                    market_mode = normalize_mvp_market_mode(parts[0])
                    pair_code = parts[1]
                    expiry_minutes = int(parts[2])
                    fast = len(parts) > 3 and parts[3] == "1"
                else:
                    market_mode = "FOREX"
                    pair_code = parts[0]
                    expiry_minutes = int(parts[1])
                    fast = len(parts) > 2 and parts[2] == "1"
                send_signal_preview(client, chat_id, market_mode, pair_code, expiry_minutes, fast=fast)
            elif action == "preview_back":
                preview_token = parts[0]
                fast = len(parts) > 1 and parts[1] == "1"
                preview = ADMIN_SIGNAL_PREVIEWS.get(preview_token)
                market_mode = preview.get("market_mode", "FOREX") if preview else "FOREX"
                send_signal_pair_menu(client, chat_id, market_mode=market_mode, fast=fast)
            elif action == "confirm":
                preview_token = parts[0]
                fast = len(parts) > 1 and parts[1] == "1"
                preview = ADMIN_SIGNAL_PREVIEWS.pop(preview_token, None)
                if preview is None:
                    send_admin_message(client, chat_id, "РџСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ СѓСЃС‚Р°СЂРµР». Р—Р°РїСѓСЃС‚Рё /signal_mvp Р·Р°РЅРѕРІРѕ.")
                    callback_text = "РџСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ СѓСЃС‚Р°СЂРµР»"
                    if callback_id:
                        answer_callback_query(client, callback_id, callback_text).raise_for_status()
                    return True
                start_at = datetime.utcnow() + timedelta(seconds=15) if fast else None
                session = create_mvp_trading_session(
                    db,
                    created_by_telegram_id=user.get("id"),
                    start_at=start_at,
                    pair=preview["pair"],
                    market_mode=preview.get("market_mode", "FOREX"),
                    expiry_minutes=preview["expiry_minutes"],
                    preview=preview,
                )
                send_admin_message(client, chat_id, format_mvp_session_summary(session))
                callback_text = "РЎРµСЃСЃРёСЏ СЃРѕР·РґР°РЅР°"
            else:
                callback_text = "РќРµРёР·РІРµСЃС‚РЅРѕРµ РґРµР№СЃС‚РІРёРµ"
        except (
            DevsbiteApiError,
            DevsbiteConfigError,
            DevsbiteRequestError,
            TradingMvpConfigError,
            ValueError,
        ) as error:
            callback_text = "РћС€РёР±РєР°"
            send_admin_message(client, chat_id, f"РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±СЂР°Р±РѕС‚Р°С‚СЊ MVP-СЃРёРіРЅР°Р»: <code>{escape(str(error))}</code>")

        if callback_id:
            answer_callback_query(client, callback_id, callback_text).raise_for_status()
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
            lines = ["<b>РЎРµРіРјРµРЅС‚С‹ СЂР°СЃСЃС‹Р»РєРё</b>"]
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

        if command_name == "/broadcast_test":
            reply_to_message = message.get("reply_to_message")
            if reply_to_message:
                sent, failed = broadcast_copy_message(client, [chat_id], chat_id, reply_to_message["message_id"])
            elif command_body.strip():
                sent, failed = broadcast_text(client, [chat_id], command_body.strip())
            else:
                send_admin_message(client, chat_id, "РћС‚РІРµС‚СЊ РєРѕРјР°РЅРґРѕР№ РЅР° СЃРѕРѕР±С‰РµРЅРёРµ РёР»Рё РґРѕР±Р°РІСЊ С‚РµРєСЃС‚ РїРѕСЃР»Рµ /broadcast_test.")
                return True

            send_admin_message(client, chat_id, f"РўРµСЃС‚РѕРІР°СЏ СЂР°СЃСЃС‹Р»РєР°: РѕС‚РїСЂР°РІР»РµРЅРѕ {sent}, РѕС€РёР±РѕРє {failed}.")
            return True

        if command_name == "/broadcast_segment":
            segment, _, segment_text = command_body.strip().partition(" ")
            if not segment:
                send_admin_message(client, chat_id, "РЈРєР°Р¶Рё СЃРµРіРјРµРЅС‚: /broadcast_segment need_id С‚РµРєСЃС‚")
                return True

            segment_target_chat_ids = get_broadcast_target_chat_ids(db, segment)
            reply_to_message = message.get("reply_to_message")
            if reply_to_message:
                sent, failed = broadcast_copy_message(client, segment_target_chat_ids, chat_id, reply_to_message["message_id"])
            elif segment_text.strip():
                sent, failed = broadcast_text(client, segment_target_chat_ids, segment_text.strip())
            else:
                send_admin_message(client, chat_id, "РћС‚РІРµС‚СЊ /broadcast_segment segment РЅР° СЃРѕРѕР±С‰РµРЅРёРµ РёР»Рё РґРѕР±Р°РІСЊ С‚РµРєСЃС‚ РїРѕСЃР»Рµ СЃРµРіРјРµРЅС‚Р°.")
                return True

            send_admin_message(
                client,
                chat_id,
                (
                    f"РЎРµРіРјРµРЅС‚РЅР°СЏ СЂР°СЃСЃС‹Р»РєР° Р·Р°РІРµСЂС€РµРЅР°.\n"
                    f"РЎРµРіРјРµРЅС‚: <b>{escape(segment)}</b>\n"
                    f"РћС‚РїСЂР°РІР»РµРЅРѕ: <b>{sent}</b>\n"
                    f"РћС€РёР±РѕРє: <b>{failed}</b>\n"
                    f"Р’СЃРµРіРѕ С†РµР»РµР№: <b>{len(segment_target_chat_ids)}</b>"
                ),
            )
            return True

        if command_name != "/broadcast":
            send_admin_message(client, chat_id, "РќРµРёР·РІРµСЃС‚РЅР°СЏ Р°РґРјРёРЅ-РєРѕРјР°РЅРґР°. РСЃРїРѕР»СЊР·СѓР№ /admin.")
            return True

        reply_to_message = message.get("reply_to_message")
        if reply_to_message:
            sent, failed = broadcast_copy_message(client, target_chat_ids, chat_id, reply_to_message["message_id"])
        elif command_body.strip():
            sent, failed = broadcast_text(client, target_chat_ids, command_body.strip())
        else:
            send_admin_message(client, chat_id, "РћС‚РІРµС‚СЊ /broadcast РЅР° СЃРѕРѕР±С‰РµРЅРёРµ РёР»Рё РЅР°РїРёС€Рё С‚РµРєСЃС‚ РїРѕСЃР»Рµ РєРѕРјР°РЅРґС‹.")
            return True

        send_admin_message(
            client,
            chat_id,
            f"Р Р°СЃСЃС‹Р»РєР° Р·Р°РІРµСЂС€РµРЅР°.\nРћС‚РїСЂР°РІР»РµРЅРѕ: <b>{sent}</b>\nРћС€РёР±РѕРє: <b>{failed}</b>\nР’СЃРµРіРѕ С†РµР»РµР№: <b>{len(target_chat_ids)}</b>",
        )
        return True
