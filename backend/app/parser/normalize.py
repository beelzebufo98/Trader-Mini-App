import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from urllib.parse import urljoin


SOURCE = "forexfactory"
BASE_URL = "https://www.forexfactory.com"


@dataclass(frozen=True)
class ParsedEvent:
    source: str
    title: str
    currency: str
    impact: str
    event_hash: str
    datetime_utc: datetime
    event_date: datetime
    event_time: str | None
    is_all_day: bool
    source_event_id: str | None = None
    event_url: str | None = None
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def normalize_url(href: str | None) -> str | None:
    href = clean_text(href)
    if not href:
        return None

    return urljoin(BASE_URL, href)


def parse_impact(value: str) -> str | None:
    normalized = clean_text(value).lower()

    if "holiday" in normalized:
        return "HOLIDAY"
    if "high" in normalized or "red" in normalized:
        return "HIGH"
    if "medium" in normalized or "orange" in normalized:
        return "MEDIUM"
    if "low" in normalized or "yellow" in normalized:
        return "LOW"

    return None


def parse_time(value: str) -> tuple[time | None, bool]:
    normalized = clean_text(value).lower()

    if not normalized:
        return None, False
    if "all day" in normalized or "day" == normalized:
        return None, True

    normalized = normalized.replace(".", "").replace(" ", "")
    match = re.match(r"^(\d{1,2}):(\d{2})(am|pm)?$", normalized)
    if not match:
        match = re.match(r"^(\d{1,2})(am|pm)$", normalized)
        if not match:
            return None, False
        hour = int(match.group(1))
        minute = 0
        suffix = match.group(2)
    else:
        hour = int(match.group(1))
        minute = int(match.group(2))
        suffix = match.group(3)

    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0

    if hour > 23 or minute > 59:
        return None, False

    return time(hour, minute), False


def parse_date(value: str, year: int) -> date | None:
    normalized = clean_text(value)
    if not normalized:
        return None

    normalized = re.sub(r"^(mon|tue|wed|thu|fri|sat|sun)\w*\s+", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.replace(",", "")

    for fmt in ("%b %d %Y", "%B %d %Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            source = normalized if "%Y" in fmt and re.search(r"\d{4}", normalized) else f"{normalized} {year}"
            return datetime.strptime(source, fmt).date()
        except ValueError:
            continue

    return None


def make_event_hash(title: str, currency: str, datetime_utc: datetime, source: str = SOURCE) -> str:
    key = f"{source}|{datetime_utc.isoformat()}|{currency.upper()}|{clean_text(title)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def build_parsed_event(
    *,
    title: str,
    currency: str,
    impact: str,
    event_date: date,
    event_time: time | None,
    is_all_day: bool,
    source_timezone_offset_hours: int,
    source_event_id: str | None = None,
    event_url: str | None = None,
    actual: str | None = None,
    forecast: str | None = None,
    previous: str | None = None,
) -> ParsedEvent:
    local_time = event_time or time(0, 0)
    source_datetime = datetime.combine(event_date, local_time)
    datetime_utc = source_datetime - timedelta(hours=source_timezone_offset_hours)

    return ParsedEvent(
        source=SOURCE,
        source_event_id=source_event_id,
        title=clean_text(title),
        currency=clean_text(currency).upper(),
        impact=impact,
        datetime_utc=datetime_utc,
        event_date=datetime.combine(event_date, time(0, 0)),
        event_time=None if is_all_day or event_time is None else event_time.strftime("%H:%M"),
        is_all_day=is_all_day,
        event_url=normalize_url(event_url),
        actual=clean_text(actual) or None,
        forecast=clean_text(forecast) or None,
        previous=clean_text(previous) or None,
        event_hash=make_event_hash(title, currency, datetime_utc),
    )
