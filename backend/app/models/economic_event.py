from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class EconomicEvent(Base):
    __tablename__ = "economic_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    currency = Column(String(8), nullable=False)
    impact = Column(String(32), nullable=False)
    source = Column(String(128), nullable=False, default="forexfactory")
    source_event_id = Column(String(128), nullable=True)
    event_hash = Column(String(128), nullable=False, unique=True, index=True)
    datetime_utc = Column(DateTime, nullable=False)
    event_date = Column(DateTime, nullable=True)
    event_time = Column(String(16), nullable=True)
    event_url = Column(String(512), nullable=True)
    actual = Column(String(64), nullable=True)
    forecast = Column(String(64), nullable=True)
    previous = Column(String(64), nullable=True)
    is_all_day = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
