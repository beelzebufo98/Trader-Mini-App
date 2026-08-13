from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal
from secrets import randbelow

from sqlalchemy.orm import Session

from app.config import settings
from app.models.trading import TradingSession, TradingSignal, TradingSignalAttempt, TradingSignalJob
from app.services.devsbite import extract_latest_price, get_combined_analysis, get_quote

MVP_MARKET_MODE = "FOREX"
MVP_CATEGORY = "forex"
MVP_SYMBOL = "EUR/USD"
MVP_ANALYSIS_SYMBOL = "EUR/USD"
MVP_FLAG_1 = "\U0001f1ea\U0001f1fa"
MVP_FLAG_2 = "\U0001f1fa\U0001f1f8"
MVP_EXPIRY_SECONDS = 180
MVP_EXPIRY_MINUTES = 3
MVP_MIN_PAYOUT = 80
MVP_MIN_CONFIDENCE = 40
MVP_FALLBACK_CONFIDENCE_MIN = 70
MVP_MAX_OVERLAPS = 3
MVP_SESSION_DURATION_MINUTES = 60
MVP_SESSION_START_DELAY_MINUTES = 60
MVP_SIGNAL_COUNTDOWN_SECONDS = 60
MVP_EXPIRY_MINUTE_OPTIONS = (1, 3, 5, 15)


@dataclass(frozen=True)
class MvpPairOption:
    code: str
    symbol: str
    flag_1: str
    flag_2: str


MVP_PAIR_OPTIONS = (
    MvpPairOption("GBPJPY", "GBP/JPY", "\U0001f1ec\U0001f1e7", "\U0001f1ef\U0001f1f5"),
    MvpPairOption("EURJPY", "EUR/JPY", "\U0001f1ea\U0001f1fa", "\U0001f1ef\U0001f1f5"),
    MvpPairOption("AUDCAD", "AUD/CAD", "\U0001f1e6\U0001f1fa", "\U0001f1e8\U0001f1e6"),
    MvpPairOption("AUDCHF", "AUD/CHF", "\U0001f1e6\U0001f1fa", "\U0001f1e8\U0001f1ed"),
    MvpPairOption("AUDJPY", "AUD/JPY", "\U0001f1e6\U0001f1fa", "\U0001f1ef\U0001f1f5"),
    MvpPairOption("AUDUSD", "AUD/USD", "\U0001f1e6\U0001f1fa", "\U0001f1fa\U0001f1f8"),
    MvpPairOption("CADCHF", "CAD/CHF", "\U0001f1e8\U0001f1e6", "\U0001f1e8\U0001f1ed"),
    MvpPairOption("CHFJPY", "CHF/JPY", "\U0001f1e8\U0001f1ed", "\U0001f1ef\U0001f1f5"),
    MvpPairOption("EURAUD", "EUR/AUD", "\U0001f1ea\U0001f1fa", "\U0001f1e6\U0001f1fa"),
    MvpPairOption("EURCAD", "EUR/CAD", "\U0001f1ea\U0001f1fa", "\U0001f1e8\U0001f1e6"),
    MvpPairOption("EURCHF", "EUR/CHF", "\U0001f1ea\U0001f1fa", "\U0001f1e8\U0001f1ed"),
    MvpPairOption("EURUSD", "EUR/USD", "\U0001f1ea\U0001f1fa", "\U0001f1fa\U0001f1f8"),
    MvpPairOption("GBPAUD", "GBP/AUD", "\U0001f1ec\U0001f1e7", "\U0001f1e6\U0001f1fa"),
    MvpPairOption("GBPCAD", "GBP/CAD", "\U0001f1ec\U0001f1e7", "\U0001f1e8\U0001f1e6"),
    MvpPairOption("GBPCHF", "GBP/CHF", "\U0001f1ec\U0001f1e7", "\U0001f1e8\U0001f1ed"),
    MvpPairOption("USDCAD", "USD/CAD", "\U0001f1fa\U0001f1f8", "\U0001f1e8\U0001f1e6"),
    MvpPairOption("USDCHF", "USD/CHF", "\U0001f1fa\U0001f1f8", "\U0001f1e8\U0001f1ed"),
    MvpPairOption("USDJPY", "USD/JPY", "\U0001f1fa\U0001f1f8", "\U0001f1ef\U0001f1f5"),
    MvpPairOption("CADJPY", "CAD/JPY", "\U0001f1e8\U0001f1e6", "\U0001f1ef\U0001f1f5"),
    MvpPairOption("EURGBP", "EUR/GBP", "\U0001f1ea\U0001f1fa", "\U0001f1ec\U0001f1e7"),
    MvpPairOption("GBPUSD", "GBP/USD", "\U0001f1ec\U0001f1e7", "\U0001f1fa\U0001f1f8"),
)
MVP_PAIR_BY_CODE = {option.code: option for option in MVP_PAIR_OPTIONS}


class TradingMvpConfigError(RuntimeError):
    pass


def get_mvp_pair_options() -> tuple[MvpPairOption, ...]:
    return MVP_PAIR_OPTIONS


def get_mvp_pair_option(code: str) -> MvpPairOption:
    try:
        return MVP_PAIR_BY_CODE[code]
    except KeyError as error:
        raise ValueError(f"Unsupported MVP pair code: {code}") from error


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
    if confidence is not None and Decimal(str(MVP_MIN_CONFIDENCE)) <= confidence <= Decimal("100"):
        return confidence
    return Decimal(str(MVP_FALLBACK_CONFIDENCE_MIN + randbelow(31)))


