from datetime import datetime, timedelta
from decimal import Decimal
from secrets import randbelow

from sqlalchemy.orm import Session

from app.config import settings
from app.models.trading import TradingSession, TradingSignal, TradingSignalAttempt, TradingSignalJob
from app.services.devsbite import extract_latest_price, get_combined_analysis, get_quote

MVP_MARKET_MODE = "OTC"
MVP_CATEGORY = "otc"
MVP_SYMBOL = "EUR/USD OTC"
MVP_ANALYSIS_SYMBOL = "EUR/USD OTC"
MVP_FLAG_1 = "\U0001f1ea\U0001f1fa"
MVP_FLAG_2 = "\U0001f1fa\U0001f1f8"
MVP_EXPIRY_SECONDS = 180
MVP_EXPIRY_MINUTES = 3
MVP_MIN_PAYOUT = 80
MVP_MIN_CONFIDENCE = 70
MVP_MAX_OVERLAPS = 3
MVP_SESSION_DURATION_MINUTES = 60
MVP_SESSION_START_DELAY_MINUTES = 60
MVP_SIGNAL_COUNTDOWN_SECONDS = 60


class TradingMvpConfigError(RuntimeError):
    pass


def get_signals_channel_id() -> int:
    value = settings.telegram_signals_channel_id.strip()
    if not value:
        raise TradingMvpConfigError("TELEGRAM_SIGNALS_CHANNEL_ID is not configured")
    return int(value)


