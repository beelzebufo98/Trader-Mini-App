from datetime import datetime, timedelta, timezone


SIGNAL_TIMEZONE = timezone(timedelta(hours=3), "MSK")


def to_signal_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SIGNAL_TIMEZONE)


def format_signal_time(value: datetime, *, seconds: bool = True) -> str:
    fmt = "%H:%M:%S" if seconds else "%H:%M"
    return to_signal_timezone(value).strftime(fmt)
