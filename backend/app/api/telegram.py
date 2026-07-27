import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user_settings import UserSettings

router = APIRouter()

SUPPORTED_LANGUAGES = {"ru", "en", "es", "pt", "tr", "ar"}
LANGUAGE_ALIASES = {
    "russian": "ru",
    "english": "en",
    "spanish": "es",
    "portuguese": "pt",
    "turkish": "tr",
    "arabic": "ar",
}

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


def parse_start_language(text: str | None) -> str | None:
    if not text:
        return None

    parts = text.strip().split(maxsplit=1)
    if not parts or not parts[0].startswith("/start") or len(parts) < 2:
        return None

    payload = parts[1].strip().lower()
    tokens = [token for token in re.split(r"[^a-z]+", payload) if token]
    for token in tokens:
        if token in SUPPORTED_LANGUAGES:
            return token
        if token in LANGUAGE_ALIASES:
            return LANGUAGE_ALIASES[token]

    return None


def save_start_language(db: Session, user: dict[str, Any], language: str) -> None:
    telegram_id = user.get("id")
    if telegram_id is None:
        return

    settings_row = db.query(UserSettings).filter(UserSettings.telegram_id == telegram_id).first()
    if settings_row is None:
        settings_row = UserSettings(
            telegram_id=telegram_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
            language=language,
        )
        db.add(settings_row)
    else:
        settings_row.username = user.get("username")
        settings_row.first_name = user.get("first_name")
        settings_row.language = language

    db.commit()


def mini_app_keyboard(language: str) -> dict[str, Any]:
    text = BOT_TEXTS[language]
    return {
        "inline_keyboard": [
            [{"text": text["mini_app"], "web_app": {"url": settings.telegram_webapp_url}}],
            [{"text": text["text_format"], "callback_data": "text_format"}],
        ]
    }


@router.post("/webhook", summary="Telegram bot webhook")
def telegram_webhook(update: dict[str, Any], db: Session = Depends(get_db)):
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
    language = parse_start_language(text) or normalize_language(user.get("language_code"))
    print(
        f"telegram_start language_code={user.get('language_code')} "
        f"start_language={parse_start_language(text)} normalized_language={language}"
    )

    if not text or not text.startswith("/start") or chat_id is None:
        return {"ok": True}

    save_start_language(db, user, language)

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
    print(f"telegram_callback data={data} language_code={user.get('language_code')} normalized_language={language}")

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
