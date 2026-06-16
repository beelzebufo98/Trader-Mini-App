# Trader Mini Backend

Минимальная структура бэкенда для проекта Trader Mini.

Запуск:

```bash
cd backend
uvicorn app.main:app --reload
```

Seed:

```bash
python seed.py
```

Парсер ForexFactory:

```bash
python -m app.jobs.parse_forexfactory
```

Парсинг из локального HTML для отладки:

```bash
python -m app.jobs.parse_forexfactory --html tests/fixtures/forexfactory_calendar_sample.html --impact HIGH --impact HOLIDAY
```

Если обычная HTTP-загрузка не подходит, можно использовать Playwright:

```bash
python -m playwright install chromium
python -m app.jobs.parse_forexfactory --browser --save-html forexfactory_calendar.html
```

PostgreSQL URL example:

```bash
DATABASE_URL=postgresql+psycopg://trader:trader@localhost:5432/trader_mini
```
