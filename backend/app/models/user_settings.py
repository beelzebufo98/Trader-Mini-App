from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(128), nullable=True)
    first_name = Column(String(128), nullable=True)
    utc_offset = Column(Integer, nullable=False, default=3)
    impacts = Column(String(128), nullable=False, default="HIGH")
    currencies = Column(String(256), nullable=False, default="")
    news_window = Column(String(32), nullable=False, default="48H")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
