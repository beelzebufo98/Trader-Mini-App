from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.funnel_session import FunnelSession
from app.models.telegram_user import TelegramUser as TelegramUserModel
from app.models.user_settings import UserSettings
from app.schemas.user_settings import TelegramUser, UserSettingsRead, UserSettingsUpdate
from app.services.telegram_auth import get_current_telegram_user

router = APIRouter()


def serialize_settings(
    settings: UserSettings,
    telegram_user: TelegramUserModel | None,
    funnel_session: FunnelSession | None,
) -> UserSettingsRead:
    return UserSettingsRead(
        telegram_id=settings.telegram_id,
        username=telegram_user.username if telegram_user else None,
        first_name=telegram_user.first_name if telegram_user else None,
        utc_offset=settings.utc_offset,
        impacts=[impact for impact in settings.impacts.split(",") if impact],
        currencies=[currency for currency in settings.currencies.split(",") if currency],
        news_window=settings.news_window,
        language=settings.language,
        market=settings.market,
        funnel_route=funnel_session.route if funnel_session else "",
        funnel_access_granted=bool(funnel_session and funnel_session.access_granted),
        created_at=settings.created_at,
        updated_at=settings.updated_at,
    )


def get_or_create_telegram_user(db: Session, user: TelegramUser) -> TelegramUserModel:
    telegram_user = db.query(TelegramUserModel).filter(TelegramUserModel.telegram_id == user.id).first()
    if telegram_user is None:
        telegram_user = TelegramUserModel(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
        db.add(telegram_user)
    else:
        telegram_user.username = user.username
        telegram_user.first_name = user.first_name

    return telegram_user


def get_or_create_settings(db: Session, user: TelegramUser) -> UserSettings:
    settings = db.query(UserSettings).filter(UserSettings.telegram_id == user.id).first()
    if settings is not None:
        return settings

    settings = UserSettings(telegram_id=user.id)
    db.add(settings)
    return settings


def get_or_create_funnel_session(db: Session, user: TelegramUser) -> FunnelSession:
    funnel_session = db.query(FunnelSession).filter(FunnelSession.telegram_id == user.id).first()
    if funnel_session is not None:
        return funnel_session

    funnel_session = FunnelSession(telegram_id=user.id)
    db.add(funnel_session)
    return funnel_session


def get_or_create_user_state(db: Session, user: TelegramUser) -> tuple[UserSettings, TelegramUserModel, FunnelSession]:
    telegram_user = get_or_create_telegram_user(db, user)
    settings = get_or_create_settings(db, user)
    funnel_session = get_or_create_funnel_session(db, user)
    db.commit()
    db.refresh(telegram_user)
    db.refresh(settings)
    db.refresh(funnel_session)
    return settings, telegram_user, funnel_session


@router.get("/settings", response_model=UserSettingsRead, summary="Get current Telegram user settings")
def read_settings(
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_current_telegram_user),
):
    settings, telegram_user, funnel_session = get_or_create_user_state(db, user)
    return serialize_settings(settings, telegram_user, funnel_session)


@router.put("/settings", response_model=UserSettingsRead, summary="Update current Telegram user settings")
def update_settings(
    payload: UserSettingsUpdate,
    db: Session = Depends(get_db),
    user: TelegramUser = Depends(get_current_telegram_user),
):
    settings, telegram_user, funnel_session = get_or_create_user_state(db, user)

    if payload.utc_offset is not None:
        settings.utc_offset = payload.utc_offset
    if payload.impacts is not None:
        settings.impacts = ",".join(payload.impacts)
    if payload.currencies is not None:
        settings.currencies = ",".join(payload.currencies)
    if payload.news_window is not None:
        settings.news_window = payload.news_window
    if payload.language is not None:
        settings.language = payload.language
    if payload.market is not None:
        settings.market = payload.market
    if payload.funnel_route is not None:
        funnel_session.route = payload.funnel_route

    db.commit()
    db.refresh(telegram_user)
    db.refresh(settings)
    db.refresh(funnel_session)
    return serialize_settings(settings, telegram_user, funnel_session)
