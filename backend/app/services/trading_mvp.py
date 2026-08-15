from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal
from secrets import randbelow

from sqlalchemy.orm import Session

from app.config import settings
from app.models.trading import TradingSession, TradingSignal, TradingSignalAttempt, TradingSignalJob
from app.services.devsbite import extract_instruments, extract_latest_price, get_combined_analysis, get_pairs, get_quote
from app.services.signal_time import format_signal_time

MVP_DEFAULT_MARKET_MODE = "FOREX"
MVP_MARKET_MODES = ("FOREX", "OTC", "MIXED")
MVP_EXPIRY_SECONDS = 180
MVP_EXPIRY_MINUTES = 3
MVP_MIN_PAYOUT = 80
MVP_BASE_AMOUNT = Decimal("1000")
MVP_MIN_CONFIDENCE = 40
MVP_MAX_OVERLAPS = 3
MVP_OVERLAP_MULTIPLIER = Decimal("2")
MVP_SESSION_DURATION_MINUTES = 60
MVP_SESSION_START_DELAY_MINUTES = 60
MVP_SIGNAL_COUNTDOWN_SECONDS = 60
MVP_EXPIRY_MINUTE_OPTIONS = (1, 3, 5, 15)
MVP_EXPIRY_SECOND_OPTIONS = tuple(minutes * 60 for minutes in MVP_EXPIRY_MINUTE_OPTIONS)
MVP_MAX_BASE_AMOUNT = Decimal("1000000")
MVP_MAX_ALLOWED_OVERLAPS = 10
MVP_MAX_OVERLAP_MULTIPLIER = Decimal("10")
ACTIVE_SESSION_STATUSES = ("scheduled", "running")
OPEN_JOB_STATUSES = ("scheduled", "processing")


@dataclass(frozen=True)
class MvpPairOption:
    code: str
    symbol: str
    flag_1: str
    flag_2: str
    market_type: str = "FOREX"
    category: str = "forex"


_CURRENCY_FLAGS = {
    "AED": "\U0001f1e6\U0001f1ea",
    "ARS": "\U0001f1e6\U0001f1f7",
    "AUD": "\U0001f1e6\U0001f1fa",
    "BDT": "\U0001f1e7\U0001f1e9",
    "BHD": "\U0001f1e7\U0001f1ed",
    "BRL": "\U0001f1e7\U0001f1f7",
    "CAD": "\U0001f1e8\U0001f1e6",
    "CHF": "\U0001f1e8\U0001f1ed",
    "CLP": "\U0001f1e8\U0001f1f1",
    "CNH": "\U0001f1e8\U0001f1f3",
    "CNY": "\U0001f1e8\U0001f1f3",
    "COP": "\U0001f1e8\U0001f1f4",
    "DZD": "\U0001f1e9\U0001f1ff",
    "EGP": "\U0001f1ea\U0001f1ec",
    "EUR": "\U0001f1ea\U0001f1fa",
    "GBP": "\U0001f1ec\U0001f1e7",
    "HUF": "\U0001f1ed\U0001f1fa",
    "IDR": "\U0001f1ee\U0001f1e9",
    "INR": "\U0001f1ee\U0001f1f3",
    "JOD": "\U0001f1ef\U0001f1f4",
    "JPY": "\U0001f1ef\U0001f1f5",
    "KES": "\U0001f1f0\U0001f1ea",
    "LBP": "\U0001f1f1\U0001f1e7",
    "MAD": "\U0001f1f2\U0001f1e6",
    "MXN": "\U0001f1f2\U0001f1fd",
    "MYR": "\U0001f1f2\U0001f1fe",
    "NGN": "\U0001f1f3\U0001f1ec",
    "NOK": "\U0001f1f3\U0001f1f4",
    "NZD": "\U0001f1f3\U0001f1ff",
    "OMR": "\U0001f1f4\U0001f1f2",
    "PHP": "\U0001f1f5\U0001f1ed",
    "PKR": "\U0001f1f5\U0001f1f0",
    "QAR": "\U0001f1f6\U0001f1e6",
    "RUB": "\U0001f1f7\U0001f1fa",
    "SAR": "\U0001f1f8\U0001f1e6",
    "SGD": "\U0001f1f8\U0001f1ec",
    "THB": "\U0001f1f9\U0001f1ed",
    "TND": "\U0001f1f9\U0001f1f3",
    "TRY": "\U0001f1f9\U0001f1f7",
    "UAH": "\U0001f1fa\U0001f1e6",
    "USD": "\U0001f1fa\U0001f1f8",
    "VND": "\U0001f1fb\U0001f1f3",
    "YER": "\U0001f1fe\U0001f1ea",
    "ZAR": "\U0001f1ff\U0001f1e6",
}

