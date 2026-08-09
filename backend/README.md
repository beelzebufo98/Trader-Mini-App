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
TELEGRAM_FUNNEL_ENABLED=false
TELEGRAM_FUNNEL_ALLOWED_USER_IDS=<comma-separated Telegram user ids>
TELEGRAM_SOURCE_CHANNEL_ID=<private channel id, e.g. -100...>
TEAM_VIP_URL=<private VIP team invite link>
```

Set `TELEGRAM_FUNNEL_ENABLED=true` in Render to enable deep-link funnel routes, Trader ID checks, and the bot API prototype.
Only users listed in `TELEGRAM_FUNNEL_ALLOWED_USER_IDS` can use the funnel while it is enabled.

Telegram deep links:

```bash
BOT auto language:  https://t.me/<bot_username>?start=want_bot
TEAM auto language: https://t.me/<bot_username>?start=want_team

BOT RU:  https://t.me/<bot_username>?start=want_bot_ru
BOT EN:  https://t.me/<bot_username>?start=want_bot_en
TEAM RU: https://t.me/<bot_username>?start=want_team_ru
TEAM EN: https://t.me/<bot_username>?start=want_team_en
```

Pocket Option affiliate API env vars:

```bash
POCKET_OPTION_PARTNER_ID=<partner id>
POCKET_OPTION_API_TOKEN=<api token>
POCKET_OPTION_API_BASE_URL=https://affiliate.pocketoption.com/api
POCKET_OPTION_REF_RU_URL=<private RU referral link>
POCKET_OPTION_REF_WW_URL=<private WW referral link>
```

Devsbite API env vars:

```bash
DEVSBITE_CLIENT_TOKEN=<client token>
DEVSBITE_API_BASE_URL=https://api.devsbite.com
```

Minimal bot API prototype:

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

The bot can request Devsbite pairs, quotes, and `/analysis/combined`, then returns short HTML-formatted summaries.

Internal endpoint:

```bash
GET /api/v1/pocket-option/user-info/{user_id}
```
