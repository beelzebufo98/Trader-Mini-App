from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()

SUPPORTED_LANGUAGES = {"ru", "en", "es", "pt", "tr", "ar"}

BOT_TEXTS = {
    "ru": {
        "start": (
            "Привет! 👋\n\n"
            "Профессиональные торговые сигналы для бинарных опционов и форекс рынка.\n\n"
            "Выберите формат работы:"
        ),
        "mini_app": "⚡ Мини-апп (рекомендуется)",
        "text_format": "💬 Текстовый формат",
        "text_selected": "Текстовый формат выбран",
        "text_selected_message": (
            "Текстовый формат выбран.\n\n"
            "Сигналы будут приходить сообщениями Telegram. На первом этапе реальные сигналы еще не подключены."
        ),
        "open_mini_app": "⚡ Открыть Mini App",
    },
    "en": {
        "start": (
            "Hi! 👋\n\n"
            "Professional trading signals for binary options and the forex market.\n\n"
            "Choose how you want to work:"
        ),
        "mini_app": "⚡ Mini App (recommended)",
        "text_format": "💬 Text format",
        "text_selected": "Text format selected",
        "text_selected_message": (
            "Text format selected.\n\n"
            "Signals will be delivered as Telegram messages. Real signals are not connected at this stage."
        ),
        "open_mini_app": "⚡ Open Mini App",
    },
    "es": {
        "start": "¡Hola! 👋\n\nSeñales profesionales para opciones binarias y forex.\n\nElige el formato de trabajo:",
        "mini_app": "⚡ Mini App (recomendado)",
        "text_format": "💬 Formato de texto",
        "text_selected": "Formato de texto seleccionado",
        "text_selected_message": "Formato de texto seleccionado.\n\nLas señales llegarán como mensajes de Telegram. Las señales reales aún no están conectadas.",
        "open_mini_app": "⚡ Abrir Mini App",
    },
    "pt": {
        "start": "Olá! 👋\n\nSinais profissionais para opções binárias e forex.\n\nEscolha o formato de trabalho:",
        "mini_app": "⚡ Mini App (recomendado)",
        "text_format": "💬 Formato de texto",
        "text_selected": "Formato de texto selecionado",
        "text_selected_message": "Formato de texto selecionado.\n\nOs sinais chegarão como mensagens do Telegram. Sinais reais ainda não estão conectados.",
        "open_mini_app": "⚡ Abrir Mini App",
    },
    "tr": {
        "start": "Merhaba! 👋\n\nBinary opsiyonlar ve forex piyasası için profesyonel işlem sinyalleri.\n\nÇalışma formatını seçin:",
        "mini_app": "⚡ Mini App (önerilir)",
        "text_format": "💬 Metin formatı",
        "text_selected": "Metin formatı seçildi",
        "text_selected_message": "Metin formatı seçildi.\n\nSinyaller Telegram mesajları olarak gelecek. Gerçek sinyaller bu aşamada bağlı değil.",
        "open_mini_app": "⚡ Mini App'i aç",
    },
    "ar": {
        "start": "مرحبا! 👋\n\nإشارات تداول احترافية للخيارات الثنائية وسوق الفوركس.\n\nاختر طريقة العمل:",
        "mini_app": "⚡ Mini App (موصى به)",
        "text_format": "💬 تنسيق نصي",
        "text_selected": "تم اختيار التنسيق النصي",
        "text_selected_message": "تم اختيار التنسيق النصي.\n\nستصل الإشارات كرسائل Telegram. الإشارات الحقيقية غير متصلة في هذه المرحلة.",
        "open_mini_app": "⚡ فتح Mini App",
    },
}


def ensure_telegram_configured() -> None:
    if not settings.telegram_bot_token or not settings.telegram_webapp_url:
        raise HTTPException(status_code=503, detail="Telegram bot is not configured")


def telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def normalize_language(language_code: str | None) -> str:
    if not language_code:
        return "en"

    language = language_code.lower().split("-")[0]
    return language if language in SUPPORTED_LANGUAGES else "en"


def mini_app_keyboard(language: str) -> dict[str, Any]:
    text = BOT_TEXTS[language]
    return {
        "inline_keyboard": [
            [{"text": text["mini_app"], "web_app": {"url": settings.telegram_webapp_url}}],
            [{"text": text["text_format"], "callback_data": "text_format"}],
        ]
    }


@router.post("/webhook", summary="Telegram bot webhook")
def telegram_webhook(update: dict[str, Any]):
    ensure_telegram_configured()

    callback_query = update.get("callback_query")
    if callback_query:
        handle_callback_query(callback_query)
        return {"ok": True}

    message = update.get("message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")
    language = normalize_language(user.get("language_code"))

    if text != "/start" or chat_id is None:
        return {"ok": True}

    payload = {
        "chat_id": chat_id,
        "text": BOT_TEXTS[language]["start"],
        "reply_markup": mini_app_keyboard(language),
    }

    with httpx.Client(timeout=10) as client:
        response = client.post(telegram_api_url("sendMessage"), json=payload)
        response.raise_for_status()

    return {"ok": True}


def handle_callback_query(callback_query: dict[str, Any]) -> None:
    callback_id = callback_query.get("id")
    data = callback_query.get("data")
    user = callback_query.get("from") or {}
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    language = normalize_language(user.get("language_code"))
    text = BOT_TEXTS[language]

    with httpx.Client(timeout=10) as client:
        if callback_id:
            client.post(
                telegram_api_url("answerCallbackQuery"),
                json={"callback_query_id": callback_id, "text": text["text_selected"]},
            ).raise_for_status()

        if data != "text_format" or chat_id is None:
            return

        client.post(
            telegram_api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text["text_selected_message"],
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": text["open_mini_app"], "web_app": {"url": settings.telegram_webapp_url}}]
                    ]
                },
            },
        ).raise_for_status()
