from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.user_settings import TelegramUser
from app.services.pocket_option import (
    PocketOptionApiError,
    PocketOptionConfigError,
    PocketOptionRequestError,
    get_user_info,
)
from app.services.telegram_auth import get_current_telegram_user

router = APIRouter()


@router.get("/user-info/{user_id}", summary="Get Pocket Option user info")
def read_pocket_option_user_info(
    user_id: str,
    _: TelegramUser = Depends(get_current_telegram_user),
) -> dict[str, Any]:
    try:
        return get_user_info(user_id)
    except PocketOptionConfigError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except PocketOptionApiError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error
    except PocketOptionRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
