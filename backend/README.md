# Paradox FX Backend

FastAPI backend for the Telegram Mini App MVP.

At this stage it is responsible for:

- Telegram `/start` webhook response with Mini App and text-format buttons.
- Telegram Mini App `initData` validation.
- Saving per-user settings: selected market and language.

Run locally:

```bash
cd backend
uvicorn app.main:app --reload
```

PostgreSQL URL example:

```bash
DATABASE_URL=postgresql+psycopg://trader:trader@localhost:5432/trader_mini
```

Required Telegram env vars:

```bash
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_WEBAPP_URL=http://localhost:5173
```