_FOREX_SYMBOLS = (
    "GBP/JPY",
    "EUR/JPY",
    "AUD/CAD",
    "AUD/CHF",
    "AUD/JPY",
    "AUD/USD",
    "CAD/CHF",
    "CHF/JPY",
    "EUR/AUD",
    "EUR/CAD",
    "EUR/CHF",
    "EUR/USD",
    "GBP/AUD",
    "GBP/CAD",
    "GBP/CHF",
    "USD/CAD",
    "USD/CHF",
    "USD/JPY",
    "CAD/JPY",
    "EUR/GBP",
    "GBP/USD",
)

_OTC_SYMBOLS = (
    "AED/CNY OTC",
    "AUD/CAD OTC",
    "AUD/NZD OTC",
    "AUD/USD OTC",
    "BHD/CNY OTC",
    "CAD/CHF OTC",
    "CAD/JPY OTC",
    "CHF/JPY OTC",
    "CHF/NOK OTC",
    "EUR/CHF OTC",
    "EUR/NZD OTC",
    "EUR/TRY OTC",
    "JOD/CNY OTC",
    "KES/USD OTC",
    "NZD/USD OTC",
    "OMR/CNY OTC",
    "SAR/CNY OTC",
    "UAH/USD OTC",
    "USD/ARS OTC",
    "USD/BRL OTC",
    "USD/DZD OTC",
    "USD/EGP OTC",
    "USD/INR OTC",
    "USD/MXN OTC",
    "USD/MYR OTC",
    "USD/PKR OTC",
    "USD/VND OTC",
    "ZAR/USD OTC",
    "EUR/USD OTC",
    "MAD/USD OTC",
    "EUR/GBP OTC",
    "EUR/RUB OTC",
    "EUR/HUF OTC",
    "EUR/JPY OTC",
    "NGN/USD OTC",
    "TND/USD OTC",
    "USD/IDR OTC",
    "QAR/CNY OTC",
    "USD/CLP OTC",
    "USD/SGD OTC",
    "USD/PHP OTC",
    "USD/BDT OTC",
    "USD/CAD OTC",
    "USD/CHF OTC",
    "USD/THB OTC",
    "AUD/JPY OTC",
    "GBP/USD OTC",
    "GBP/AUD OTC",
    "USD/RUB OTC",
    "USD/COP OTC",
    "AUD/CHF OTC",
    "USD/CNH OTC",
    "USD/JPY OTC",
    "GBP/JPY OTC",
    "YER/USD OTC",
    "NZD/JPY OTC",
    "LBP/USD OTC",
)


def _pair_code(symbol: str, market_type: str) -> str:
    base = symbol.replace(" OTC", "").replace("/", "").replace(" ", "").upper()
    return f"{base}_OTC" if market_type == "OTC" else base


def _pair_flags(symbol: str) -> tuple[str, str]:
    base, quote = symbol.replace(" OTC", "").split("/", 1)
    return _CURRENCY_FLAGS.get(base, ""), _CURRENCY_FLAGS.get(quote, "")


def _build_pair_options(symbols: tuple[str, ...], *, market_type: str, category: str) -> tuple[MvpPairOption, ...]:
    return tuple(
        MvpPairOption(
            code=_pair_code(symbol, market_type),
            symbol=symbol,
            flag_1=_pair_flags(symbol)[0],
            flag_2=_pair_flags(symbol)[1],
            market_type=market_type,
            category=category,
        )
        for symbol in symbols
    )


