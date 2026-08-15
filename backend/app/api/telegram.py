import re
from html import escape
from datetime import datetime, timedelta
import random
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models.funnel_session import FunnelSession
from app.models.telegram_user import TelegramUser as TelegramUserModel
from app.models.user_settings import UserSettings
from app.services.devsbite import (
    DevsbiteApiError,
    DevsbiteConfigError,
    DevsbiteRequestError,
    get_combined_analysis,
    get_pairs,
    get_quote,
)
from app.services.pocket_option import (
    PocketOptionApiError,
    PocketOptionConfigError,
    PocketOptionRequestError,
    get_user_info,
)
from app.telegram.client import (
    answer_callback_query,
    copy_message,
    delete_message,
    ensure_telegram_configured,
    send_message,
    send_photo,
    set_chat_menu_button,
)
from app.telegram.admin import handle_admin_callback_query, handle_admin_command_message
from app.telegram.templates import (
    API_TEST_TEXTS,
    FUNNEL_NODE_PHOTOS,
    FUNNEL_NODE_TEXTS,
    LEGACY_TEXT_FORMAT_TEXTS,
    PAIR_CATEGORIES,
    PAIRS_REQUEST_RE,
    QUOTE_CATEGORIES,
    QUOTE_COMMAND_RE,
    SIGNAL_REQUEST_RE,
    SUPPORTED_LANGUAGES,
    TRADER_ID_RE,
    TRADER_ID_TEXTS,
    bot_reminder_keyboard,
    funnel_node_keyboard,
    funnel_texts,
    normalize_funnel_language,
    normalize_language,
    parse_start_context,
    reminder_03_keyboard,
    user_display_name,
)

router = APIRouter()

