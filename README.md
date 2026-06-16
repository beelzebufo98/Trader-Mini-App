# Trader Mini App

MVP Telegram Mini App for market sessions, market state, and ForexFactory economic events.

## Local Docker Run

```bash
docker compose up --build
```

Services:

```text
frontend  http://localhost:5173
backend   http://localhost:8000
postgres  localhost:5432
```

Health check:

```text
http://localhost:8000/health/
```

Events API:

```text
http://localhost:8000/api/v1/events/?impact=HIGH,MEDIUM&limit=20
```

## Parser Job

Run the parser against the Docker PostgreSQL database:

```bash
docker compose --profile jobs run --rm parser
```

The parser uses Playwright Chromium inside the backend image.

## Environment

Backend:

```text
DATABASE_URL=postgresql+psycopg://trader:trader@postgres:5432/trader_mini
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
TELEGRAM_BOT_TOKEN=<token from BotFather>
```

Frontend build argument:

```text
VITE_API_BASE_URL=http://localhost:8000
```

For Telegram production, both frontend and backend must use public HTTPS URLs.

## Render Deploy

The repository includes `render.yaml` for Render Blueprint deploy:

```text
Postgres: trader-mini-db
Backend:  trader-mini-backend
Frontend: trader-mini-frontend
Cron:     trader-mini-parser
```

After deployment, verify the generated Render domains. If Render changes service
domains, update:

```text
Backend CORS_ORIGINS
Frontend VITE_API_BASE_URL
```

The Render cron job runs the parser every 3 hours:

```text
0 */3 * * *
```

Parser command:

```bash
python -m app.jobs.parse_forexfactory --browser --url https://www.forexfactory.com/calendar?week=this --impact HIGH --prune-source
```

Telegram settings endpoints use Telegram Mini App `initData` validation. Set
`TELEGRAM_BOT_TOKEN` on the backend service in Render; without it, public events
still work, but `/api/v1/me/settings` is disabled.

Production examples:

```text
backend/.env.production.example
frontend/.env.production.example
.env.example
```

Do not commit real production secrets.
