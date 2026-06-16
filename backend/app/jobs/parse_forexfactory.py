import argparse
from pathlib import Path

import httpx
from playwright.sync_api import Error as PlaywrightError

from app.database import SessionLocal, engine
from app.models.economic_event import EconomicEvent
from app.parser.forexfactory import (
    CALENDAR_URL,
    fetch_calendar_html,
    fetch_calendar_html_with_browser,
    load_calendar_html,
    parse_calendar_html,
    save_calendar_html,
)
from app.parser.upsert import upsert_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse ForexFactory calendar and upsert economic events.")
    parser.add_argument("--url", default=CALENDAR_URL, help="ForexFactory calendar URL to fetch.")
    parser.add_argument("--html", help="Parse an existing local HTML file instead of fetching ForexFactory.")
    parser.add_argument("--save-html", help="Save fetched ForexFactory HTML to this path for debugging.")
    parser.add_argument("--browser", action="store_true", help="Fetch ForexFactory through Playwright Chromium.")
    parser.add_argument(
        "--source-tz-offset",
        type=int,
        default=0,
        help="Timezone offset of times shown by ForexFactory. Use 0 when the source is configured to UTC.",
    )
    parser.add_argument(
        "--impact",
        action="append",
        choices=["HIGH", "MEDIUM", "LOW", "HOLIDAY"],
        help="Impact to store. Can be passed multiple times. Default: HIGH.",
    )
    parser.add_argument(
        "--prune-source",
        action="store_true",
        help="Delete stored source events that are not present in the current parsed result.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_impacts = set(args.impact or ["HIGH"])

    print("ForexFactory parser started")

    if args.html:
        html = load_calendar_html(args.html)
        print(f"Loaded HTML: {Path(args.html)}")
    elif args.browser:
        html = fetch_with_browser_or_exit(args.url)
        print(f"Fetched ForexFactory calendar with Playwright: {args.url}")
    else:
        try:
            html = fetch_calendar_html(args.url)
            print(f"Fetched ForexFactory calendar: {args.url}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise

            print("HTTP fetch returned 403 Forbidden, retrying with Playwright")
            html = fetch_with_browser_or_exit(args.url)
            print(f"Fetched ForexFactory calendar with Playwright: {args.url}")

    if args.save_html:
        save_calendar_html(args.save_html, html)
        print(f"Saved HTML: {Path(args.save_html)}")

    events = parse_calendar_html(
        html,
        source_timezone_offset_hours=args.source_tz_offset,
        include_impacts=include_impacts,
    )

    EconomicEvent.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        result = upsert_events(db, events, prune_source=args.prune_source)

    print(f"Parsed: {result.parsed}")
    print(f"Created: {result.created}")
    print(f"Updated: {result.updated}")
    print(f"Skipped: {result.skipped}")
    print(f"Pruned: {result.pruned}")
    print("Done")


def fetch_with_browser_or_exit(url: str) -> str:
    try:
        return fetch_calendar_html_with_browser(url)
    except PlaywrightError as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "playwright install" in message:
            raise SystemExit(
                "Playwright Chromium is not installed. Run:\n"
                "python -m playwright install chromium\n"
                "Then retry the parser command."
            ) from exc

        raise


if __name__ == "__main__":
    main()
