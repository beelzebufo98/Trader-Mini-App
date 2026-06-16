import hashlib
from datetime import UTC, datetime, time, timedelta

from app.database import SessionLocal, engine
from app.models.economic_event import EconomicEvent


def make_hash(title: str, currency: str, datetime_utc: datetime, source: str) -> str:
    key = f"{title}|{currency}|{datetime_utc.isoformat()}|{source}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def seed_events() -> None:
    EconomicEvent.metadata.create_all(bind=engine)
    today = datetime.now(UTC).date()
    usd_event_time = datetime.combine(today, time(18, 0))
    eur_event_time = datetime.combine(today + timedelta(days=1), time(9, 0))
    gbp_event_time = datetime.combine(today, time(15, 0))

    raw_events = [
        {
            "title": "Retail Sales",
            "currency": "USD",
            "impact": "HIGH",
            "datetime_utc": usd_event_time,
            "event_date": usd_event_time,
            "event_time": usd_event_time.strftime("%H:%M"),
            "source": "forexfactory",
            "source_event_id": f"ff_seed_{usd_event_time.strftime('%Y-%m-%d_%H_%M')}_USD_retail_sales",
            "event_url": "https://www.forexfactory.com/",
        },
        {
            "title": "CPI y/y",
            "currency": "EUR",
            "impact": "HIGH",
            "datetime_utc": eur_event_time,
            "event_date": eur_event_time,
            "event_time": eur_event_time.strftime("%H:%M"),
            "source": "forexfactory",
            "source_event_id": f"ff_seed_{eur_event_time.strftime('%Y-%m-%d_%H_%M')}_EUR_cpi",
            "event_url": "https://www.forexfactory.com/",
        },
        {
            "title": "Official Bank Rate",
            "currency": "GBP",
            "impact": "HIGH",
            "datetime_utc": gbp_event_time,
            "event_date": gbp_event_time,
            "event_time": gbp_event_time.strftime("%H:%M"),
            "source": "forexfactory",
            "source_event_id": f"ff_seed_{gbp_event_time.strftime('%Y-%m-%d_%H_%M')}_GBP_bank_rate",
            "event_url": "https://www.forexfactory.com/",
        },
        {
            "title": "Unemployment Claims",
            "currency": "USD",
            "impact": "HIGH",
            "datetime_utc": datetime(2026, 1, 2, 15, 0),
            "event_date": datetime(2026, 1, 2),
            "event_time": "15:00",
            "source": "forexfactory",
            "source_event_id": "ff_2026-01-02_15_00_USD_unemployment_claims",
            "event_url": "https://www.forexfactory.com/",
        },
        {
            "title": "FOMC Meeting Minutes",
            "currency": "USD",
            "impact": "HIGH",
            "datetime_utc": datetime(2026, 1, 2, 15, 0),
            "event_date": datetime(2026, 1, 2),
            "event_time": "15:00",
            "source": "forexfactory",
            "source_event_id": "ff_2026-01-02_15_00_USD_fomc_minutes",
            "event_url": "https://www.forexfactory.com/",
        },
        {
            "title": "Final Services PMI",
            "currency": "GBP",
            "impact": "HIGH",
            "datetime_utc": datetime(2026, 1, 3, 9, 30),
            "event_date": datetime(2026, 1, 3),
            "event_time": "09:30",
            "source": "forexfactory",
            "source_event_id": "ff_2026-01-03_09_30_GBP_services_pmi",
            "event_url": "https://www.forexfactory.com/",
        },
        {
            "title": "ECB Rate Decision",
            "currency": "EUR",
            "impact": "HIGH",
            "datetime_utc": datetime(2026, 1, 3, 12, 45),
            "event_date": datetime(2026, 1, 3),
            "event_time": "12:45",
            "source": "forexfactory",
            "source_event_id": "ff_2026-01-03_12_45_EUR_rate_decision",
            "event_url": "https://www.forexfactory.com/",
        },
    ]

    with SessionLocal() as session:
        added = 0
        for item in raw_events:
            item["event_hash"] = make_hash(
                item["title"], item["currency"], item["datetime_utc"], item["source"]
            )
            existing = session.query(EconomicEvent).filter_by(event_hash=item["event_hash"]).first()
            if existing:
                continue

            session.add(EconomicEvent(**item))
            added += 1

        if added:
            session.commit()

    print(f"Seed complete, events added: {added}")


if __name__ == "__main__":
    seed_events()
