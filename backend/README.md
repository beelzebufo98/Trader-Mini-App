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
TELEGRAM_FUNNEL_TEST_ACCESS_CODE=<private test code word>
TELEGRAM_SOURCE_CHANNEL_ID=<private channel id, optional for future source-channel sends>
TEAM_VIP_URL=<private VIP team invite link>
```

The Telegram funnel is enabled for all users by default. The Mini App menu button is hidden until access is granted.
Set `TELEGRAM_FUNNEL_TEST_ACCESS_CODE` to a private code word that lets a user pass the funnel checks and receive access without real deposit verification.

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