BOT_REMINDER_SOURCE_MESSAGE_ID = 6
ID_FORMAT_SOURCE_MESSAGE_ID = 21
TOPUP_SOURCE_MESSAGE_ID = 26
TOPUP_LOW_SOURCE_MESSAGE_ID = 29
TOPUP_NOT_FOUND_SOURCE_MESSAGE_ID = 32
BOT_SUCCESS_SOURCE_MESSAGE_ID = 35
BOT_INTRO_REMINDER_KIND = "BOT-01"
BOT_STEP_REMINDER_KIND = "BOT-STEP-01"
ID_REMINDER_KIND = "ID-01"
ID_FORMAT_REMINDER_KIND = "ID-FORMAT"
ID_NOT_FOUND_REMINDER_KIND = "ID-NOT-FOUND"
TOPUP_REMINDER_KIND = "TOPUP-01"
TOPUP_LOW_REMINDER_KIND = "TOPUP-LOW"
TOPUP_NOT_FOUND_REMINDER_KIND = "TOPUP-NOT-FOUND"
REMINDER_03_TOPUP_LOW_KIND = "REMINDER-03:TOPUP-LOW"
REMINDER_03_TOPUP_NOT_FOUND_KIND = "REMINDER-03:TOPUP-NOT-FOUND"
TRADER_ID_EXPECTED_REMINDER_KINDS = {
    BOT_STEP_REMINDER_KIND,
    ID_REMINDER_KIND,
    ID_FORMAT_REMINDER_KIND,
    ID_NOT_FOUND_REMINDER_KIND,
}
MIN_TOPUP_AMOUNT_USD = 20.0
BOT_REMINDER_DELAYS_SECONDS = (
    (5 * 60, 15 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
)
BOT_STEP_REMINDER_DELAYS_SECONDS = (
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
ID_REMINDER_DELAYS_SECONDS = (
    (5 * 60, 15 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
ID_FORMAT_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
ID_NOT_FOUND_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
TOPUP_LOW_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
TOPUP_NOT_FOUND_REMINDER_DELAYS_SECONDS = ((15 * 60, 15 * 60),)
REMINDER_03_DELAYS_SECONDS = (
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
TOPUP_REMINDER_DELAYS_SECONDS = (
    (5 * 60, 15 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (30 * 60, 60 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (60 * 60, 120 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
    (120 * 60, 180 * 60),
)
REMINDER_DELAYS_BY_KIND = {
    BOT_INTRO_REMINDER_KIND: BOT_REMINDER_DELAYS_SECONDS,
    BOT_STEP_REMINDER_KIND: BOT_STEP_REMINDER_DELAYS_SECONDS,
    ID_REMINDER_KIND: ID_REMINDER_DELAYS_SECONDS,
    ID_FORMAT_REMINDER_KIND: ID_FORMAT_REMINDER_DELAYS_SECONDS,
    ID_NOT_FOUND_REMINDER_KIND: ID_NOT_FOUND_REMINDER_DELAYS_SECONDS,
    TOPUP_REMINDER_KIND: TOPUP_REMINDER_DELAYS_SECONDS,
    TOPUP_LOW_REMINDER_KIND: TOPUP_LOW_REMINDER_DELAYS_SECONDS,
    TOPUP_NOT_FOUND_REMINDER_KIND: TOPUP_NOT_FOUND_REMINDER_DELAYS_SECONDS,
    REMINDER_03_TOPUP_LOW_KIND: REMINDER_03_DELAYS_SECONDS,
    REMINDER_03_TOPUP_NOT_FOUND_KIND: REMINDER_03_DELAYS_SECONDS,
}
REMINDER_WORKER_POLL_SECONDS = 15
REMINDER_WORKER_BATCH_SIZE = 20
_reminder_worker_lock = threading.Lock()
_reminder_worker_started = False


@dataclass(frozen=True)
class FunnelDelivery:
    text_message_id: int | None = None
    media_message_id: int | None = None


def upsert_telegram_user(db: Session, user: dict[str, Any]) -> TelegramUserModel | None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return None

    telegram_user = db.query(TelegramUserModel).filter(TelegramUserModel.telegram_id == telegram_id).first()
    if telegram_user is None:
        telegram_user = TelegramUserModel(
            telegram_id=telegram_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
        )
        db.add(telegram_user)
    else:
        telegram_user.username = user.get("username")
        telegram_user.first_name = user.get("first_name")

    return telegram_user


def get_or_create_user_settings(db: Session, telegram_id: int) -> UserSettings:
    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is not None:
        return settings_row

    settings_row = UserSettings(telegram_id=telegram_id)
    db.add(settings_row)
    return settings_row


def get_or_create_funnel_session(db: Session, telegram_id: int) -> FunnelSession:
    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    if funnel_session is not None:
        return funnel_session

    funnel_session = FunnelSession(telegram_id=telegram_id)
    db.add(funnel_session)
    return funnel_session


def save_start_context(db: Session, user: dict[str, Any], language: str, funnel_route: str) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    upsert_telegram_user(db, user)
    settings_row = get_or_create_user_settings(db, telegram_id)
    funnel_session = get_or_create_funnel_session(db, telegram_id)
    settings_row.language = language
    funnel_session.route = funnel_route

    db.commit()


def has_funnel_access(db: Session, user: dict[str, Any]) -> bool:
    telegram_id = user.get("id")
    if telegram_id is None:
        return False

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    return bool(funnel_session and funnel_session.access_granted)


def grant_funnel_access(db: Session, user: dict[str, Any]) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    upsert_telegram_user(db, user)
    get_or_create_user_settings(db, telegram_id)
    funnel_session = get_or_create_funnel_session(db, telegram_id)
    funnel_session.access_granted = True
    funnel_session.reminder_kind = ""
    funnel_session.reminder_stage = 0
    funnel_session.reminder_token = ""
    funnel_session.reminder_chat_id = None
    funnel_session.reminder_due_at = None
    funnel_session.last_reminder_message_id = None
    funnel_session.last_media_message_id = None

    db.commit()


def should_show_mini_app_menu(db: Session, user: dict[str, Any]) -> bool:
    return has_funnel_access(db, user)


def is_test_access_code(text: str) -> bool:
    access_code = settings.telegram_funnel_test_access_code.strip()
    return bool(access_code) and text.strip().casefold() == access_code.casefold()


def set_chat_mini_app_menu(client: httpx.Client, chat_id: int, language: str, *, enabled: bool) -> None:
    menu_button: dict[str, Any]
    if enabled:
        menu_button = {
            "type": "web_app",
            "text": funnel_texts(language)["open_bot"],
            "web_app": {"url": settings.telegram_webapp_url},
        }
    else:
        menu_button = {"type": "commands"}

    try:
        set_chat_menu_button(client, chat_id, menu_button).raise_for_status()
    except Exception as error:
        print(f"telegram_menu_button_update_failed chat_id={chat_id} enabled={enabled} detail={telegram_error_detail(error)}")


def copy_source_message(
    client: httpx.Client,
    chat_id: int,
    source_message_id: int,
    language: str,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> int | None:
    if not settings.telegram_source_channel_id:
        print("telegram_source_copy skipped: TELEGRAM_SOURCE_CHANNEL_ID is empty")
        return None

    response = copy_message(
        client,
        chat_id,
        settings.telegram_source_channel_id,
        source_message_id,
        reply_markup=reply_markup,
    )
    response.raise_for_status()
    result = response.json().get("result") or {}
    message_id = result.get("message_id")
    print(f"telegram_copy_source source_message_id={source_message_id} chat_id={chat_id} copied_message_id={message_id}")
    return message_id if isinstance(message_id, int) else None


def delete_chat_message(client: httpx.Client, chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return

    try:
        delete_message(client, chat_id, message_id).raise_for_status()
    except Exception as error:
        print(f"telegram_delete_message_failed chat_id={chat_id} message_id={message_id} detail={telegram_error_detail(error)}")


def delete_funnel_delivery(client: httpx.Client, chat_id: int, text_message_id: int | None, media_message_id: int | None) -> None:
    delete_chat_message(client, chat_id, media_message_id)
    delete_chat_message(client, chat_id, text_message_id)


def get_reminder_delay_seconds(kind: str, stage: int) -> int | None:
    reminder_delays = REMINDER_DELAYS_BY_KIND.get(kind)
    if reminder_delays is None or stage < 1 or stage > len(reminder_delays):
        return None

    delay_min, delay_max = reminder_delays[stage - 1]
    return random.randint(delay_min, delay_max)


def schedule_bot_reminder_row(funnel_session: FunnelSession, chat_id: int, stage: int, kind: str) -> bool:
    delay_seconds = get_reminder_delay_seconds(kind, stage)
    if delay_seconds is None:
        return False

    funnel_session.reminder_chat_id = chat_id
    funnel_session.reminder_due_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
    print(
        "telegram_bot_reminder_scheduled "
        f"telegram_id={funnel_session.telegram_id} kind={kind} stage={stage} delay_seconds={delay_seconds}"
    )
    return True


def start_bot_reminder_flow(
    db: Session,
    user: dict[str, Any],
    chat_id: int,
    language: str,
    kind: str = BOT_INTRO_REMINDER_KIND,
    initial_message_id: int | None = None,
    initial_media_message_id: int | None = None,
) -> None:
    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return

    if kind not in REMINDER_DELAYS_BY_KIND:
        return

    get_or_create_user_settings(db, telegram_id)
    funnel_session = get_or_create_funnel_session(db, telegram_id)
    if funnel_session.access_granted:
        return

    token = uuid.uuid4().hex
    funnel_session.reminder_kind = kind
    funnel_session.reminder_stage = 1
    funnel_session.reminder_token = token
    funnel_session.last_reminder_message_id = initial_message_id
    funnel_session.last_media_message_id = initial_media_message_id
    if not schedule_bot_reminder_row(funnel_session, chat_id, stage=1, kind=kind):
        return
    db.commit()


def cancel_bot_reminder_flow(
    db: Session,
    user: dict[str, Any],
    client: httpx.Client | None = None,
    chat_id: int | None = None,
    delete_last_delivery: bool = False,
) -> None:
    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    if funnel_session is None:
        return

    last_message_id = funnel_session.last_reminder_message_id
    last_media_message_id = funnel_session.last_media_message_id
    funnel_session.reminder_kind = ""
    funnel_session.reminder_stage = 0
    funnel_session.reminder_token = ""
    funnel_session.reminder_chat_id = None
    funnel_session.reminder_due_at = None
    funnel_session.last_reminder_message_id = None
    funnel_session.last_media_message_id = None
    db.commit()

    if delete_last_delivery and client is not None and chat_id is not None:
        delete_funnel_delivery(client, chat_id, last_message_id, last_media_message_id)


def run_bot_reminder_stage(chat_id: int, telegram_id: int, token: str, language: str, stage: int, kind: str) -> None:
    db = SessionLocal()
    try:
        funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
        if funnel_session is None:
            return
        if (
            funnel_session.reminder_kind != kind
            or funnel_session.reminder_token != token
            or funnel_session.reminder_stage != stage
        ):
            return
        if funnel_session.access_granted:
            cancel_bot_reminder_flow(db, {"id": telegram_id})
            return

        reminder_delays = REMINDER_DELAYS_BY_KIND.get(kind)
        if reminder_delays is None:
            cancel_bot_reminder_flow(db, {"id": telegram_id})
            return

        telegram_user = db.query(TelegramUserModel).filter(TelegramUserModel.telegram_id == telegram_id).first()
        user = {
            "id": telegram_id,
            "username": telegram_user.username if telegram_user else None,
            "first_name": telegram_user.first_name if telegram_user else None,
        }
        with httpx.Client(timeout=20) as client:
            delete_funnel_delivery(
                client,
                chat_id,
                funnel_session.last_reminder_message_id,
                funnel_session.last_media_message_id,
            )

            if kind == BOT_INTRO_REMINDER_KIND and stage < len(reminder_delays):
                message_id = copy_source_message(
                    client=client,
                    chat_id=chat_id,
                    source_message_id=BOT_REMINDER_SOURCE_MESSAGE_ID,
                    language=language,
                    reply_markup=bot_reminder_keyboard(language, funnel_session.route),
                )
                funnel_session.last_reminder_message_id = message_id
                funnel_session.last_media_message_id = None
                funnel_session.reminder_stage = stage + 1
                schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                db.commit()
                return

            if kind == BOT_INTRO_REMINDER_KIND:
                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                step_node_code = "TEAM-STEP-01" if funnel_session.route == "TEAM" else "BOT-STEP-01"
                delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code=step_node_code, language=language, user=user)
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=BOT_STEP_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return

            if kind == ID_REMINDER_KIND:
                delivery = copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code="ID-01",
                    language=language,
                    user=user,
                )
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                return

            if kind in {ID_FORMAT_REMINDER_KIND, ID_NOT_FOUND_REMINDER_KIND}:
                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                delivery = copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code="ID-01",
                    language=language,
                    user=user,
                )
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=ID_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return

            if kind == TOPUP_REMINDER_KIND:
                delivery = send_topup_step(client=client, chat_id=chat_id, language=language, user=user)
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                return

            if kind in {TOPUP_LOW_REMINDER_KIND, TOPUP_NOT_FOUND_REMINDER_KIND}:
                target_node_code = "TOPUP-LOW" if kind == TOPUP_LOW_REMINDER_KIND else "TOPUP-NOT-FOUND"
                reminder_03_kind = (
                    REMINDER_03_TOPUP_LOW_KIND
                    if target_node_code == "TOPUP-LOW"
                    else REMINDER_03_TOPUP_NOT_FOUND_KIND
                )
                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                delivery = send_reminder_03(
                    client=client,
                    chat_id=chat_id,
                    language=language,
                    target_node_code=target_node_code,
                    user=user,
                )
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=reminder_03_kind,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return

            if kind in {REMINDER_03_TOPUP_LOW_KIND, REMINDER_03_TOPUP_NOT_FOUND_KIND}:
                target_node_code = "TOPUP-LOW" if kind == REMINDER_03_TOPUP_LOW_KIND else "TOPUP-NOT-FOUND"
                delivery = send_reminder_03(
                    client=client,
                    chat_id=chat_id,
                    language=language,
                    target_node_code=target_node_code,
                    user=user,
                )
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                funnel_session.last_reminder_message_id = None
                funnel_session.last_media_message_id = None
                db.commit()
                return

            if kind == BOT_STEP_REMINDER_KIND:
                step_node_code = "TEAM-STEP-01" if funnel_session.route == "TEAM" else "BOT-STEP-01"
                delivery = copy_funnel_node(
                    client=client,
                    chat_id=chat_id,
                    node_code=step_node_code,
                    language=language,
                    user=user,
                )
                funnel_session.last_reminder_message_id = delivery.text_message_id
                funnel_session.last_media_message_id = delivery.media_message_id
                if stage < len(reminder_delays):
                    funnel_session.reminder_stage = stage + 1
                    schedule_bot_reminder_row(funnel_session, chat_id, stage=stage + 1, kind=kind)
                    db.commit()
                    return

                funnel_session.reminder_kind = ""
                funnel_session.reminder_stage = 0
                funnel_session.reminder_token = ""
                funnel_session.reminder_chat_id = None
                funnel_session.reminder_due_at = None
                db.commit()
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=ID_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
    except Exception as error:
        print(f"telegram_bot_reminder_failed telegram_id={telegram_id} kind={kind} stage={stage} detail={telegram_error_detail(error)}")
    finally:
        db.close()


def process_due_funnel_reminders() -> None:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        due_rows = (
            db.query(FunnelSession)
            .filter(
                FunnelSession.reminder_kind != "",
                FunnelSession.reminder_stage > 0,
                FunnelSession.reminder_token != "",
                FunnelSession.access_granted.is_(False),
                FunnelSession.reminder_chat_id.isnot(None),
                FunnelSession.reminder_due_at.isnot(None),
                FunnelSession.reminder_due_at <= now,
            )
            .order_by(FunnelSession.reminder_due_at.asc())
            .limit(REMINDER_WORKER_BATCH_SIZE)
            .all()
        )
        jobs = [
            {
                "chat_id": row.reminder_chat_id,
                "telegram_id": row.telegram_id,
                "token": row.reminder_token,
                "language": normalize_funnel_language(
                    (
                        db.query(UserSettings.language)
                        .filter(UserSettings.telegram_id == row.telegram_id)
                        .scalar()
                    )
                ),
                "stage": row.reminder_stage,
                "kind": row.reminder_kind,
            }
            for row in due_rows
            if row.reminder_chat_id is not None
        ]
    finally:
        db.close()

    for job in jobs:
        run_bot_reminder_stage(
            chat_id=int(job["chat_id"]),
            telegram_id=int(job["telegram_id"]),
            token=str(job["token"]),
            language=str(job["language"]),
            stage=int(job["stage"]),
            kind=str(job["kind"]),
        )


def run_funnel_reminder_worker() -> None:
    print("telegram_funnel_reminder_worker_started")
    while True:
        try:
            process_due_funnel_reminders()
        except Exception as error:
            print(f"telegram_funnel_reminder_worker_failed detail={telegram_error_detail(error)}")
        time.sleep(REMINDER_WORKER_POLL_SECONDS)


def start_funnel_reminder_worker() -> None:
    global _reminder_worker_started

    with _reminder_worker_lock:
        if _reminder_worker_started:
            return

        worker = threading.Thread(target=run_funnel_reminder_worker, daemon=True)
        worker.start()
        _reminder_worker_started = True


def send_topup_step(client: httpx.Client, chat_id: int, language: str, user: dict[str, Any] | None = None) -> FunnelDelivery:
    message_id = copy_source_message(
        client=client,
        chat_id=chat_id,
        source_message_id=TOPUP_SOURCE_MESSAGE_ID,
        language=language,
        reply_markup=funnel_node_keyboard("TOPUP-01", language),
    )
    if message_id is not None:
        return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code="TOPUP-01", language=language, user=user)


def send_topup_low(client: httpx.Client, chat_id: int, language: str, user: dict[str, Any] | None = None) -> FunnelDelivery:
    message_id = copy_source_message(
        client=client,
        chat_id=chat_id,
        source_message_id=TOPUP_LOW_SOURCE_MESSAGE_ID,
        language=language,
        reply_markup=funnel_node_keyboard("TOPUP-LOW", language),
    )
    if message_id is not None:
        return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code="TOPUP-LOW", language=language, user=user)


def send_topup_not_found(client: httpx.Client, chat_id: int, language: str, user: dict[str, Any] | None = None) -> FunnelDelivery:
    message_id = copy_source_message(
        client=client,
        chat_id=chat_id,
        source_message_id=TOPUP_NOT_FOUND_SOURCE_MESSAGE_ID,
        language=language,
        reply_markup=funnel_node_keyboard("TOPUP-NOT-FOUND", language),
    )
    if message_id is not None:
        return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code="TOPUP-NOT-FOUND", language=language, user=user)


def send_reminder_03(
    client: httpx.Client,
    chat_id: int,
    language: str,
    target_node_code: str,
    user: dict[str, Any] | None = None,
) -> FunnelDelivery:
    return copy_funnel_node(
        client=client,
        chat_id=chat_id,
        node_code="REMINDER-03",
        language=language,
        user=user,
        reply_markup_override=reminder_03_keyboard(language, target_node_code),
    )


def send_funnel_success(
    client: httpx.Client,
    chat_id: int,
    language: str,
    node_code: str,
    user: dict[str, Any] | None = None,
) -> FunnelDelivery:
    if node_code == "BOT-SUCCESS":
        message_id = copy_source_message(
            client=client,
            chat_id=chat_id,
            source_message_id=BOT_SUCCESS_SOURCE_MESSAGE_ID,
            language=language,
            reply_markup=funnel_node_keyboard("BOT-SUCCESS", language),
        )
        if message_id is not None:
            return FunnelDelivery(text_message_id=message_id)

    return copy_funnel_node(client=client, chat_id=chat_id, node_code=node_code, language=language, user=user)


def copy_funnel_node(
    client: httpx.Client,
    chat_id: int,
    node_code: str,
    language: str,
    user: dict[str, Any] | None = None,
    reply_markup_override: dict[str, Any] | None = None,
) -> FunnelDelivery:
    text_by_language = FUNNEL_NODE_TEXTS.get(node_code)
    if text_by_language is None:
        raise HTTPException(status_code=500, detail=f"Funnel node text is not configured: {node_code}")

    text = text_by_language.get(normalize_funnel_language(language), text_by_language["en"])
    text = (
        text.replace("{\u0438\u043c\u044f}", "{name}")
        .replace("{name}", user_display_name(user, language))
        .replace("{team_total_income}", str(random.randint(10000, 100000)))
        .replace("{paradox_income}", str(random.randint(5000, 15000)))
    )
    photo_path = FUNNEL_NODE_PHOTOS.get(node_code)
    media_message_id: int | None = None
    if photo_path is not None and photo_path.exists():
        photo_response = send_photo(client, chat_id, photo_path)
        photo_response.raise_for_status()
        photo_result = photo_response.json().get("result") or {}
        photo_message_id = photo_result.get("message_id")
        media_message_id = photo_message_id if isinstance(photo_message_id, int) else None

    reply_markup = reply_markup_override if reply_markup_override is not None else funnel_node_keyboard(node_code, language)

    response = send_message(client, chat_id, text, parse_mode="HTML", reply_markup=reply_markup)
    response.raise_for_status()
    result = response.json().get("result") or {}
    message_id = result.get("message_id")
    text_message_id = message_id if isinstance(message_id, int) else None
    print(
        f"telegram_send_node node={node_code} chat_id={chat_id} "
        f"message_id={text_message_id} media_message_id={media_message_id}"
    )
    return FunnelDelivery(text_message_id=text_message_id, media_message_id=media_message_id)


def get_saved_language(db: Session, user: dict[str, Any]) -> str | None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return None

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is None or settings_row.language not in SUPPORTED_LANGUAGES:
        return None

    return settings_row.language


def get_saved_context(db: Session, user: dict[str, Any]) -> tuple[str | None, str | None]:
    telegram_id = user.get("id")
    if telegram_id is None:
        return None, None

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()

    language = settings_row.language if settings_row and settings_row.language in SUPPORTED_LANGUAGES else None
    funnel_route = funnel_session.route if funnel_session and funnel_session.route in {"BOT", "TEAM"} else None
    return funnel_route, language


def send_html_message(client: httpx.Client, chat_id: int, text: str) -> None:
    send_message(client, chat_id, text, parse_mode="HTML").raise_for_status()


def telegram_error_detail(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.text
    if isinstance(error, HTTPException):
        return str(error.detail)
    return repr(error)


def send_funnel_delivery_error(client: httpx.Client, chat_id: int, node_code: str, error: Exception) -> None:
    detail = telegram_error_detail(error)
    print(f"telegram_send_node_failed node={node_code} detail={detail}")
    send_html_message(
        client,
        chat_id,
        (
            "\u26a0\ufe0f <b>\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0443\u0437\u0435\u043b "
            f"{escape(node_code)}</b>\n\n"
            "\u041f\u0440\u043e\u0432\u0435\u0440\u044c:\n"
            "\u2022 TELEGRAM_BOT_TOKEN\n"
            "\u2022 TELEGRAM_WEBAPP_URL\n"
            "\u2022 \u0432\u0430\u043b\u0438\u0434\u043d\u043e\u0441\u0442\u044c inline-\u043a\u043d\u043e\u043f\u043e\u043a \u0438 URL \u0432 env\n\n"
            f"<code>{escape(detail[:700])}</code>"
        ),
    )


def log_telegram_media_ids(message: dict[str, Any]) -> None:
    sticker = message.get("sticker")
    if isinstance(sticker, dict):
        print(
            "telegram_sticker "
            f"emoji={sticker.get('emoji')} "
            f"file_id={sticker.get('file_id')} "
            f"custom_emoji_id={sticker.get('custom_emoji_id')}"
        )

    entities = []
    for key in ("entities", "caption_entities"):
        value = message.get(key)
        if isinstance(value, list):
            entities.extend(value)

    custom_emoji_ids = [
        entity.get("custom_emoji_id")
        for entity in entities
        if isinstance(entity, dict) and entity.get("type") == "custom_emoji" and entity.get("custom_emoji_id")
    ]
    if custom_emoji_ids:
        print(f"telegram_custom_emoji_ids={custom_emoji_ids}")


def utf16_slice(text: str, offset: int, length: int) -> str:
    raw = text.encode("utf-16-le")
    start = offset * 2
    end = (offset + length) * 2
    try:
        return raw[start:end].decode("utf-16-le")
    except UnicodeDecodeError:
        return text[offset : offset + length]


def custom_emoji_report(message: dict[str, Any]) -> str | None:
    rows: list[tuple[str, str]] = []

    for text_key, entities_key in (("text", "entities"), ("caption", "caption_entities")):
        text = message.get(text_key)
        entities = message.get(entities_key)
        if not isinstance(text, str) or not isinstance(entities, list):
            continue

        for entity in entities:
            if not isinstance(entity, dict) or entity.get("type") != "custom_emoji":
                continue
            custom_emoji_id = entity.get("custom_emoji_id")
            offset = entity.get("offset")
            length = entity.get("length")
            if not custom_emoji_id or not isinstance(offset, int) or not isinstance(length, int):
                continue

            emoji = utf16_slice(text, offset, length) or "?"
            rows.append((emoji, str(custom_emoji_id)))

    sticker = message.get("sticker")
    if isinstance(sticker, dict) and sticker.get("custom_emoji_id"):
        rows.append((str(sticker.get("emoji") or "?"), str(sticker["custom_emoji_id"])))

    if not rows:
        return None

    unique_rows = list(dict.fromkeys(rows))
    all_ids = "\n".join(custom_emoji_id for _, custom_emoji_id in unique_rows)
    lines = [
        f"\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b premium emoji: <b>{len(unique_rows)}</b>",
        "",
        "<b>\u0412\u0441\u0435 custom_emoji_id:</b>",
        f"<code>{escape(all_ids)}</code>",
    ]

    for index, (emoji, custom_emoji_id) in enumerate(unique_rows, start=1):
        html = f'<tg-emoji emoji-id="{custom_emoji_id}">{emoji}</tg-emoji>'
        markdown = f"![{emoji}](tg://emoji?id={custom_emoji_id})"
        lines.extend(
            [
                "",
                f"<b>{index}. {escape(emoji)}</b>",
                f"custom_emoji_id: <code>{escape(custom_emoji_id)}</code>",
                "HTML:",
                f"<code>{escape(html)}</code>",
                "Markdown:",
                f"<code>{escape(markdown)}</code>",
            ]
        )

    return "\n".join(lines)


def handle_custom_emoji_id_message(client: httpx.Client, chat_id: int, message: dict[str, Any]) -> bool:
    command_text = message.get("text") or message.get("caption") or ""
    if not isinstance(command_text, str) or not command_text.strip().lower().startswith(("/emoji_ids", "/emoji")):
        return False

    report = custom_emoji_report(message)
    if report is None:
        return False

    send_message(client, chat_id, report, parse_mode="HTML", disable_web_page_preview=True).raise_for_status()
    return True


def parse_pairs_request(text: str) -> tuple[str, str | None, int] | None:
    match = PAIRS_REQUEST_RE.match(text)
    if match is None:
        return None

    market = match.group(1).lower()
    category = match.group(2).lower() if match.group(2) else None
    min_payout = int(match.group(3) or 80)
    if market in PAIR_CATEGORIES:
        category = market
        market = "otc"
    return market, category, min(max(min_payout, 0), 100)


def normalize_quote_symbol(symbol: str) -> str:
    normalized = re.sub(r"\s+", " ", symbol.strip())
    if re.match(r"^[a-z]{3}/?[a-z]{3}(?:\s+otc)?$", normalized, re.IGNORECASE):
        return normalized.upper()
    return normalized


def infer_quote_category(symbol: str) -> str:
    return "otc" if " OTC" in symbol.upper() else "forex"


def parse_quote_request(text: str) -> tuple[str, str, int | None] | None:
    match = QUOTE_COMMAND_RE.match(text)
    if match is None:
        return None

    tokens = match.group(1).split()
    if not tokens:
        return None

    history_seconds: int | None = None
    if tokens[-1].isdigit():
        history_seconds = max(1, min(int(tokens.pop()), 3600))

    category = tokens[0].lower()
    if category in QUOTE_CATEGORIES:
        tokens.pop(0)
    else:
        category = infer_quote_category(" ".join(tokens))

    symbol = normalize_quote_symbol(" ".join(tokens))
    if not symbol:
        return None

    return category, symbol, history_seconds


def extract_payload_items(payload: dict[str, Any]) -> list[Any]:
    for key in ("pairs", "assets", "items", "data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested_items = extract_payload_items(value)
            if nested_items:
                return nested_items
    return []


def extract_payload_object(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("quote", "data", "result", "item"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def scalar_text(value: Any, fallback: str) -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def first_existing(payload: dict[str, Any], keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return str(payload[key])
    return fallback


def format_pair_item(item: Any, index: int, texts: dict[str, str]) -> str:
    if isinstance(item, dict):
        symbol = first_existing(item, ("symbol", "name", "pair", "resolved_symbol"), texts["unknown"])
        payout = first_existing(item, ("payout", "profit", "percent", "return"), "")
        status = first_existing(item, ("market_status", "status", "state"), "")

        details = []
        if payout:
            details.append(f'{texts["payout"]}: {escape(payout)}')
        if status:
            details.append(escape(status))

        suffix = f" В· {' В· '.join(details)}" if details else ""
        return f"{index}. <b>{escape(symbol)}</b>{suffix}"

    return f"{index}. <b>{escape(str(item))}</b>"


def format_pair_item_clean(item: Any, index: int, texts: dict[str, str]) -> str:
    if isinstance(item, dict):
        symbol = first_existing(item, ("symbol", "name", "pair", "resolved_symbol"), texts["unknown"])
        payout = first_existing(item, ("payout", "profit", "percent", "return"), "")
        status = first_existing(item, ("market_status", "status", "state"), "")

        details = []
        if payout:
            details.append(f'{texts["payout"]}: {escape(payout)}')
        if status:
            details.append(escape(status))

        suffix = f" - {' - '.join(details)}" if details else ""
        return f"{index}. <b>{escape(symbol)}</b>{suffix}"

    return f"{index}. <b>{escape(str(item))}</b>"


def format_pairs_response(
    language: str,
    market: str,
    category: str | None,
    min_payout: int,
    payload: dict[str, Any],
) -> str:
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    items = extract_payload_items(payload)
    count = payload.get("count")
    total = count if isinstance(count, int) else len(items)
    shown_items = items[:15]

    lines = [
        texts["pairs_title"],
        "",
        f'{texts["market"]}: <b>{escape(market.upper())}</b>',
    ]
    if category:
        lines.append(f'{texts["category"]}: <b>{escape(category)}</b>')
    lines.extend(
        [
            f'{texts["min_payout"]}: <b>{min_payout}%</b>',
            f'{texts["available"]}: <b>{escape(str(total))}</b>',
            f'{texts["shown"]}: <b>{len(shown_items)}</b>',
            "",
        ]
    )

    if not shown_items:
        lines.append(texts["empty"])
        return "\n".join(lines)

    lines.append("<blockquote>")
    lines.extend(format_pair_item_clean(item, index, texts) for index, item in enumerate(shown_items, start=1))
    lines.append("</blockquote>")
    return "\n".join(lines)


def format_quote_response(language: str, category: str, symbol: str, payload: dict[str, Any]) -> str:
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    quote = extract_payload_object(payload)
    price = first_existing(quote, ("price", "bid", "ask", "last", "value", "close"), texts["unknown"])
    status = first_existing(quote, ("market_status", "status", "state"), texts["unknown"])
    source = first_existing(quote, ("source", "provider"), texts["unknown"])
    fetched_at = first_existing(quote, ("fetched_at", "time", "timestamp", "updated_at"), texts["unknown"])
    message = scalar_text(quote.get("message") or payload.get("message"), "")

    lines = [
        texts["quote_title"],
        "",
        f'{texts["category"]}: <b>{escape(category)}</b>',
        f'{texts["symbol"]}: <b>{escape(symbol)}</b>',
        f'{texts["price"]}: <code>{escape(price)}</code>',
        f'{texts["status"]}: <b>{escape(status)}</b>',
        f'{texts["source"]}: <code>{escape(source)}</code>',
        f'{texts["fetched_at"]}: <code>{escape(fetched_at)}</code>',
    ]

    if message:
        lines.extend(["", f'{texts["message"]}: {escape(message)}'])

    return "\n".join(lines)


def parse_money_amount(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def get_topup_amount(payload: dict[str, Any]) -> float | None:
    total_deposits = parse_money_amount(payload.get("total_deposits"))
    if total_deposits is not None:
        return total_deposits

    return parse_money_amount(payload.get("ftd_amount"))


def parse_signal_request(text: str) -> tuple[str, int] | None:
    match = SIGNAL_REQUEST_RE.match(text)
    if match is None:
        return None

    symbol = match.group(1).strip().upper()
    expiry_min = int(match.group(2))
    if expiry_min < 1 or expiry_min > 60:
        raise ValueError("invalid expiry")

    if " OTC" not in symbol:
        symbol = symbol.replace("/", "")

    symbol = re.sub(r"\s+", " ", symbol)
    return symbol, expiry_min


def format_signal_response(language: str, symbol: str, expiry_min: int, payload: dict[str, Any]) -> str:
    texts = SIGNAL_TEXTS.get(language, SIGNAL_TEXTS["en"])
    direction = payload.get("signal") or payload.get("direction") or texts["unknown"]
    confidence = payload.get("confidence", texts["unknown"])
    price = payload.get("price", texts["unknown"])
    source = payload.get("decision_source") or payload.get("mode") or texts["unknown"]
    reason = payload.get("decision_reason") or payload.get("reason") or payload.get("message")

    lines = [
        texts["title"],
        "",
        f'{texts["asset"]}: <b>{escape(str(symbol))}</b>',
        f'{texts["expiry"]}: <b>{expiry_min} {texts["minutes"]}</b>',
        f'{texts["direction"]}: <b>{escape(str(direction))}</b>',
        f'{texts["confidence"]}: <b>{escape(str(confidence))}%</b>',
        f'{texts["price"]}: <code>{escape(str(price))}</code>',
        f'{texts["source"]}: <code>{escape(str(source))}</code>',
    ]

    if reason:
        lines.extend(["", f'{texts["reason"]}: {escape(str(reason))}'])

    return "\n".join(lines)


def handle_signal_request_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    try:
        signal_request = parse_signal_request(text)
    except ValueError:
        funnel_route, language = get_saved_context(db, user)
        language = language or normalize_language(user.get("language_code"))
        if funnel_route == "BOT":
            with httpx.Client(timeout=10) as client:
                send_html_message(client, chat_id, SIGNAL_TEXTS.get(language, SIGNAL_TEXTS["en"])["bad_expiry"])
            return True
        return False

    if signal_request is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route != "BOT":
        return False

    language = language or normalize_language(user.get("language_code"))
    texts = SIGNAL_TEXTS.get(language, SIGNAL_TEXTS["en"])
    symbol, expiry_min = signal_request

    with httpx.Client(timeout=10) as client:
        try:
            payload = get_combined_analysis(symbol=symbol, expiry_min=expiry_min)
        except (DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        send_html_message(client, chat_id, format_signal_response(language, symbol, expiry_min, payload))
        return True


def handle_test_access_code_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    if not is_test_access_code(text):
        return False

    funnel_route, language = get_saved_context(db, user)
    language = normalize_funnel_language(language or user.get("language_code"))
    funnel_route = funnel_route or "BOT"
    save_start_context(db, user, language, funnel_route)
    grant_funnel_access(db, user)

    node_code = "TEAM-SUCCESS" if funnel_route == "TEAM" else "BOT-SUCCESS"
    with httpx.Client(timeout=10) as client:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        set_chat_mini_app_menu(client, chat_id, language, enabled=True)
        send_funnel_success(client=client, chat_id=chat_id, language=language, node_code=node_code, user=user)
    return True


def handle_pairs_request_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    pairs_request = parse_pairs_request(text)
    if pairs_request is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route != "BOT":
        return False

    language = language or normalize_language(user.get("language_code"))
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    market, category, min_payout = pairs_request

    with httpx.Client(timeout=10) as client:
        try:
            payload = get_pairs(market=market, min_payout=min_payout, category=category)
        except (DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        send_html_message(client, chat_id, format_pairs_response(language, market, category, min_payout, payload))
        return True


def handle_quote_request_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    quote_request = parse_quote_request(text)
    if quote_request is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route != "BOT":
        return False

    language = language or normalize_language(user.get("language_code"))
    texts = API_TEST_TEXTS.get(language, API_TEST_TEXTS["en"])
    category, symbol, history_seconds = quote_request

    with httpx.Client(timeout=10) as client:
        try:
            payload = get_quote(category=category, symbol=symbol, history_seconds=history_seconds)
        except (DevsbiteApiError, DevsbiteConfigError, DevsbiteRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        send_html_message(client, chat_id, format_quote_response(language, category, symbol, payload))
        return True


def handle_trader_id_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    match = TRADER_ID_RE.match(text)
    if match is None:
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route not in {"BOT", "TEAM"}:
        return False

    language = normalize_funnel_language(language or user.get("language_code"))
    texts = TRADER_ID_TEXTS.get(language, TRADER_ID_TEXTS["en"])
    trader_id = match.group(1)

    with httpx.Client(timeout=10) as client:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        try:
            get_user_info(trader_id)
        except PocketOptionApiError as error:
            if error.status_code == 404:
                delivery = copy_funnel_node(client, chat_id, "ID-NOT-FOUND", language, user=user)
                start_bot_reminder_flow(
                    db,
                    user,
                    chat_id,
                    language,
                    kind=ID_NOT_FOUND_REMINDER_KIND,
                    initial_message_id=delivery.text_message_id,
                    initial_media_message_id=delivery.media_message_id,
                )
                return True

            send_html_message(client, chat_id, texts["unavailable"])
            return True
        except (PocketOptionConfigError, PocketOptionRequestError):
            send_html_message(client, chat_id, texts["unavailable"])
            return True

        telegram_id = user.get("id")
        if isinstance(telegram_id, int):
            funnel_session = get_or_create_funnel_session(db, telegram_id)
            funnel_session.trader_id = trader_id
            db.commit()
        delivery = send_topup_step(client=client, chat_id=chat_id, language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=TOPUP_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return True


def handle_invalid_trader_id_message(db: Session, user: dict[str, Any], chat_id: int, text: str) -> bool:
    if text.startswith("/"):
        return False

    funnel_route, language = get_saved_context(db, user)
    if funnel_route not in {"BOT", "TEAM"}:
        return False

    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return False

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    if (
        funnel_session is None
        or funnel_session.access_granted
        or funnel_session.reminder_kind not in TRADER_ID_EXPECTED_REMINDER_KINDS
    ):
        return False

    language = normalize_funnel_language(language or user.get("language_code"))
    with httpx.Client(timeout=10) as client:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        message_id = copy_source_message(
            client=client,
            chat_id=chat_id,
            source_message_id=ID_FORMAT_SOURCE_MESSAGE_ID,
            language=language,
        )
        if message_id is None:
            delivery = copy_funnel_node(client, chat_id, "ID-FORMAT", language, user=user)
            message_id = delivery.text_message_id
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=ID_FORMAT_REMINDER_KIND,
            initial_message_id=message_id,
        )
    return True


def handle_topup_check_callback(db: Session, user: dict[str, Any], chat_id: int, language: str, client: httpx.Client) -> str:
    texts = TRADER_ID_TEXTS.get(language, TRADER_ID_TEXTS["en"])
    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return texts["unavailable"]

    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == telegram_id).first()
    trader_id = funnel_session.trader_id.strip() if funnel_session and funnel_session.trader_id else ""
    if not trader_id:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="ID-01", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=ID_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return funnel_texts(language)["callback_ok"]

    cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
    try:
        payload = get_user_info(trader_id)
    except PocketOptionApiError as error:
        if error.status_code == 404:
            delivery = send_topup_not_found(client=client, chat_id=chat_id, language=language, user=user)
            start_bot_reminder_flow(
                db,
                user,
                chat_id,
                language,
                kind=TOPUP_NOT_FOUND_REMINDER_KIND,
                initial_message_id=delivery.text_message_id,
                initial_media_message_id=delivery.media_message_id,
            )
            return funnel_texts(language)["callback_ok"]

        send_html_message(client, chat_id, texts["unavailable"])
        return texts["unavailable"]
    except (PocketOptionConfigError, PocketOptionRequestError):
        send_html_message(client, chat_id, texts["unavailable"])
        return texts["unavailable"]

    topup_amount = get_topup_amount(payload)
    if topup_amount is None or topup_amount <= 0:
        delivery = send_topup_not_found(client=client, chat_id=chat_id, language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=TOPUP_NOT_FOUND_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return funnel_texts(language)["callback_ok"]

    if topup_amount < MIN_TOPUP_AMOUNT_USD:
        delivery = send_topup_low(client=client, chat_id=chat_id, language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=TOPUP_LOW_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return funnel_texts(language)["callback_ok"]

    grant_funnel_access(db, user)
    node_code = "TEAM-SUCCESS" if (funnel_session and funnel_session.route == "TEAM") else "BOT-SUCCESS"
    set_chat_mini_app_menu(client, chat_id, language, enabled=True)
    send_funnel_success(client=client, chat_id=chat_id, language=language, node_code=node_code, user=user)
    return funnel_texts(language)["callback_ok"]


@router.post("/webhook", summary="Telegram bot webhook")
def telegram_webhook(update: dict[str, Any], db: Session = Depends(get_db)):
    ensure_telegram_configured()

    callback_query = update.get("callback_query")
    if callback_query:
        callback_data = callback_query.get("data")
        if callback_data and callback_data.startswith("admin_signal:"):
            handle_admin_callback_query(db, callback_query)
            return {"ok": True}
        if callback_data == "text_format":
            handle_callback_query(callback_query, db)
            return {"ok": True}
        handle_callback_query(callback_query, db)
        return {"ok": True}

    message = update.get("message") or {}
    log_telegram_media_ids(message)
    text = message.get("text")
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")

    if chat_id is None:
        return {"ok": True}

    upsert_telegram_user(db, user)
    db.commit()

    if text and handle_admin_command_message(db, user, chat_id, message, text):
        return {"ok": True}

    saved_route, saved_language = get_saved_context(db, user)
    menu_language = normalize_funnel_language(saved_language or user.get("language_code"))
    with httpx.Client(timeout=10) as client:
        set_chat_mini_app_menu(client, chat_id, menu_language, enabled=should_show_mini_app_menu(db, user))
        if handle_custom_emoji_id_message(client, chat_id, message):
            return {"ok": True}

    if text and not text.startswith("/start"):
        if handle_test_access_code_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_trader_id_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_pairs_request_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_quote_request_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        if handle_signal_request_message(db=db, user=user, chat_id=chat_id, text=text):
            return {"ok": True}
        handle_invalid_trader_id_message(db=db, user=user, chat_id=chat_id, text=text)
        return {"ok": True}

    if not text or not text.startswith("/start"):
        return {"ok": True}

    start_context = parse_start_context(text)
    if start_context is None:
        print(f"telegram_start ignored unsupported_payload text={text!r}")
        return {"ok": True}

    funnel_route, deeplink_language = start_context
    language = normalize_funnel_language(deeplink_language or user.get("language_code"))
    print(
        f"telegram_start language_code={user.get('language_code')} "
        f"funnel_route={funnel_route} deeplink_language={deeplink_language} normalized_language={language}"
    )

    save_start_context(db, user, language, funnel_route)

    node_code = "TEAM-01" if funnel_route == "TEAM" else "BOT-01"

    with httpx.Client(timeout=10) as client:
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        try:
            delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code=node_code, language=language, user=user)
            start_bot_reminder_flow(
                db,
                user,
                chat_id,
                language,
                initial_message_id=delivery.text_message_id,
                initial_media_message_id=delivery.media_message_id,
            )
        except Exception as error:
            send_funnel_delivery_error(client, chat_id, node_code, error)

    return {"ok": True}


def handle_funnel_callback(
    db: Session,
    user: dict[str, Any],
    chat_id: int,
    data: str,
    language: str,
    client: httpx.Client,
) -> str:
    action = data.removeprefix("funnel:")
    texts = funnel_texts(language)

    if action == "bot_start":
        save_start_context(db, user, language, "BOT")
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-STEP-01", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=BOT_STEP_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return texts["callback_ok"]

    if action == "team_start":
        save_start_context(db, user, language, "TEAM")
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        set_chat_mini_app_menu(client, chat_id, language, enabled=should_show_mini_app_menu(db, user))
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="TEAM-STEP-01", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=BOT_STEP_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return texts["callback_ok"]

    if action == "existing_account":
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        delivery = copy_funnel_node(client=client, chat_id=chat_id, node_code="BOT-EXISTING-ACCOUNT", language=language, user=user)
        start_bot_reminder_flow(
            db,
            user,
            chat_id,
            language,
            kind=ID_REMINDER_KIND,
            initial_message_id=delivery.text_message_id,
            initial_media_message_id=delivery.media_message_id,
        )
        return texts["callback_ok"]

    if action == "check_topup":
        return handle_topup_check_callback(db=db, user=user, chat_id=chat_id, language=language, client=client)

    if action in {"continue_topup_low", "continue_topup_not_found"}:
        cancel_bot_reminder_flow(db, user, client=client, chat_id=chat_id)
        if action == "continue_topup_low":
            delivery = send_topup_low(client=client, chat_id=chat_id, language=language, user=user)
            start_bot_reminder_flow(
                db,
                user,
                chat_id,
                language,
                kind=TOPUP_LOW_REMINDER_KIND,
                initial_message_id=delivery.text_message_id,
                initial_media_message_id=delivery.media_message_id,
            )
        else:
            delivery = send_topup_not_found(client=client, chat_id=chat_id, language=language, user=user)
            start_bot_reminder_flow(
                db,
                user,
                chat_id,
                language,
                kind=TOPUP_NOT_FOUND_REMINDER_KIND,
                initial_message_id=delivery.text_message_id,
                initial_media_message_id=delivery.media_message_id,
            )
        return texts["callback_ok"]

    return texts["callback_ok"]


def handle_callback_query(callback_query: dict[str, Any], db: Session) -> None:
    callback_id = callback_query.get("id")
    data = callback_query.get("data")
    user = callback_query.get("from") or {}
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    saved_language = get_saved_language(db, user)
    language = normalize_funnel_language(saved_language or user.get("language_code"))
    print(
        f"telegram_callback data={data} language_code={user.get('language_code')} "
        f"saved_language={saved_language} normalized_language={language}"
    )

    with httpx.Client(timeout=10) as client:
        callback_text = funnel_texts(language)["callback_ok"]
        if data and data.startswith("funnel:") and chat_id is not None:
            try:
                callback_text = handle_funnel_callback(
                    db=db,
                    user=user,
                    chat_id=chat_id,
                    data=data,
                    language=language,
                    client=client,
                )
            except Exception as error:
                callback_text = "\u041e\u0448\u0438\u0431\u043a\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0438"
                send_funnel_delivery_error(client, chat_id, data.removeprefix("funnel:"), error)
        elif data == "text_format":
            callback_text = LEGACY_TEXT_FORMAT_TEXTS.get(language, LEGACY_TEXT_FORMAT_TEXTS["en"])["selected"]

        if callback_id:
            answer_callback_query(client, callback_id, callback_text).raise_for_status()

        if data and data.startswith("funnel:"):
            return

        if data != "text_format" or chat_id is None:
            return

        legacy_text = LEGACY_TEXT_FORMAT_TEXTS.get(language, LEGACY_TEXT_FORMAT_TEXTS["en"])
        send_message(
            client,
            chat_id,
            legacy_text["message"],
            parse_mode="HTML",
            reply_markup={
                "inline_keyboard": [
                    [{"text": legacy_text["open_mini_app"], "web_app": {"url": settings.telegram_webapp_url}}]
                ]
            },
        ).raise_for_status()


