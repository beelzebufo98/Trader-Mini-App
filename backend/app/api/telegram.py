from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()


@router.post("/webhook", summary="Telegram bot webhook")
def telegram_webhook(update: dict[str, Any]):
    message = update.get("message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if text != "/start" or chat_id is None:
        return {"ok": True}

    if not settings.telegram_bot_token or not settings.telegram_webapp_url:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")

    payload = {
        "chat_id": chat_id,
        "text": "Open Trader Mini App",
        "reply_markup": {
            "inline_keyboard": [[{"text": "Open Trader App", "web_app": {"url": settings.telegram_webapp_url}}]]
        },
    }

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    with httpx.Client(timeout=10) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    return {"ok": True}