def _decimal_or_none(value: float | int | str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _confidence_from_payload(payload: dict) -> Decimal:
    confidence = _decimal_or_none(payload.get("confidence"))
    if confidence is not None:
        return confidence
    return Decimal(str(MVP_MIN_CONFIDENCE + randbelow(31)))


def _direction_from_payload(payload: dict) -> str:
    direction = str(payload.get("signal") or payload.get("direction") or "").upper()
    if direction in {"CALL", "BUY", "UP", "LONG"}:
        return "BUY"
    if direction in {"PUT", "SELL", "DOWN", "SHORT"}:
        return "SELL"
    return "BUY" if randbelow(2) == 0 else "SELL"


def _entry_price_from_payload(quote_payload: dict, analysis_payload: dict) -> Decimal | None:
    quote_price = extract_latest_price(quote_payload)
    if quote_price is not None:
        return _decimal_or_none(quote_price)
    return _decimal_or_none(analysis_payload.get("price"))


def create_mvp_trading_session(
    db: Session,
    *,
    created_by_telegram_id: int | None = None,
    start_at: datetime | None = None,
) -> TradingSession:
    now = datetime.utcnow()
    session_start = start_at or now + timedelta(minutes=MVP_SESSION_START_DELAY_MINUTES)
    session_end = session_start + timedelta(minutes=MVP_SESSION_DURATION_MINUTES)
    entry_time = session_start + timedelta(seconds=MVP_SIGNAL_COUNTDOWN_SECONDS)
    close_time = entry_time + timedelta(seconds=MVP_EXPIRY_SECONDS)
    channel_id = get_signals_channel_id()

    quote_payload = get_quote(MVP_CATEGORY, MVP_SYMBOL, history_seconds=300)
    analysis_payload = get_combined_analysis(MVP_ANALYSIS_SYMBOL, MVP_EXPIRY_MINUTES)
    direction = _direction_from_payload(analysis_payload)
    confidence = _confidence_from_payload(analysis_payload)
    current_price = _entry_price_from_payload(quote_payload, analysis_payload)

    trading_session = TradingSession(
        channel_id=channel_id,
        market_mode=MVP_MARKET_MODE,
        status="scheduled",
        starts_at=session_start,
        ends_at=session_end,
        expiry_seconds=MVP_EXPIRY_SECONDS,
        base_amount=Decimal("0"),
        max_overlaps=MVP_MAX_OVERLAPS,
        min_payout=MVP_MIN_PAYOUT,
        min_confidence=MVP_MIN_CONFIDENCE,
        created_by_telegram_id=created_by_telegram_id,
        notes="MVP hardcoded session",
    )
    db.add(trading_session)
    db.flush()

    signal = TradingSignal(
        session_id=trading_session.id,
        channel_id=channel_id,
        status="planned",
        market_type=MVP_MARKET_MODE,
        category=MVP_CATEGORY,
        symbol=MVP_SYMBOL,
        flag_1=MVP_FLAG_1,
        flag_2=MVP_FLAG_2,
        direction=direction,
        direction_source=str(analysis_payload.get("decision_source") or analysis_payload.get("mode") or "devsbite"),
        decision_reason=str(analysis_payload.get("decision_reason") or analysis_payload.get("reason") or ""),
        confidence=confidence,
        expiry_seconds=MVP_EXPIRY_SECONDS,
        entry_time=entry_time,
        close_time=close_time,
        max_attempts=MVP_MAX_OVERLAPS + 1,
        source_payload={
            "mode": "mvp_hardcoded",
            "created_price": str(current_price) if current_price is not None else None,
            "quote": quote_payload,
            "analysis": analysis_payload,
        },
    )
    db.add(signal)
    db.flush()

    attempt = TradingSignalAttempt(
        signal_id=signal.id,
        attempt_no=0,
        kind="base",
        status="planned",
        direction=direction,
        expiry_seconds=MVP_EXPIRY_SECONDS,
        entry_time=entry_time,
        close_time=close_time,
        quote_snapshot=quote_payload,
    )
    db.add(attempt)
    db.flush()

    jobs = [
        TradingSignalJob(
            session_id=trading_session.id,
            kind="SESSION_SOON",
            status="scheduled",
            run_at=now,
            payload={"minutes_before": MVP_SESSION_START_DELAY_MINUTES},
        ),
        TradingSignalJob(
            session_id=trading_session.id,
            signal_id=signal.id,
            kind="SIGNAL_COUNTDOWN",
            status="scheduled",
            run_at=max(now, entry_time - timedelta(seconds=MVP_SIGNAL_COUNTDOWN_SECONDS)),
            payload={"seconds_before": MVP_SIGNAL_COUNTDOWN_SECONDS},
        ),
        TradingSignalJob(
            session_id=trading_session.id,
            signal_id=signal.id,
            attempt_id=attempt.id,
            kind="SIGNAL_ENTRY",
            status="scheduled",
            run_at=entry_time,
            payload={},
        ),
        TradingSignalJob(
            session_id=trading_session.id,
            signal_id=signal.id,
            attempt_id=attempt.id,
            kind="SIGNAL_RESULT",
            status="scheduled",
            run_at=close_time,
            payload={},
        ),
        TradingSignalJob(
            session_id=trading_session.id,
            kind="SESSION_FINISHED",
            status="scheduled",
            run_at=session_end,
            payload={},
        ),
    ]
    db.add_all(jobs)
    db.commit()
    db.refresh(trading_session)
    return trading_session


def format_mvp_session_summary(session: TradingSession) -> str:
    signal = session.signals[0] if session.signals else None
    direction = signal.direction if signal is not None else "-"
    confidence = signal.confidence if signal is not None else "-"
    source_payload = signal.source_payload if signal is not None and isinstance(signal.source_payload, dict) else {}
    price = source_payload.get("created_price") or "-"
    return (
        f"<b>MVP trading session created</b>\n"
        f"ID: <code>{session.id}</code>\n"
        f"Channel: <code>{session.channel_id}</code>\n"
        f"Market: <b>{session.market_mode}</b>\n"
        f"Symbol: <b>{MVP_SYMBOL}</b>\n"
        f"Direction: <b>{direction}</b>\n"
        f"Confidence: <b>{confidence}%</b>\n"
        f"Entry price: <code>{price}</code>\n"
        f"Start: <code>{session.starts_at.isoformat(sep=' ', timespec='seconds')} UTC</code>\n"
        f"End: <code>{session.ends_at.isoformat(sep=' ', timespec='seconds')} UTC</code>\n"
        f"Expiry: <b>{MVP_EXPIRY_SECONDS}s</b>\n"
        f"Jobs: <b>5</b>"
    )