MVP_FOREX_PAIR_OPTIONS = _build_pair_options(_FOREX_SYMBOLS, market_type="FOREX", category="forex")
MVP_OTC_PAIR_OPTIONS = _build_pair_options(_OTC_SYMBOLS, market_type="OTC", category="otc")
MVP_PAIR_OPTIONS = MVP_FOREX_PAIR_OPTIONS + MVP_OTC_PAIR_OPTIONS
MVP_PAIR_BY_CODE = {option.code: option for option in MVP_PAIR_OPTIONS}


class TradingMvpConfigError(RuntimeError):
    pass


def normalize_mvp_market_mode(value: str | None) -> str:
    market_mode = (value or MVP_DEFAULT_MARKET_MODE).strip().upper()
    if market_mode not in MVP_MARKET_MODES:
        raise ValueError(f"Unsupported MVP market mode: {value}")
    return market_mode


def get_mvp_pair_options(market_mode: str | None = None) -> tuple[MvpPairOption, ...]:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    if normalized_market_mode == "FOREX":
        return MVP_FOREX_PAIR_OPTIONS
    if normalized_market_mode == "OTC":
        return MVP_OTC_PAIR_OPTIONS
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


def _decimal_required(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise TradingMvpConfigError(f"{field_name} must be a number")
    try:
        decimal_value = Decimal(str(value))
    except Exception as error:
        raise TradingMvpConfigError(f"{field_name} must be a number") from error
    if not decimal_value.is_finite():
        raise TradingMvpConfigError(f"{field_name} must be finite")
    return decimal_value


def _int_required(value: object, field_name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise TradingMvpConfigError(f"{field_name} must be an integer")
    try:
        if isinstance(value, str) and value.strip() != str(int(value.strip())):
            raise ValueError
        integer_value = int(value)
    except Exception as error:
        raise TradingMvpConfigError(f"{field_name} must be an integer") from error
    return integer_value


def _validate_percent(value: object, field_name: str) -> Decimal:
    decimal_value = _decimal_required(value, field_name)
    if decimal_value < Decimal("0") or decimal_value > Decimal("100"):
        raise TradingMvpConfigError(f"{field_name} must be between 0 and 100")
    return decimal_value


def _payout_percent_or_none(value: object) -> Decimal | None:
    if isinstance(value, dict):
        for key in ("payout", "payout_percent", "profit", "profit_percent", "percent", "value"):
            payout = _payout_percent_or_none(value.get(key))
            if payout is not None:
                return payout
        return None

    payout = _decimal_or_none(value)  # type: ignore[arg-type]
    if payout is None:
        return None
    if Decimal("0") < payout <= Decimal("1"):
        payout *= Decimal("100")
    return payout


def _pair_match_key(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def _instrument_matches_pair(instrument: dict, pair: MvpPairOption) -> bool:
    target_keys = {_pair_match_key(pair.symbol), _pair_match_key(pair.code)}
    for key in ("symbol", "name", "pair", "ticker", "asset", "label", "title", "display_name"):
        value = instrument.get(key)
        if isinstance(value, str) and _pair_match_key(value) in target_keys:
            return True
    return False


def _instrument_payout(instrument: dict) -> Decimal | None:
    for key in (
        "payout",
        "payout_percent",
        "profit",
        "profit_percent",
        "return",
        "return_percent",
        "percent",
        "percentage",
    ):
        payout = _payout_percent_or_none(instrument.get(key))
        if payout is not None:
            return payout
    return None


def _pair_payout_from_devsbite(pair: MvpPairOption) -> Decimal:
    payload = get_pairs(pair.market_type.lower(), min_payout=0)
    for instrument in extract_instruments(payload):
        if not _instrument_matches_pair(instrument, pair):
            continue
        payout = _instrument_payout(instrument)
        if payout is None:
            raise TradingMvpConfigError(f"Devsbite pair {pair.symbol} has no payout field")
        if payout < Decimal(str(MVP_MIN_PAYOUT)):
            raise TradingMvpConfigError(
                f"Pair {pair.symbol} payout is {payout}% but minimum is {MVP_MIN_PAYOUT}%"
            )
        return payout

    raise TradingMvpConfigError(f"Pair {pair.symbol} was not found in Devsbite pairs")


def get_mvp_pair_options_with_payout(
    market_mode: str | None = None,
    *,
    min_payout: int = MVP_MIN_PAYOUT,
) -> tuple[tuple[MvpPairOption, Decimal], ...]:
    normalized_market_mode = normalize_mvp_market_mode(market_mode)
    pair_options = get_mvp_pair_options(normalized_market_mode)
    instruments_by_market: dict[str, list[dict]] = {}

    for market_type in sorted({pair.market_type for pair in pair_options}):
        payload = get_pairs(market_type.lower(), min_payout=min_payout)
        instruments_by_market[market_type] = extract_instruments(payload)

    pairs_with_payout: list[tuple[MvpPairOption, Decimal]] = []
    for pair in pair_options:
        for instrument in instruments_by_market.get(pair.market_type, []):
            if not _instrument_matches_pair(instrument, pair):
                continue
            payout = _instrument_payout(instrument)
            if payout is not None and payout >= Decimal(str(min_payout)):
                pairs_with_payout.append((pair, payout))
            break

    return tuple(pairs_with_payout)


def _confidence_from_payload(payload: dict) -> Decimal:
    confidence = _decimal_or_none(payload.get("confidence"))
    if confidence is not None and Decimal("0") <= confidence <= Decimal("100"):
        return confidence
    raise TradingMvpConfigError(f"Devsbite returned invalid confidence: {payload.get('confidence')!r}")


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
    expiry_minutes = _int_required(expiry_minutes, "expiry_minutes")
    if expiry_minutes not in MVP_EXPIRY_MINUTE_OPTIONS:
        raise ValueError(f"Unsupported MVP expiry: {expiry_minutes}")

    quote_payload = get_quote(pair.category, pair.symbol, history_seconds=300)
    analysis_payload = get_combined_analysis(pair.symbol, expiry_minutes)
    direction = _direction_from_payload(analysis_payload)
    confidence = _confidence_from_payload(analysis_payload)
    payout = _pair_payout_from_devsbite(pair)
    current_price = _entry_price_from_payload(quote_payload, analysis_payload)

    return {
        "pair": pair,
        "expiry_minutes": expiry_minutes,
        "expiry_seconds": expiry_minutes * 60,
        "quote": quote_payload,
        "analysis": analysis_payload,
        "direction": direction,
        "confidence": confidence,
        "payout": payout,
        "entry_price": current_price,
    }


def validate_mvp_session_inputs(
    *,
    starts_at: datetime,
    ends_at: datetime,
    entry_time: datetime,
    close_time: datetime,
    expiry_seconds: object,
    base_amount: object,
    max_overlaps: object,
    overlap_multiplier: object,
    min_payout: object,
    min_confidence: object,
    confidence: object,
    payout: object,
) -> dict[str, Decimal | int]:
    for field_name, value in (
        ("starts_at", starts_at),
        ("ends_at", ends_at),
        ("entry_time", entry_time),
        ("close_time", close_time),
    ):
        if not isinstance(value, datetime):
            raise TradingMvpConfigError(f"{field_name} must be a datetime")
        if value.tzinfo is not None and value.utcoffset() is not None:
            raise TradingMvpConfigError(f"{field_name} must be a naive UTC datetime")

    current_time = datetime.utcnow()
    if starts_at < current_time - timedelta(minutes=1):
        raise TradingMvpConfigError("Session start time cannot be in the past")
    if ends_at <= current_time:
        raise TradingMvpConfigError("Session end time must be in the future")
    if starts_at >= ends_at:
        raise TradingMvpConfigError("Session start time must be earlier than end time")
    if entry_time < starts_at:
        raise TradingMvpConfigError("Signal entry time cannot be earlier than session start time")
    if close_time <= entry_time:
        raise TradingMvpConfigError("Signal close time must be later than entry time")
    if close_time > ends_at:
        raise TradingMvpConfigError("Signal close time cannot be later than session end time")

    normalized_expiry_seconds = _int_required(expiry_seconds, "expiry_seconds")
    if normalized_expiry_seconds not in MVP_EXPIRY_SECOND_OPTIONS:
        allowed = ", ".join(str(value) for value in MVP_EXPIRY_SECOND_OPTIONS)
        raise TradingMvpConfigError(f"expiry_seconds must be one of: {allowed}")

    normalized_base_amount = _decimal_required(base_amount, "base_amount")
    if normalized_base_amount <= Decimal("0"):
        raise TradingMvpConfigError("base_amount must be greater than 0")
    if normalized_base_amount > MVP_MAX_BASE_AMOUNT:
        raise TradingMvpConfigError(f"base_amount must be less than or equal to {MVP_MAX_BASE_AMOUNT}")

    normalized_max_overlaps = _int_required(max_overlaps, "max_overlaps")
    if normalized_max_overlaps < 0 or normalized_max_overlaps > MVP_MAX_ALLOWED_OVERLAPS:
        raise TradingMvpConfigError(f"max_overlaps must be between 0 and {MVP_MAX_ALLOWED_OVERLAPS}")

    normalized_overlap_multiplier = _decimal_required(overlap_multiplier, "overlap_multiplier")
    if normalized_overlap_multiplier <= Decimal("1") or normalized_overlap_multiplier > MVP_MAX_OVERLAP_MULTIPLIER:
        raise TradingMvpConfigError(
            f"overlap_multiplier must be greater than 1 and less than or equal to {MVP_MAX_OVERLAP_MULTIPLIER}"
        )

    normalized_min_payout = _validate_percent(min_payout, "min_payout")
    normalized_min_confidence = _validate_percent(min_confidence, "min_confidence")
    normalized_confidence = _validate_percent(confidence, "confidence")
    normalized_payout = _validate_percent(payout, "payout")

    if normalized_payout < normalized_min_payout:
        raise TradingMvpConfigError(f"payout {normalized_payout}% is lower than minimum {normalized_min_payout}%")
    if normalized_confidence < normalized_min_confidence:
        raise TradingMvpConfigError(
            f"confidence {normalized_confidence}% is lower than minimum {normalized_min_confidence}%"
        )

    return {
        "expiry_seconds": normalized_expiry_seconds,
        "base_amount": normalized_base_amount,
        "max_overlaps": normalized_max_overlaps,
        "overlap_multiplier": normalized_overlap_multiplier,
        "min_payout": normalized_min_payout,
        "min_confidence": normalized_min_confidence,
        "confidence": normalized_confidence,
        "payout": normalized_payout,
    }


def cancel_open_channel_sessions(db: Session, channel_id: int) -> int:
    open_sessions = (
        db.query(TradingSession)
        .filter(
            TradingSession.channel_id == channel_id,
            TradingSession.status.in_(ACTIVE_SESSION_STATUSES),
        )
        .all()
    )
    if not open_sessions:
        return 0

    session_ids = [session.id for session in open_sessions]
    now = datetime.utcnow()
    for session in open_sessions:
        session.status = "cancelled"
        session.updated_at = now

    db.query(TradingSignal).filter(TradingSignal.session_id.in_(session_ids), TradingSignal.status != "finished").update(
        {"status": "cancelled", "updated_at": now},
        synchronize_session=False,
    )
    db.query(TradingSignalAttempt).filter(
        TradingSignalAttempt.signal_id.in_(
            db.query(TradingSignal.id).filter(TradingSignal.session_id.in_(session_ids))
        ),
        TradingSignalAttempt.status != "finished",
    ).update(
        {"status": "cancelled", "updated_at": now},
        synchronize_session=False,
    )
    db.query(TradingSignalJob).filter(
        TradingSignalJob.session_id.in_(session_ids),
        TradingSignalJob.status.in_(OPEN_JOB_STATUSES),
    ).update(
        {
            "status": "cancelled",
            "last_error": "Cancelled because a newer MVP session was created for this channel.",
            "lock_token": "",
            "locked_at": None,
            "updated_at": now,
        },
        synchronize_session=False,
    )
    return len(open_sessions)


def cancel_trading_session(
    db: Session,
    session_id: int,
    *,
    reason: str,
    allowed_statuses: tuple[str, ...] = ACTIVE_SESSION_STATUSES,
) -> TradingSession:
    trading_session = db.query(TradingSession).filter(TradingSession.id == session_id).first()
    if trading_session is None:
        raise TradingMvpConfigError(f"Trading session #{session_id} was not found.")

    if trading_session.status not in allowed_statuses:
        allowed = ", ".join(allowed_statuses)
        raise TradingMvpConfigError(
            f"Trading session #{session_id} has status '{trading_session.status}', expected: {allowed}."
        )

    now = datetime.utcnow()
    trading_session.status = "cancelled"
    trading_session.updated_at = now
    note = f"{now.isoformat(timespec='seconds')} UTC: {reason}"
    trading_session.notes = f"{trading_session.notes}\n{note}".strip() if trading_session.notes else note

    signal_ids = [
        signal_id
        for (signal_id,) in db.query(TradingSignal.id)
        .filter(TradingSignal.session_id == trading_session.id)
        .all()
    ]

    db.query(TradingSignal).filter(
        TradingSignal.session_id == trading_session.id,
        TradingSignal.status != "finished",
    ).update(
        {"status": "cancelled", "updated_at": now},
        synchronize_session=False,
    )

    if signal_ids:
        db.query(TradingSignalAttempt).filter(
            TradingSignalAttempt.signal_id.in_(signal_ids),
            TradingSignalAttempt.status != "finished",
        ).update(
            {"status": "cancelled", "updated_at": now},
            synchronize_session=False,
        )

    db.query(TradingSignalJob).filter(
        TradingSignalJob.session_id == trading_session.id,
        TradingSignalJob.status.in_(OPEN_JOB_STATUSES),
    ).update(
        {
            "status": "cancelled",
            "last_error": reason,
            "lock_token": "",
            "locked_at": None,
            "updated_at": now,
        },
        synchronize_session=False,
    )

    db.commit()
    db.refresh(trading_session)
    return trading_session


def create_mvp_trading_session(
    db: Session,
    *,
    created_by_telegram_id: int | None = None,
    start_at: datetime | None = None,
    pair: MvpPairOption | None = None,
    market_mode: str = MVP_DEFAULT_MARKET_MODE,
    expiry_minutes: int = MVP_EXPIRY_MINUTES,
    base_amount: Decimal = MVP_BASE_AMOUNT,
    max_overlaps: int = MVP_MAX_OVERLAPS,
    overlap_multiplier: Decimal = MVP_OVERLAP_MULTIPLIER,
    min_payout: int = MVP_MIN_PAYOUT,
    min_confidence: int = MVP_MIN_CONFIDENCE,
    preview: dict | None = None,
) -> TradingSession:
    now = datetime.utcnow()
    market_mode = normalize_mvp_market_mode(market_mode)
    pair = pair or get_mvp_pair_options(market_mode)[0]
    if pair not in get_mvp_pair_options(market_mode):
        raise ValueError(f"Pair {pair.symbol} is not allowed for market mode {market_mode}")
    expiry_minutes = _int_required(expiry_minutes, "expiry_minutes")
    if expiry_minutes not in MVP_EXPIRY_MINUTE_OPTIONS:
        raise TradingMvpConfigError(f"Unsupported MVP expiry: {expiry_minutes}")
    expiry_seconds = expiry_minutes * 60
    session_start = start_at or now + timedelta(minutes=MVP_SESSION_START_DELAY_MINUTES)
    session_end = session_start + timedelta(minutes=MVP_SESSION_DURATION_MINUTES)
    entry_time = session_start + timedelta(seconds=MVP_SIGNAL_COUNTDOWN_SECONDS)
    close_time = entry_time + timedelta(seconds=expiry_seconds)

    if preview is None:
        preview = preview_mvp_trading_signal(pair, expiry_minutes)
    preview_pair = preview.get("pair")
    if preview_pair != pair:
        raise TradingMvpConfigError("Preview pair does not match selected pair")
    preview_expiry_minutes = _int_required(preview.get("expiry_minutes"), "preview.expiry_minutes")
    if preview_expiry_minutes != expiry_minutes:
        raise TradingMvpConfigError("Preview expiry does not match selected expiry")

    quote_payload = preview["quote"]
    analysis_payload = preview["analysis"]
    direction = preview["direction"]
    confidence = preview["confidence"]
    payout = preview["payout"]
    current_price = preview["entry_price"]
    if direction not in {"BUY", "SELL"}:
        raise TradingMvpConfigError(f"Unsupported direction: {direction!r}")
    normalized_values = validate_mvp_session_inputs(
        starts_at=session_start,
        ends_at=session_end,
        entry_time=entry_time,
        close_time=close_time,
        expiry_seconds=expiry_seconds,
        base_amount=base_amount,
        max_overlaps=max_overlaps,
        overlap_multiplier=overlap_multiplier,
        min_payout=min_payout,
        min_confidence=min_confidence,
        confidence=confidence,
        payout=payout,
    )

    channel_id = get_signals_channel_id()
    cancel_open_channel_sessions(db, channel_id)

    trading_session = TradingSession(
        channel_id=channel_id,
        market_mode=market_mode,
        status="scheduled",
        starts_at=session_start,
        ends_at=session_end,
        expiry_seconds=normalized_values["expiry_seconds"],
        base_amount=normalized_values["base_amount"],
        max_overlaps=normalized_values["max_overlaps"],
        min_payout=int(normalized_values["min_payout"]),
        min_confidence=int(normalized_values["min_confidence"]),
        created_by_telegram_id=created_by_telegram_id,
        notes=f"MVP {market_mode} admin selected session",
    )
    db.add(trading_session)
    db.flush()

    signal = TradingSignal(
        session_id=trading_session.id,
        channel_id=channel_id,
        status="planned",
        market_type=pair.market_type,
        category=pair.category,
        symbol=pair.symbol,
        flag_1=pair.flag_1,
        flag_2=pair.flag_2,
        direction=direction,
        direction_source=str(analysis_payload.get("decision_source") or analysis_payload.get("mode") or "devsbite"),
        decision_reason=str(analysis_payload.get("decision_reason") or analysis_payload.get("reason") or ""),
        confidence=normalized_values["confidence"],
        payout=normalized_values["payout"],
        expiry_seconds=normalized_values["expiry_seconds"],
        entry_time=entry_time,
        close_time=close_time,
        max_attempts=int(normalized_values["max_overlaps"]) + 1,
        source_payload={
            "mode": "mvp_admin_selected",
            "market_mode": market_mode,
            "created_price": str(current_price) if current_price is not None else None,
            "pair_code": pair.code,
            "expiry_minutes": expiry_minutes,
            "payout": str(payout),
            "overlap_multiplier": str(normalized_values["overlap_multiplier"]),
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
        expiry_seconds=normalized_values["expiry_seconds"],
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
    payout = signal.payout if signal is not None else "-"
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
        f"Payout: <b>{payout}%</b>\n"
        f"Entry price: <code>{price}</code>\n"
        f"Start: <code>{format_signal_time(session.starts_at)} MSK</code>\n"
        f"End: <code>{format_signal_time(session.ends_at)} MSK</code>\n"
        f"Expiry: <b>{session.expiry_seconds}s</b>\n"
        f"Jobs: <b>5</b>"
    )
