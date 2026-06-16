from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user_settings import UserSettings
from app.schemas.user_settings import TelegramUser, UserSettingsRead, UserSettingsUpdate
from app.services.telegram_auth import get_current_telegram_user

router = APIRouter()


def serialize_settings(settings: UserSettings) -> UserSettingsRead:
    return UserSettingsRead(
        telegram_id=settings.telegram_id,
        username=settings.username,
        first_name=settings.first_name,
        utc_offset=settings.utc_offset,
        impacts=[impact for impact in settings.impacts.split(",") if impact],
        currencies=[currency for currency in settings.currencies.split(",") if currency],
        news_window=settings.news_window,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


def get_or_create_settings(db: Session, user: TelegramUser) -> UserSettings:
    settings = db.query(UserSettings).filter(UserSettings.telegram_id == user.id).first()
    if settings is not None:
        settings.username = user.username
        settings.first_name = user.first_name
        db.commit()
        db.refresh(settings)
        return settings

    settings = UserSettings(telegram_id=user.id, username=user.username, first_name=user.first_name)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/settings", response_model=UserSettingsRead, summary="Get current Telegram user settings")
def read_settings(
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_current_telegram_user),
):
    return serialize_settings(get_or_create_settings(db, user))


@router.put("/settings", response_model=UserSettingsRead, summary="Update current Telegram user settings")
def update_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_current_telegram_user),
):
    settings = get_or_create_settings(db, user)

    if payload.utc_offset is not None:
        settings.utc_offset = payload.utc_offset
    if payload.impacts is not None:
        settings.impacts = ",".join(payload.impacts)
    if payload.currencies is not None:
        settings.currencies = ",".join(payload.currencies)
    if payload.news_window is not None:
        settings.news_window = payload.news_window

    db.commit()
    db.refresh(settings)
    return serialize_settings(settings)
