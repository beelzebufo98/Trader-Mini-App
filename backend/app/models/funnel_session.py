from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from app.database import Base


class FunnelSession(Base):
    __tablename__ = "funnel_sessions"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    route = Column(String(16), nullable=False, default="")
    access_granted = Column(Boolean, nullable=False, default=False)
    reminder_kind = Column(String(32), nullable=False, default="")
    reminder_stage = Column(Integer, nullable=False, default=0)
    reminder_token = Column(String(64), nullable=False, default="")
    reminder_chat_id = Column(BigInteger, nullable=True)
    reminder_due_at = Column(DateTime, nullable=True)
    last_reminder_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
