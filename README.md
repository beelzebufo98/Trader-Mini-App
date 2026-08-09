# Paradox FX Mini App

MVP Telegram Mini App interface for Paradox FX. The first stage includes only
the Mini App flow and UI: format selection in Telegram, market selection,
language selection, and a placeholder signal workspace. Broker connections,
trading servers, parsers, and real signal generation are out of scope for this
stage.

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

## Environment

Backend:

```text
DATABASE_URL=postgresql+psycopg://trader:trader@postgres:5432/trader_mini
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_WEBAPP_URL=http://localhost:5173
TELEGRAM_FUNNEL_ENABLED=false
TELEGRAM_FUNNEL_ALLOWED_USER_IDS=<comma-separated Telegram user ids>
DEVSBITE_CLIENT_TOKEN=<client token>
DEVSBITE_API_BASE_URL=https://api.devsbite.com
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
```

After deployment, verify the generated Render domains. If Render changes service
domains, update:

```text
Backend CORS_ORIGINS
Frontend VITE_API_BASE_URL
```

Telegram settings endpoints use Telegram Mini App `initData` validation. Set
`TELEGRAM_BOT_TOKEN` on the backend service in Render; without it,
`/api/v1/me/settings` is disabled.

For the Telegram funnel prototype, also set:

```text
TELEGRAM_FUNNEL_ENABLED=true
TELEGRAM_FUNNEL_ALLOWED_USER_IDS=<allowed Telegram user ids>
DEVSBITE_CLIENT_TOKEN=<Devsbite client token>
```

Allowed users can test Devsbite analysis in the bot with:

```text
pairs forex
pairs otc
pairs forex 80
pairs commodities
pairs stocks
pairs crypto
quote EUR/USD
quote AED/CNY OTC
quote commodities Gold OTC 60
signal EUR/USD 3
EUR/USD 3
```

The Mini App stores:

```text
market: FOREX / OTC
language: ru / en / es / pt / tr / ar
```

To make `/start` send format buttons, including the Mini App button, set these
backend env vars:

```text
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_WEBAPP_URL=https://trader-mini-frontend.onrender.com
```

Then register the webhook once:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://trader-mini-backend.onrender.com/api/v1/telegram/webhook
```

Production examples:

```text
backend/.env.production.example
frontend/.env.production.example
.env.example
```

Do not commit real production secrets.
