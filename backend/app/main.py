from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.api.health import router as health_router
from app.api.me import router as me_router
from app.api.pocket_option import router as pocket_option_router
from app.api.telegram import router as telegram_router, start_funnel_reminder_worker
from app.config import settings
from app.database import Base, engine
from app.models import funnel_session, signal_channel, telegram_user, trading, user_settings
from app.services.trading_signal_worker import start_trading_signal_worker

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
    ensure_funnel_session_columns()
    ensure_normalized_tables_seeded()
    start_funnel_reminder_worker()
    start_trading_signal_worker()


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

        legacy_reminder_columns = {
            "funnel_reminder_chat_id",
            "funnel_reminder_due_at",
            "funnel_reminder_stage",
            "funnel_reminder_token",
        }
        if legacy_reminder_columns.issubset(columns):
            connection.execute(
                text(
                    "UPDATE user_settings "
                    "SET funnel_reminder_chat_id = telegram_id "
                    "WHERE funnel_reminder_chat_id IS NULL "
                    "AND funnel_reminder_stage > 0 "
                    "AND funnel_reminder_token != ''"
                )
            )
            connection.execute(
                text(
                    "UPDATE user_settings "
                    "SET funnel_reminder_due_at = CURRENT_TIMESTAMP "
                    "WHERE funnel_reminder_due_at IS NULL "
                    "AND funnel_reminder_stage > 0 "
                    "AND funnel_reminder_token != ''"
                )
            )


def ensure_funnel_session_columns() -> None:
    inspector = inspect(engine)
    if "funnel_sessions" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("funnel_sessions")}
    with engine.begin() as connection:
        if "last_media_message_id" not in columns:
            connection.execute(text("ALTER TABLE funnel_sessions ADD COLUMN last_media_message_id INTEGER"))
        if "trader_id" not in columns:
            connection.execute(text("ALTER TABLE funnel_sessions ADD COLUMN trader_id VARCHAR(64) DEFAULT '' NOT NULL"))


def ensure_normalized_tables_seeded() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not {"user_settings", "telegram_users", "funnel_sessions"}.issubset(tables):
        return

    columns = {column["name"] for column in inspector.get_columns("user_settings")}

    def legacy(column: str, fallback: str) -> str:
        return f"us.{column}" if column in columns else fallback

    created_at = legacy("created_at", "CURRENT_TIMESTAMP")
    updated_at = legacy("updated_at", "CURRENT_TIMESTAMP")
    empty_string = "''"

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_users (telegram_id, username, first_name, created_at, updated_at) "
                "SELECT us.telegram_id, "
                f"{legacy('username', 'NULL')}, "
                f"{legacy('first_name', 'NULL')}, "
                f"{created_at}, "
                f"{updated_at} "
                "FROM user_settings us "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM telegram_users tu WHERE tu.telegram_id = us.telegram_id"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO funnel_sessions ("
                "telegram_id, route, access_granted, reminder_kind, reminder_stage, reminder_token, "
                "reminder_chat_id, reminder_due_at, last_reminder_message_id, created_at, updated_at"
                ") "
                "SELECT us.telegram_id, "
                f"{legacy('funnel_route', empty_string)}, "
                f"{legacy('funnel_access_granted', 'FALSE')}, "
                f"{legacy('funnel_reminder_kind', empty_string)}, "
                f"{legacy('funnel_reminder_stage', '0')}, "
                f"{legacy('funnel_reminder_token', empty_string)}, "
                f"{legacy('funnel_reminder_chat_id', 'NULL')}, "
                f"{legacy('funnel_reminder_due_at', 'NULL')}, "
                f"{legacy('funnel_last_reminder_message_id', 'NULL')}, "
                f"{created_at}, "
                f"{updated_at} "
                "FROM user_settings us "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM funnel_sessions fs WHERE fs.telegram_id = us.telegram_id"
                ")"
            )
        )
