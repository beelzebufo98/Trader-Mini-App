from datetime import datetime, timedelta
from decimal import Decimal
import threading
import time
import uuid

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.trading import TradingSession, TradingSignal, TradingSignalAttempt, TradingSignalJob
from app.services.devsbite import extract_latest_price, get_quote
from app.services.trading_chart_renderer import TradeChartData, render_trade_result_chart
from app.telegram.channel_signals import (
    SignalAsset,
    SignalEntry,
    SignalOutcome,
    send_overlap,
    send_session_finished,
    send_session_soon,
    send_signal_countdown,
    send_signal_entry,
    send_signal_result,
)

TRADING_SIGNAL_WORKER_POLL_SECONDS = 10
TRADING_SIGNAL_WORKER_BATCH_SIZE = 10
TRADING_SIGNAL_WORKER_MAX_ATTEMPTS = 3
TRADING_SIGNAL_WORKER_RETRY_SECONDS = 60
OPEN_JOB_STATUSES = ("scheduled", "processing")

_worker_lock = threading.Lock()
_worker_started = False


def _decimal_or_none(value: float | int | str | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _float_or_none(value: float | int | str | Decimal | None) -> float | None:
    decimal_value = _decimal_or_none(value)
    return float(decimal_value) if decimal_value is not None else None


def _signal_asset(signal: TradingSignal) -> SignalAsset:
    return SignalAsset(
        symbol=signal.symbol,
        market_type=signal.market_type,
        flag_1=signal.flag_1,
        flag_2=signal.flag_2,
    )


def _signal_entry(signal: TradingSignal, attempt: TradingSignalAttempt | None = None) -> SignalEntry:
    entry_source = attempt or signal
    return SignalEntry(
        asset=_signal_asset(signal),
        direction=signal.direction if signal.direction in {"BUY", "SELL"} else "BUY",
        entry_time=entry_source.entry_time or signal.entry_time or datetime.utcnow(),
        expiry_seconds=entry_source.expiry_seconds or signal.expiry_seconds,
        entry_price=_float_or_none(entry_source.entry_price or signal.entry_price),
    )


def _latest_price(signal: TradingSignal) -> tuple[Decimal, dict]:
    payload = get_quote(signal.category, signal.symbol, history_seconds=300)
    price = _decimal_or_none(extract_latest_price(payload))
    if price is None:
        raise RuntimeError("Devsbite returned quote without price")
    return price, payload


def _is_win(direction: str, entry_price: Decimal, close_price: Decimal) -> bool:
    if direction == "SELL":
        return close_price < entry_price
    return close_price > entry_price


def _render_result_chart(
    signal: TradingSignal,
    attempt: TradingSignalAttempt | None,
    *,
    direction: str,
    result: str,
    entry_price: Decimal,
    close_price: Decimal,
    history_payload: dict,
):
    session = signal.session
    trade_amount = _float_or_none(session.base_amount if session is not None else None) or 1000
    payout_percent = float(signal.payout or (session.min_payout if session is not None else 80) or 80)
    try:
        return render_trade_result_chart(
            TradeChartData(
                symbol=signal.symbol,
                market_type=signal.market_type,
                direction=direction,
                result=result,
                entry_time=(attempt.entry_time if attempt is not None else None) or signal.entry_time or datetime.utcnow(),
                close_time=(attempt.close_time if attempt is not None else None) or signal.close_time or datetime.utcnow(),
                expiry_seconds=(attempt.expiry_seconds if attempt is not None else None) or signal.expiry_seconds,
                entry_price=float(entry_price),
                close_price=float(close_price),
                trade_amount=trade_amount,
                payout_percent=payout_percent,
                flag_1=signal.flag_1,
                flag_2=signal.flag_2,
                history_payload=history_payload,
            )
        )
    except Exception as error:
        print(f"trading_result_chart_failed signal_id={signal.id} detail={error}")
        return None


def _next_overlap_run_at() -> datetime:
    return datetime.utcnow()


def _mark_session_running(session: TradingSession) -> None:
    if session.status == "scheduled":
        session.status = "running"


def _cancel_session_open_work(db: Session, session: TradingSession, reason: str) -> None:
    now = datetime.utcnow()
    session.status = "cancelled"
    session.updated_at = now
    for signal in session.signals:
        if signal.status != "finished":
            signal.status = "cancelled"
            signal.updated_at = now
        for attempt in signal.attempts:
            if attempt.status != "finished":
                attempt.status = "cancelled"
                attempt.updated_at = now

    (
        db.query(TradingSignalJob)
        .filter(
            TradingSignalJob.session_id == session.id,
            TradingSignalJob.status.in_(OPEN_JOB_STATUSES),
        )
        .update(
            {
                "status": "cancelled",
                "last_error": reason[:2000],
                "lock_token": "",
                "locked_at": None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )


def _should_skip_job(db: Session, job: TradingSignalJob) -> bool:
    session = job.session
    if session is None:
        return False

    if session.status == "cancelled":
        job.status = "cancelled"
        job.last_error = "Session was cancelled."
        job.lock_token = ""
        job.locked_at = None
        job.updated_at = datetime.utcnow()
        db.commit()
        return True

    if session.status == "finished":
        job.status = "cancelled"
        job.last_error = "Session is already finished."
        job.lock_token = ""
        job.locked_at = None
        job.updated_at = datetime.utcnow()
        db.commit()
        return True

    newer_session_exists = (
        db.query(TradingSession.id)
        .filter(
            TradingSession.channel_id == session.channel_id,
            TradingSession.id > session.id,
            TradingSession.status != "cancelled",
        )
        .first()
        is not None
    )
    if newer_session_exists:
        _cancel_session_open_work(
            db,
            session,
            "Cancelled because a newer trading session exists for this channel.",
        )
        db.commit()
        return True

    return False


def _execute_session_soon(db: Session, client: httpx.Client, job: TradingSignalJob) -> None:
    session = job.session
    if session is None:
        raise RuntimeError("SESSION_SOON job has no session")

    minutes_before = int((job.payload or {}).get("minutes_before", 60))
    message_id = send_session_soon(
        client,
        market_type=session.market_mode,
        session_start_time=session.starts_at,
        minutes_before=minutes_before,
    )
    payload = dict(job.payload or {})
    payload["message_id"] = message_id
    job.payload = payload
    _mark_session_running(session)
    db.flush()


def _execute_signal_countdown(db: Session, client: httpx.Client, job: TradingSignalJob) -> None:
    signal = job.signal
    if signal is None:
        raise RuntimeError("SIGNAL_COUNTDOWN job has no signal")

    seconds_before = int((job.payload or {}).get("seconds_before", 60))
    message_id = send_signal_countdown(
        client,
        asset=_signal_asset(signal),
        entry_time=signal.entry_time or datetime.utcnow(),
        expiry_seconds=signal.expiry_seconds,
        seconds_before=seconds_before,
    )
    signal.countdown_message_id = message_id
    _mark_session_running(signal.session)
    db.flush()


def _execute_signal_entry(db: Session, client: httpx.Client, job: TradingSignalJob) -> None:
    signal = job.signal
    if signal is None:
        raise RuntimeError("SIGNAL_ENTRY job has no signal")
    attempt = job.attempt

    if signal.entry_price is None:
        entry_price, quote_payload = _latest_price(signal)
        signal.entry_price = entry_price
        if attempt is not None:
            attempt.entry_price = entry_price
            attempt.quote_snapshot = quote_payload

    message_id = send_signal_entry(client, _signal_entry(signal, attempt))
    signal.signal_message_id = message_id
    signal.status = "active"
    if attempt is not None:
        attempt.entry_message_id = message_id
        attempt.status = "active"
    _mark_session_running(signal.session)
    db.flush()


def _execute_signal_result(db: Session, client: httpx.Client, job: TradingSignalJob) -> None:
    signal = job.signal
    if signal is None:
        raise RuntimeError("SIGNAL_RESULT job has no signal")
    attempt = job.attempt
    entry_price = _decimal_or_none((attempt.entry_price if attempt is not None else None) or signal.entry_price)
    if entry_price is None:
        raise RuntimeError("SIGNAL_RESULT job has no entry price")

    close_price, quote_payload = _latest_price(signal)
    direction = signal.direction if signal.direction in {"BUY", "SELL"} else "BUY"
    result = "WIN" if _is_win(direction, entry_price, close_price) else "LOSS"

    outcome = SignalOutcome(
        asset=_signal_asset(signal),
        direction=direction,
        result=result,
        entry_time=(attempt.entry_time if attempt is not None else None) or signal.entry_time or datetime.utcnow(),
        expiry_seconds=(attempt.expiry_seconds if attempt is not None else None) or signal.expiry_seconds,
        entry_price=float(entry_price),
        close_price=float(close_price),
        chart_image_path=_render_result_chart(
            signal,
            attempt,
            direction=direction,
            result=result,
            entry_price=entry_price,
            close_price=close_price,
            history_payload=quote_payload,
        ),
    )

    signal.close_price = close_price
    if attempt is not None:
        attempt.close_price = close_price
        attempt.result = result
        attempt.status = "finished"
        attempt.quote_snapshot = quote_payload

    session = signal.session
    _mark_session_running(session)

    attempt_no = attempt.attempt_no if attempt is not None else signal.current_attempt_no
    max_overlaps = max(0, (session.max_overlaps or 0))
    if result == "LOSS" and attempt_no < max_overlaps:
        next_attempt_no = attempt_no + 1
        next_entry_time = _next_overlap_run_at()
        next_close_time = next_entry_time + timedelta(seconds=signal.expiry_seconds)
        next_entry_price, next_quote_payload = _latest_price(signal)

        next_attempt = TradingSignalAttempt(
            signal_id=signal.id,
            attempt_no=next_attempt_no,
            kind="overlap",
            status="active",
            direction=direction,
            expiry_seconds=signal.expiry_seconds,
            entry_time=next_entry_time,
            close_time=next_close_time,
            entry_price=next_entry_price,
            quote_snapshot=next_quote_payload,
        )
        db.add(next_attempt)
        db.flush()

        overlap_message_id = send_overlap(client, _signal_entry(signal, next_attempt), attempt_no=next_attempt_no)
        next_attempt.entry_message_id = overlap_message_id
        signal.current_attempt_no = next_attempt_no
        signal.entry_price = next_entry_price
        signal.entry_time = next_entry_time
        signal.close_time = next_close_time
        signal.status = "active"

        db.add(
            TradingSignalJob(
                session_id=session.id,
                signal_id=signal.id,
                attempt_id=next_attempt.id,
                kind="SIGNAL_RESULT",
                status="scheduled",
                run_at=next_close_time,
                payload={"overlap_attempt_no": next_attempt_no},
            )
        )
        db.flush()
        return

    message_id = send_signal_result(client, outcome)

    signal.result = result
    signal.result_message_id = message_id
    signal.status = "finished"
    if attempt is not None:
        attempt.result_message_id = message_id
    session.total_series += 1
    if result == "WIN":
        session.wins += 1
    else:
        session.losses += 1
    db.flush()


def _execute_session_finished(db: Session, client: httpx.Client, job: TradingSignalJob) -> None:
    session = job.session
    if session is None:
        raise RuntimeError("SESSION_FINISHED job has no session")

    message_id = send_session_finished(
        client,
        market_type=session.market_mode,
        session_start_time=session.starts_at,
        session_end_time=session.ends_at,
        total_series=session.total_series,
        wins=session.wins,
        losses=session.losses,
    )
    payload = dict(job.payload or {})
    payload["message_id"] = message_id
    job.payload = payload
    session.status = "finished"
    db.flush()


def _execute_job(db: Session, client: httpx.Client, job: TradingSignalJob) -> None:
    if job.kind == "SESSION_SOON":
        _execute_session_soon(db, client, job)
    elif job.kind == "SIGNAL_COUNTDOWN":
        _execute_signal_countdown(db, client, job)
    elif job.kind == "SIGNAL_ENTRY":
        _execute_signal_entry(db, client, job)
    elif job.kind == "SIGNAL_RESULT":
        _execute_signal_result(db, client, job)
    elif job.kind == "SESSION_FINISHED":
        _execute_session_finished(db, client, job)
    else:
        raise RuntimeError(f"Unknown trading signal job kind: {job.kind}")


def _claim_job(db: Session, job_id: int, lock_token: str) -> TradingSignalJob | None:
    now = datetime.utcnow()
    updated = (
        db.query(TradingSignalJob)
        .filter(TradingSignalJob.id == job_id, TradingSignalJob.status == "scheduled")
        .update(
            {
                "status": "processing",
                "locked_at": now,
                "lock_token": lock_token,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if updated != 1:
        return None
    return db.query(TradingSignalJob).filter(TradingSignalJob.id == job_id).first()


def _finish_job(db: Session, job: TradingSignalJob) -> None:
    job.status = "done"
    job.last_error = ""
    job.updated_at = datetime.utcnow()
    db.commit()


def _fail_job(db: Session, job: TradingSignalJob, error: Exception) -> None:
    db.rollback()
    job.attempts_count += 1
    job.last_error = str(error)[:2000]
    job.lock_token = ""
    job.locked_at = None
    job.updated_at = datetime.utcnow()
    if job.attempts_count >= TRADING_SIGNAL_WORKER_MAX_ATTEMPTS:
        job.status = "failed"
    else:
        job.status = "scheduled"
        job.run_at = datetime.utcnow() + timedelta(seconds=TRADING_SIGNAL_WORKER_RETRY_SECONDS)
    db.commit()


def run_due_trading_signal_jobs() -> int:
    now = datetime.utcnow()
    stale_locked_before = now - timedelta(minutes=5)
    db = SessionLocal()
    try:
        (
            db.query(TradingSignalJob)
            .filter(
                TradingSignalJob.status == "processing",
                TradingSignalJob.locked_at.isnot(None),
                TradingSignalJob.locked_at <= stale_locked_before,
            )
            .update(
                {
                    "status": "scheduled",
                    "lock_token": "",
                    "locked_at": None,
                    "updated_at": now,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        due_job_ids = [
            job_id
            for (job_id,) in (
                db.query(TradingSignalJob.id)
                .filter(TradingSignalJob.status == "scheduled", TradingSignalJob.run_at <= now)
                .order_by(TradingSignalJob.run_at.asc(), TradingSignalJob.id.asc())
                .limit(TRADING_SIGNAL_WORKER_BATCH_SIZE)
                .all()
            )
        ]
    finally:
        db.close()

    executed = 0
    for job_id in due_job_ids:
        db = SessionLocal()
        lock_token = uuid.uuid4().hex
        job = None
        try:
            job = _claim_job(db, job_id, lock_token)
            if job is None:
                continue
            if _should_skip_job(db, job):
                continue
            with httpx.Client(timeout=30) as client:
                _execute_job(db, client, job)
            _finish_job(db, job)
            executed += 1
        except Exception as error:
            if job is not None:
                _fail_job(db, job, error)
            print(f"trading_signal_job_failed job_id={job_id} detail={error}")
        finally:
            db.close()

    return executed


def run_trading_signal_worker() -> None:
    print("trading_signal_worker_started")
    while True:
        try:
            executed = run_due_trading_signal_jobs()
            if executed:
                print(f"trading_signal_worker_executed count={executed}")
        except Exception as error:
            print(f"trading_signal_worker_failed detail={error}")
        time.sleep(TRADING_SIGNAL_WORKER_POLL_SECONDS)


def start_trading_signal_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        worker = threading.Thread(target=run_trading_signal_worker, daemon=True)
        worker.start()
        _worker_started = True
