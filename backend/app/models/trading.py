from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    market_mode = Column(String(16), nullable=False, default="OTC")
    status = Column(String(32), nullable=False, default="scheduled", index=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=False, index=True)
    expiry_seconds = Column(Integer, nullable=False, default=180)
    base_amount = Column(Numeric(12, 2), nullable=True)
    max_overlaps = Column(Integer, nullable=False, default=3)
    min_payout = Column(Integer, nullable=False, default=80)
    min_confidence = Column(Integer, nullable=False, default=70)
    total_series = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    created_by_telegram_id = Column(BigInteger, nullable=True)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    signals = relationship("TradingSignal", back_populates="session", cascade="all, delete-orphan")
    jobs = relationship("TradingSignalJob", back_populates="session", cascade="all, delete-orphan")


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="planned", index=True)
    market_type = Column(String(16), nullable=False, default="OTC")
    category = Column(String(32), nullable=False, default="otc")
    symbol = Column(String(128), nullable=False, index=True)
    resolved_symbol = Column(String(128), nullable=False, default="")
    flag_1 = Column(String(16), nullable=False, default="")
    flag_2 = Column(String(16), nullable=False, default="")
    direction = Column(String(8), nullable=False, default="")
    direction_source = Column(String(64), nullable=False, default="")
    decision_reason = Column(Text, nullable=False, default="")
    confidence = Column(Numeric(6, 2), nullable=True)
    payout = Column(Numeric(6, 2), nullable=True)
    expiry_seconds = Column(Integer, nullable=False, default=180)
    entry_time = Column(DateTime, nullable=True, index=True)
    entry_price = Column(Numeric(20, 8), nullable=True)
    close_time = Column(DateTime, nullable=True, index=True)
    close_price = Column(Numeric(20, 8), nullable=True)
    result = Column(String(16), nullable=False, default="")
    current_attempt_no = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=4)
    countdown_message_id = Column(Integer, nullable=True)
    signal_message_id = Column(Integer, nullable=True)
    result_message_id = Column(Integer, nullable=True)
    chart_image_path = Column(String(512), nullable=False, default="")
    source_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    session = relationship("TradingSession", back_populates="signals")
    attempts = relationship("TradingSignalAttempt", back_populates="signal", cascade="all, delete-orphan")
    jobs = relationship("TradingSignalJob", back_populates="signal", cascade="all, delete-orphan")


class TradingSignalAttempt(Base):
    __tablename__ = "trading_signal_attempts"
    __table_args__ = (
        UniqueConstraint("signal_id", "attempt_no", name="uq_trading_signal_attempt_no"),
    )

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("trading_signals.id"), nullable=False, index=True)
    attempt_no = Column(Integer, nullable=False)
    kind = Column(String(24), nullable=False, default="base")
    status = Column(String(32), nullable=False, default="planned", index=True)
    direction = Column(String(8), nullable=False, default="")
    entry_time = Column(DateTime, nullable=True, index=True)
    entry_price = Column(Numeric(20, 8), nullable=True)
    close_time = Column(DateTime, nullable=True, index=True)
    close_price = Column(Numeric(20, 8), nullable=True)
    result = Column(String(16), nullable=False, default="")
    expiry_seconds = Column(Integer, nullable=False, default=180)
    entry_message_id = Column(Integer, nullable=True)
    result_message_id = Column(Integer, nullable=True)
    chart_message_id = Column(Integer, nullable=True)
    chart_image_path = Column(String(512), nullable=False, default="")
    quote_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    signal = relationship("TradingSignal", back_populates="attempts")
    jobs = relationship("TradingSignalJob", back_populates="attempt", cascade="all, delete-orphan")


class TradingSignalJob(Base):
    __tablename__ = "trading_signal_jobs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=True, index=True)
    signal_id = Column(Integer, ForeignKey("trading_signals.id"), nullable=True, index=True)
    attempt_id = Column(Integer, ForeignKey("trading_signal_attempts.id"), nullable=True, index=True)
    kind = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="scheduled", index=True)
    run_at = Column(DateTime, nullable=False, index=True)
    locked_at = Column(DateTime, nullable=True)
    lock_token = Column(String(64), nullable=False, default="")
    attempts_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=False, default="")
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    session = relationship("TradingSession", back_populates="jobs")
    signal = relationship("TradingSignal", back_populates="jobs")
    attempt = relationship("TradingSignalAttempt", back_populates="jobs")


Index("ix_trading_signal_jobs_due", TradingSignalJob.status, TradingSignalJob.run_at)
Index("ix_trading_signals_session_status", TradingSignal.session_id, TradingSignal.status)