def _direction_from_payload(payload: dict) -> str:
    direction = str(payload.get("signal") or payload.get("direction") or "").upper()
    if direction in {"CALL", "BUY", "UP", "LONG"}:
        return "BUY"
    if direction in {"PUT", "SELL", "DOWN", "SHORT"}:
        return "SELL"
    tv_recommendation = str(payload.get("tv_recommendation") or "").upper()
    td_recommendation = str(payload.get("td_recommendation") or "").upper()
    if tv_recommendation == td_recommendation == "BUY":
        return "BUY"
    if tv_recommendation == td_recommendation == "SELL":
        return "SELL"
    return "BUY" if randbelow(2) == 0 else "SELL"


def _entry_price_from_payload(quote_payload: dict, analysis_payload: dict) -> Decimal | None:
    quote_price = extract_latest_price(quote_payload)
    if quote_price is not None:
        return _decimal_or_none(quote_price)
    return _decimal_or_none(analysis_payload.get("price"))


def preview_mvp_trading_signal(pair: MvpPairOption, expiry_minutes: int) -> dict:
    if expiry_minutes not in MVP_EXPIRY_MINUTE_OPTIONS:
        raise ValueError(f"Unsupported MVP expiry: {expiry_minutes}")

    quote_payload = get_quote(MVP_CATEGORY, pair.symbol, history_seconds=300)
    analysis_payload = get_combined_analysis(pair.symbol, expiry_minutes)
    direction = _direction_from_payload(analysis_payload)
    confidence = _confidence_from_payload(analysis_payload)
    current_price = _entry_price_from_payload(quote_payload, analysis_payload)

    return {
        "pair": pair,
        "expiry_minutes": expiry_minutes,
        "expiry_seconds": expiry_minutes * 60,
        "quote": quote_payload,
        "analysis": analysis_payload,
        "direction": direction,
        "confidence": confidence,
        "entry_price": current_price,
    }


def create_mvp_trading_session(
    db: Session,
    *,
    created_by_telegram_id: int | None = None,
    start_at: datetime | None = None,
    pair: MvpPairOption | None = None,
    expiry_minutes: int = MVP_EXPIRY_MINUTES,
    preview: dict | None = None,
) -> TradingSession:
    now = datetime.utcnow()
    pair = pair or MVP_PAIR_BY_CODE["EURUSD"]
    expiry_seconds = expiry_minutes * 60
    session_start = start_at or now + timedelta(minutes=MVP_SESSION_START_DELAY_MINUTES)
    session_end = session_start + timedelta(minutes=MVP_SESSION_DURATION_MINUTES)
    entry_time = session_start + timedelta(seconds=MVP_SIGNAL_COUNTDOWN_SECONDS)
    close_time = entry_time + timedelta(seconds=expiry_seconds)
    channel_id = get_signals_channel_id()

    if preview is None:
        preview = preview_mvp_trading_signal(pair, expiry_minutes)
    quote_payload = preview["quote"]
    analysis_payload = preview["analysis"]
    direction = preview["direction"]
    confidence = preview["confidence"]
    current_price = preview["entry_price"]

    trading_session = TradingSession(
        channel_id=channel_id,
        market_mode=MVP_MARKET_MODE,
        status="scheduled",
        starts_at=session_start,
        ends_at=session_end,
        expiry_seconds=expiry_seconds,
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
        symbol=pair.symbol,
        flag_1=pair.flag_1,
        flag_2=pair.flag_2,
        direction=direction,
        direction_source=str(analysis_payload.get("decision_source") or analysis_payload.get("mode") or "devsbite"),
        decision_reason=str(analysis_payload.get("decision_reason") or analysis_payload.get("reason") or ""),
        confidence=confidence,
        expiry_seconds=expiry_seconds,
        entry_time=entry_time,
        close_time=close_time,
        max_attempts=MVP_MAX_OVERLAPS + 1,
        source_payload={
            "mode": "mvp_admin_selected",
            "created_price": str(current_price) if current_price is not None else None,
            "pair_code": pair.code,
            "expiry_minutes": expiry_minutes,
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
        expiry_seconds=expiry_seconds,
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
    symbol = signal.symbol if signal is not None else "-"
    source_payload = signal.source_payload if signal is not None and isinstance(signal.source_payload, dict) else {}
    price = source_payload.get("created_price") or "-"
    return (
        f"<b>MVP trading session created</b>\n"
        f"ID: <code>{session.id}</code>\n"
        f"Channel: <code>{session.channel_id}</code>\n"
        f"Market: <b>{session.market_mode}</b>\n"
        f"Symbol: <b>{symbol}</b>\n"
        f"Direction: <b>{direction}</b>\n"
        f"Confidence: <b>{confidence}%</b>\n"
        f"Entry price: <code>{price}</code>\n"
        f"Start: <code>{session.starts_at.isoformat(sep=' ', timespec='seconds')} UTC</code>\n"
        f"End: <code>{session.ends_at.isoformat(sep=' ', timespec='seconds')} UTC</code>\n"
        f"Expiry: <b>{session.expiry_seconds}s</b>\n"
        f"Jobs: <b>5</b>"
    )
