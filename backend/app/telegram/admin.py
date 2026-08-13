from datetime import datetime, timedelta
from html import escape
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.funnel_session import FunnelSession
from app.models.telegram_user import TelegramUser as TelegramUserModel
from app.services.devsbite import DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError
from app.services.trading_mvp import TradingMvpConfigError, create_mvp_trading_session, format_mvp_session_summary
from app.telegram.client import copy_message, send_message


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


def send_admin_message(client: httpx.Client, chat_id: int, text: str) -> None:
    send_message(client, chat_id, text, parse_mode="HTML", disable_web_page_preview=True).raise_for_status()


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


def handle_admin_command_message(db: Session, user: dict[str, Any], chat_id: int, message: dict[str, Any], text: str) -> bool:
    if (
        not text.startswith("/admin")
        and not text.startswith("/broadcast")
        and not text.startswith("/segments")
        and not text.startswith("/signal_mvp")
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
            send_admin_message(
                client,
                chat_id,
                (
                    "<b>Админ-команды</b>\n\n"
                    "/admin - показать команды и число пользователей в базе\n"
                    "/segments - показать доступные сегменты и количество пользователей\n"
                    "/broadcast текст - отправить HTML-текст всем пользователям\n"
                    "/broadcast ответом на сообщение - скопировать это сообщение всем пользователям\n"
                    "/broadcast_segment segment текст - отправить HTML-текст по сегменту\n"
                    "/broadcast_segment segment ответом на сообщение - скопировать сообщение по сегменту\n"
                    "/broadcast_test текст - отправить тест только себе\n\n"
                    "<b>Торговые сессии MVP</b>\n"
                    "/signal_mvp - создать тестовую OTC-сессию по EUR/USD OTC и положить due jobs в БД\n\n"
                    "/signal_mvp now - создать такую же сессию со стартом через 15 секунд для быстрой проверки воркера\n\n"
                    "<b>Как отправлять</b>\n"
                    "<b>1. HTML-текст:</b>\n"
                    "<code>/broadcast &lt;b&gt;Заголовок&lt;/b&gt;\n"
                    "&lt;i&gt;Текст рассылки&lt;/i&gt;</code>\n"
                    "Бот отправит новый текст с parse_mode=HTML. Теги пользователь не увидит.\n\n"
                    "<b>2. Ответом на сообщение:</b>\n"
                    "Ответь командой <code>/broadcast</code> на любое сообщение в чате с ботом.\n"
                    "Бот скопирует это сообщение пользователям через copyMessage: сохраняются медиа, форматирование и premium emoji.\n\n"
                    "<b>Premium emoji:</b>\n"
                    "Если делаешь рассылку ответом на готовое сообщение, emoji сохраняются автоматически.\n"
                    "Если пишешь HTML вручную, premium emoji нужно вставлять так:\n"
                    "<code>&lt;tg-emoji emoji-id=\"123\"&gt;🔥&lt;/tg-emoji&gt;</code>\n"
                    "ID premium emoji можно получить через @userinfobot.\n\n"
                    "<b>3. По сегменту:</b>\n"
                    "<code>/broadcast_segment need_topup &lt;b&gt;Напоминание&lt;/b&gt;</code>\n"
                    "или ответь <code>/broadcast_segment need_topup</code> на готовое сообщение.\n\n"
                    "<b>4. Тест себе:</b>\n"
                    "<code>/broadcast_test &lt;b&gt;Проверка&lt;/b&gt;</code>\n"
                    "или ответь <code>/broadcast_test</code> на сообщение.\n\n"
                    "<b>Основные сегменты</b>\n"
                    "all - все пользователи\n"
                    "bot - ветка получения бота\n"
                    "team - ветка команды\n"
                    "no_access - доступ еще не выдан\n"
                    "access - доступ уже выдан\n"
                    "need_id - ждём Trader ID\n"
                    "need_topup - Trader ID есть, ждём пополнение\n"
                    "bot_need_id / team_need_id - ждём Trader ID по конкретной ветке\n"
                    "bot_need_topup / team_need_topup - ждём пополнение по конкретной ветке\n\n"
                    f"Пользователей в базе: <b>{len(target_chat_ids)}</b>\n"
                    f"Без доступа: <b>{segment_counts['no_access']}</b>\n"
                    f"Нужно ID: <b>{segment_counts['need_id']}</b>\n"
                    f"Нужно пополнение: <b>{segment_counts['need_topup']}</b>"
                ),
            )
            return True

        if command_name == "/segments":
            counts = broadcast_segment_counts(db)
            lines = ["<b>Сегменты рассылки</b>"]
            lines.extend(f"{segment}: <b>{count}</b>" for segment, count in counts.items())
            send_admin_message(client, chat_id, "\n".join(lines))
            return True

        if command_name == "/signal_mvp":
            try:
                start_at = datetime.utcnow() + timedelta(seconds=15) if command_body.strip() == "now" else None
                session = create_mvp_trading_session(db, created_by_telegram_id=user.get("id"), start_at=start_at)
            except (
                DevsbiteApiError,
                DevsbiteConfigError,
                DevsbiteRequestError,
                TradingMvpConfigError,
                ValueError,
            ) as error:
                send_admin_message(client, chat_id, f"Не удалось создать MVP-сессию: <code>{escape(str(error))}</code>")
                return True

            send_admin_message(client, chat_id, format_mvp_session_summary(session))
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
                send_admin_message(client, chat_id, "Укажи сегмент: /broadcast_segment need_id текст")
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
