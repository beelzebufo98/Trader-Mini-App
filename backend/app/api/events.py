from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.economic_event import (
    EconomicEventCreate,
    EconomicEventRead,
    EconomicEventsResponse,
)
from app.services.events_service import create_event, get_events

router = APIRouter()


@router.get("/", response_model=EconomicEventsResponse, summary="List economic events")
def list_events(
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    impact: Optional[str] = Query("HIGH"),
    currency: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    events = get_events(db, from_, to, impact, currency, limit)
    return {"events": events}


@router.post("/", response_model=EconomicEventRead, status_code=201, summary="Create economic event")
def add_event(event_in: EconomicEventCreate, db: Session = Depends(get_db)):
    try:
        return create_event(db, event_in)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
