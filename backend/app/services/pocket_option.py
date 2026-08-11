import hashlib
from typing import Any

import httpx

from app.config import settings


class PocketOptionConfigError(RuntimeError):
    pass


class PocketOptionRequestError(RuntimeError):
    pass


class PocketOptionApiError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_user_info_hash(user_id: str, partner_id: str, api_token: str) -> str:
    payload = f"{user_id}:{partner_id}:{api_token}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def get_user_info(user_id: str) -> dict[str, Any]:
    partner_id = settings.pocket_option_partner_id.strip()
    api_token = settings.pocket_option_api_token.strip()
    base_url = settings.pocket_option_api_base_url.rstrip("/")

    if not partner_id or not api_token:
        raise PocketOptionConfigError("Pocket Option API credentials are not configured")

    request_hash = build_user_info_hash(user_id=user_id, partner_id=partner_id, api_token=api_token)
    url = f"{base_url}/user-info/{user_id}/{partner_id}/{request_hash}"

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url)
            try:
                payload = response.json()
            except ValueError as error:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as status_error:
                    raise PocketOptionRequestError(
                        f"Pocket Option API returned {status_error.response.status_code}"
                    ) from status_error
                raise PocketOptionRequestError("Pocket Option API returned invalid JSON") from error
    except (httpx.RequestError, ValueError) as error:
        raise PocketOptionRequestError("Pocket Option API request failed") from error

    if not isinstance(payload, dict):
        raise PocketOptionRequestError("Pocket Option API returned an unexpected payload")

    if payload.get("error") is True:
        status_code = payload.get("status_code", 400)
        message = payload.get("message", "Pocket Option API returned an error")

        if not isinstance(status_code, int):
            status_code = 400
        if not isinstance(message, str) or not message:
            message = "Pocket Option API returned an error"

        raise PocketOptionApiError(message=message, status_code=status_code)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise PocketOptionRequestError(
            f"Pocket Option API returned {error.response.status_code}"
        ) from error

    return payload
