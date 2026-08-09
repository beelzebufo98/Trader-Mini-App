from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.api.health import router as health_router
from app.api.me import router as me_router
from app.api.pocket_option import router as pocket_option_router
from app.api.telegram import router as telegram_router
from app.config import settings
from app.database import Base, engine
from app.models import user_settings

app = FastAPI(title="Trader Mini Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(me_router, prefix="/api/v1/me", tags=["me"])
app.include_router(pocket_option_router, prefix="/api/v1/pocket-option", tags=["pocket-option"])
app.include_router(telegram_router, prefix="/api/v1/telegram", tags=["telegram"])


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_user_settings_columns()


def ensure_user_settings_columns() -> None:
    inspector = inspect(engine)
    if "user_settings" not in inspector.get_table_names():
        return

    columns_by_name = {column["name"]: column for column in inspector.get_columns("user_settings")}
    columns = set(columns_by_name)

    with engine.begin() as connection:
        telegram_id_column = columns_by_name.get("telegram_id")
        if telegram_id_column is not None and engine.dialect.name == "postgresql":
            column_type = str(telegram_id_column["type"]).upper()
            if "BIGINT" not in column_type:
                connection.execute(text("ALTER TABLE user_settings ALTER COLUMN telegram_id TYPE BIGINT"))

        if "news_window" not in columns:
            connection.execute(text("ALTER TABLE user_settings ADD COLUMN news_window VARCHAR(32) DEFAULT '48H' NOT NULL"))
        if "language" not in columns:
            connection.execute(text("ALTER TABLE user_settings ADD COLUMN language VARCHAR(16) DEFAULT 'auto' NOT NULL"))
        if "market" not in columns:
            connection.execute(text("ALTER TABLE user_settings ADD COLUMN market VARCHAR(16) DEFAULT 'FOREX' NOT NULL"))
        if "funnel_route" not in columns:
            connection.execute(text("ALTER TABLE user_settings ADD COLUMN funnel_route VARCHAR(16) DEFAULT '' NOT NULL"))
        if "funnel_access_granted" not in columns:
            connection.execute(text("ALTER TABLE user_settings ADD COLUMN funnel_access_granted BOOLEAN DEFAULT FALSE NOT NULL"))
