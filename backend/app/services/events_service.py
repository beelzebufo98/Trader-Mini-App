from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.economic_event import EconomicEvent
from app.schemas.economic_event import EconomicEventCreate


def get_events(
    db: Session,
    from_: Optional[datetime] = None,
    to: Optional[datetime] = None,
    impact: Optional[str] = None,
    currency: Optional[str] = None,
    limit: int = 20,
):
    query = db.query(EconomicEvent)

    if from_ is not None:
        query = query.filter(EconomicEvent.datetime_utc >= from_)
    if to is not None:
        query = query.filter(EconomicEvent.datetime_utc <= to)
    if impact is not None:
        query = query.filter(EconomicEvent.impact == impact)
    if currency is not None:
        query = query.filter(EconomicEvent.currency == currency)

    return query.order_by(EconomicEvent.datetime_utc.asc()).limit(limit).all()


def create_event(db: Session, event_in: EconomicEventCreate):
    existing = db.query(EconomicEvent).filter(EconomicEvent.event_hash == event_in.event_hash).first()
    if existing:
        raise ValueError("Event with this hash already exists")

    event = EconomicEvent(**event_in.model_dump(mode="json"))
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
