from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.economic_event import EconomicEvent
from app.parser.normalize import ParsedEvent


@dataclass(frozen=True)
class UpsertResult:
    parsed: int
    created: int
    updated: int
    skipped: int


def upsert_events(db: Session, events: list[ParsedEvent]) -> UpsertResult:
    created = 0
    updated = 0
    skipped = 0

    for event in events:
        existing = db.query(EconomicEvent).filter(EconomicEvent.event_hash == event.event_hash).first()
        values = event.__dict__

        if existing is None:
            db.add(EconomicEvent(**values))
            created += 1
            continue

        changed = False
        for field, value in values.items():
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True

        if changed:
            updated += 1
        else:
            skipped += 1

    db.commit()

    return UpsertResult(parsed=len(events), created=created, updated=updated, skipped=skipped)
