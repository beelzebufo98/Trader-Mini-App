from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from app.database import Base


class TelegramSignalChannel(Base):
    __tablename__ = "telegram_signal_channels"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False, default="")
    username = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_telegram_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
