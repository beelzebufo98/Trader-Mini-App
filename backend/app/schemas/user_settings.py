from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, field_serializer, field_validator


VALID_IMPACTS = {"HIGH", "MEDIUM", "LOW", "HOLIDAY"}


class TelegramUser(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None


class UserSettingsUpdate(BaseModel):
    utc_offset: Optional[int] = None
    impacts: Optional[list[str]] = None
    currencies: Optional[list[str]] = None

    @field_validator("utc_offset")
    @classmethod
    def validate_utc_offset(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not -12 <= value <= 14:
            raise ValueError("utc_offset must be between -12 and 14")
        return value

    @field_validator("impacts")
    @classmethod
    def validate_impacts(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value

        normalized = [impact.upper() for impact in value]
        invalid = [impact for impact in normalized if impact not in VALID_IMPACTS]
        if invalid:
            raise ValueError(f"Unsupported impacts: {', '.join(invalid)}")
        return normalized

    @field_validator("currencies")
    @classmethod
    def validate_currencies(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return value

        return [currency.strip().upper() for currency in value if currency.strip()]


class UserSettingsRead(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    utc_offset: int
    impacts: list[str]
    currencies: list[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_utc_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)

        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
