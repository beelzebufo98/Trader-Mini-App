from datetime import UTC, datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, field_serializer


class EconomicEventBase(BaseModel):
    title: str
    currency: str
    impact: str
    datetime_utc: datetime
    source: str = "forexfactory"
    source_event_id: Optional[str] = None
    event_hash: str
    event_url: Optional[HttpUrl] = None
    is_all_day: bool = False
    event_date: Optional[datetime] = None
    event_time: Optional[str] = None
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None


class EconomicEventCreate(EconomicEventBase):
    pass


class EconomicEventRead(EconomicEventBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer("datetime_utc", "created_at", "updated_at", when_used="json")
    def serialize_utc_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)

        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    model_config = {
        "from_attributes": True,
    }


class EconomicEventsResponse(BaseModel):
    events: List[EconomicEventRead]
