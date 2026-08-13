from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings


def ensure_telegram_configured() -> None:
    if not settings.telegram_bot_token or not settings.telegram_webapp_url:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")


def telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def set_chat_menu_button(client: httpx.Client, chat_id: int, menu_button: dict[str, Any]) -> httpx.Response:
    return client.post(
        telegram_api_url("setChatMenuButton"),
        json={
            "chat_id": chat_id,
            "menu_button": menu_button,
        },
    )


def copy_message(
    client: httpx.Client,
    chat_id: int,
    from_chat_id: int | str,
    message_id: int,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> httpx.Response:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return client.post(telegram_api_url("copyMessage"), json=payload)


def delete_message(client: httpx.Client, chat_id: int, message_id: int) -> httpx.Response:
    return client.post(
        telegram_api_url("deleteMessage"),
        json={"chat_id": chat_id, "message_id": message_id},
    )


def send_message(
    client: httpx.Client,
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
    reply_markup: dict[str, Any] | None = None,
    disable_web_page_preview: bool | None = None,
) -> httpx.Response:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    if disable_web_page_preview is not None:
        payload["disable_web_page_preview"] = disable_web_page_preview

    return client.post(telegram_api_url("sendMessage"), json=payload)


def send_photo(client: httpx.Client, chat_id: int, photo_path: Path) -> httpx.Response:
    with photo_path.open("rb") as photo:
        return client.post(
            telegram_api_url("sendPhoto"),
            data={"chat_id": chat_id},
            files={"photo": (photo_path.name, photo, "image/png")},
        )


def answer_callback_query(client: httpx.Client, callback_query_id: str, text: str) -> httpx.Response:
    return client.post(
        telegram_api_url("answerCallbackQuery"),
        json={"callback_query_id": callback_query_id, "text": text},
    )
