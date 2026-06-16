import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.parser.normalize import (
    BASE_URL,
    ParsedEvent,
    SOURCE,
    build_parsed_event,
    clean_text,
    make_event_hash,
    parse_date,
    parse_impact,
    parse_time,
    normalize_url,
)


CALENDAR_URL = "https://www.forexfactory.com/calendar?week=this"
DEFAULT_TIMEOUT_SECONDS = 30


def fetch_calendar_html(url: str = CALENDAR_URL) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        )
    }

    with httpx.Client(headers=headers, follow_redirects=True, timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def fetch_calendar_html_with_browser(url: str = CALENDAR_URL) -> str:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)

        try:
            page.wait_for_selector("tr.calendar__row, table, body", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        scroll_to_page_bottom(page)
        html = page.content()
        browser.close()
        return html


def scroll_to_page_bottom(page, *, max_scrolls: int = 40) -> None:
    previous_height = 0

    for _ in range(max_scrolls):
        height = page.evaluate("document.body.scrollHeight")
        if height == previous_height:
            break

        previous_height = height
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(300)


def load_calendar_html(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def save_calendar_html(path: str | Path, html: str) -> None:
    Path(path).write_text(html, encoding="utf-8")


def parse_calendar_html(
    html: str,
    *,
    source_timezone_offset_hours: int = 0,
    include_impacts: set[str] | None = None,
    current_year: int | None = None,
) -> list[ParsedEvent]:
    embedded_events = parse_embedded_calendar_events(html, include_impacts=include_impacts)
    if embedded_events:
        return embedded_events

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.calendar__row")

    if not rows:
        rows = soup.select("tr")

    events: list[ParsedEvent] = []
    current_date: date | None = None
    current_time = None
    current_year = current_year or date.today().year

    for row in rows:
        if not isinstance(row, Tag):
            continue

        row_date = extract_date(row, current_year)
        if row_date is not None:
            current_date = row_date

        row_time, row_is_all_day, has_time_value = extract_time(row)
        if has_time_value:
            current_time = row_time

        currency = extract_currency(row)
        title, event_url = extract_title(row)
        impact = extract_impact(row)

        if not current_date or not currency or not title or not impact:
            continue

        if include_impacts is not None and impact not in include_impacts:
            continue

        is_all_day = row_is_all_day
        event_time = None if is_all_day else current_time

        if event_time is None and not is_all_day:
            continue

        event = build_parsed_event(
            title=title,
            currency=currency,
            impact=impact,
            event_date=current_date,
            event_time=event_time,
            is_all_day=is_all_day,
            source_timezone_offset_hours=source_timezone_offset_hours,
            event_url=event_url,
            actual=extract_cell_text(row, "actual"),
            forecast=extract_cell_text(row, "forecast"),
            previous=extract_cell_text(row, "previous"),
        )
        events.append(event)

    return events


def parse_embedded_calendar_events(html: str, *, include_impacts: set[str] | None = None) -> list[ParsedEvent]:
    days = extract_embedded_days(html)
    if not days:
        return []

    events: list[ParsedEvent] = []
    for day in days:
        for item in day.get("events", []):
            event = build_event_from_embedded_item(item)
            if event is None:
                continue

            if include_impacts is not None and event.impact not in include_impacts:
                continue

            events.append(event)

    return events


def extract_embedded_days(html: str) -> list[dict]:
    marker_index = html.find("days:")
    if marker_index == -1:
        return []

    array_start = html.find("[", marker_index)
    if array_start == -1:
        return []

    array_end = find_matching_json_array_end(html, array_start)
    if array_end is None:
        return []

    try:
        parsed = json.loads(html[array_start:array_end])
    except json.JSONDecodeError:
        return []

    return parsed if isinstance(parsed, list) else []


def find_matching_json_array_end(value: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(value)):
        char = value[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index + 1

    return None


def build_event_from_embedded_item(item: dict) -> ParsedEvent | None:
    title = clean_text(item.get("name"))
    currency = clean_text(item.get("currency")).upper()
    impact = parse_impact(" ".join([clean_text(item.get("impactName")), clean_text(item.get("impactClass"))]))
    dateline = item.get("dateline")

    if not title or not currency or not impact or not isinstance(dateline, int):
        return None

    datetime_utc = datetime.fromtimestamp(dateline, tz=timezone.utc).replace(tzinfo=None)
    time_label = clean_text(item.get("timeLabel"))
    is_all_day = "day" in time_label.lower() and not parse_time(time_label)[0]
    event_time = None if is_all_day else datetime_utc.strftime("%H:%M")

    return ParsedEvent(
        source=SOURCE,
        source_event_id=f"ff_{item.get('id')}" if item.get("id") is not None else None,
        title=title,
        currency=currency,
        impact=impact,
        datetime_utc=datetime_utc,
        event_date=datetime.combine(datetime_utc.date(), time(0, 0)),
        event_time=event_time,
        is_all_day=is_all_day,
        event_url=normalize_url(item.get("url") or item.get("soloUrl") or BASE_URL),
        actual=clean_text(item.get("actual")) or None,
        forecast=clean_text(item.get("forecast")) or None,
        previous=clean_text(item.get("previous")) or None,
        event_hash=make_event_hash(title, currency, datetime_utc),
    )


def extract_date(row: Tag, current_year: int) -> date | None:
    candidates = [
        extract_cell_text(row, "date"),
        clean_text(row.get("data-date")),
    ]

    for candidate in candidates:
        parsed = parse_date(candidate, current_year)
        if parsed is not None:
            return parsed

    return None


def extract_time(row: Tag):
    value = extract_cell_text(row, "time")
    parsed_time, is_all_day = parse_time(value)
    return parsed_time, is_all_day, bool(clean_text(value))


def extract_currency(row: Tag) -> str:
    return extract_cell_text(row, "currency")


def extract_title(row: Tag) -> tuple[str, str | None]:
    cell = find_calendar_cell(row, "event") or find_calendar_cell(row, "title")
    if cell is None:
        return "", None

    link = cell.find("a", href=True)
    title = clean_text(link.get_text(" ", strip=True) if link else cell.get_text(" ", strip=True))
    href = link.get("href") if link else None
    return title, href


def extract_impact(row: Tag) -> str | None:
    cell = find_calendar_cell(row, "impact")
    if cell is None:
        return None

    values = [cell.get_text(" ", strip=True), " ".join(cell.get("class", []))]
    for element in cell.find_all(True):
        values.extend(
            [
                " ".join(element.get("class", [])),
                clean_text(element.get("title")),
                clean_text(element.get("alt")),
                clean_text(element.get("aria-label")),
            ]
        )

    return parse_impact(" ".join(values))


def extract_cell_text(row: Tag, name: str) -> str:
    cell = find_calendar_cell(row, name)
    return clean_text(cell.get_text(" ", strip=True) if cell else "")


def find_calendar_cell(row: Tag, name: str) -> Tag | None:
    selectors = [
        f".calendar__{name}",
        f"[class*='calendar__{name}']",
        f"[data-column='{name}']",
        f"[data-col='{name}']",
    ]

    for selector in selectors:
        found = row.select_one(selector)
        if isinstance(found, Tag):
            return found

    return None
