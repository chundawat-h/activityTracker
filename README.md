# Chalo Activity Tracking Pipeline

Continuously monitors government/bureaucracy news sites for appointments,
transfers, and transport-related activity that could generate business leads
for Chalo — replacing a manual tracking process with an automated pipeline.

```
Scheduler -> Scrape -> Parse -> Keyword Match -> Dedup Check -> Store -> Email Alert
```

## Project layout

```
activity-tracker/
  backend/
    scraper/       # one module per source website (witness.py, bureaucracy.py)
    parser/        # normalizes raw scraped data
    matcher/        # loads keywords.csv, does the matching
    database/       # SQLAlchemy models, session mgmt, dedup logic
    services/        # pipeline orchestration + Composio email notifier
    scheduler/       # APScheduler-based recurring job
    config/          # settings (.env-driven) + structured logging
    tests/           # pytest suite
  main.py             # entry point (scheduler, or --once for a single run)
  keywords.csv          # 185 tracked entities — edit this, not the code
  requirements.txt
  Dockerfile
  render.yaml
  .github/workflows/main.yml
  .env.example
```

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in COMPOSIO_API_KEY, NOTIFICATION_EMAIL_TO, etc.

python main.py --once   # run the pipeline a single time (good for testing)
python main.py           # start the scheduler (blocking, runs every SCRAPE_INTERVAL_MINUTES)
```

Run tests / lint:

```bash
pytest -v
ruff check backend main.py
```

## Configuration (.env)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite by default; set to a `postgresql+psycopg2://...` URL in production — no code changes needed |
| `COMPOSIO_API_KEY` | Composio API key used to send email alerts |
| `COMPOSIO_CONNECTED_ACCOUNT_ID` | The Composio user/connected-account with an authenticated Gmail connection (see below) |
| `NOTIFICATION_EMAIL_TO` / `NOTIFICATION_EMAIL_FROM` | Alert email addresses |
| `SCRAPE_INTERVAL_MINUTES` | e.g. `60` hourly, `1440` daily |
| `RUN_SCRAPE_ON_STARTUP` | Also run once immediately when the process starts |
| `LOG_LEVEL` | `INFO`, `DEBUG`, etc. |
| `KEYWORDS_CSV_PATH` | Defaults to `keywords.csv` at the project root |

## Keywords

`keywords.csv` has two columns, `keyword,category`, and is loaded fresh on
every pipeline run — so a business user can add/remove tracked officials,
STUs, or ministries without touching code or redeploying. It currently ships
with 185 entries generated from the tracked-entities list, auto-categorized
(IAS Officer, IPS Officer, Transport Body/STU, Minister, Central Ministry,
etc.) — feel free to correct any category by hand.

## Composio email setup (one-time)

This uses Composio's **current v3 SDK** (`pip install composio`, not the
older `composio-core`/`composio_openai` toolset classes) via direct,
non-agentic tool execution — `composio.tools.execute(slug="GMAIL_SEND_EMAIL", ...)`.

1. Create a Composio account and API key -> `COMPOSIO_API_KEY`.
2. In the Composio dashboard, connect a Gmail account that alerts should be
   sent from, and note its user/connected-account ID -> `COMPOSIO_CONNECTED_ACCOUNT_ID`.
3. That's it — `backend/services/notification.py` handles the rest, and is
   written as a small, swappable `ComposioEmailNotifier` class so Slack/Teams
   notifiers can be added later with the same `send_alert()` contract.

## Known limitation: scraper selectors

- **indianbureaucracy.com** — a standard WordPress site. The scraper was
  built and verified against its real, live markup (`<article>` containers,
  `.entry-content` body — theme-independent WordPress hooks), with a couple
  of theme-specific selectors as fallback.
- **witnessinthecorridors.com** — an ASP.NET Web Forms site that returns
  bot-detection errors to plain HTTP requests (confirmed while building
  this). The scraper sends full browser-like headers and retries with
  backoff, which resolves this for a lot of basic bot filters — but if it's
  still blocked in production, swap `fetch_html` in
  `backend/scraper/witness.py` for a headless-browser fetch (e.g.
  Playwright) or route through a proxy. Nothing else in the pipeline needs
  to change either way. All CSS selectors for this scraper are collected at
  the top of the file (`SELECTOR CANDIDATES`) so they're a five-minute fix
  once someone can inspect the live DOM.

Both scrapers log a warning (not a crash) if a listing page returns zero
articles, and the pipeline continues to the next source on any single
scraper's failure — one broken source never blocks the other.

## Deployment (Render)

`render.yaml` defines a `worker` service (this pipeline has no HTTP surface
— it's a background job) plus a managed Postgres database. Push to `main`
and Render redeploys automatically; set the secret env vars
(`COMPOSIO_API_KEY`, `COMPOSIO_CONNECTED_ACCOUNT_ID`,
`NOTIFICATION_EMAIL_TO`, `NOTIFICATION_EMAIL_FROM`) in the Render dashboard.

## CI/CD

`.github/workflows/main.yml`: on push to `main`, installs dependencies,
lints (`ruff`), runs tests (`pytest`), then triggers a Render deploy via a
deploy hook. Add `RENDER_DEPLOY_HOOK_URL` as a GitHub Actions secret
(Render dashboard -> service -> Settings -> Deploy Hook).

## Adding a new source website

1. Add a new `class SomeSiteScraper(BaseScraper)` in `backend/scraper/`,
   implementing `scrape_articles() -> list[ScrapedArticle]`.
2. Register it in `SCRAPERS` in `backend/services/pipeline.py`.

Nothing else changes — parsing, matching, dedup, storage, and email all stay
source-agnostic.

## Future-ready hooks already in place

- `matcher.KeywordMatchResult.category` and swappable `ComposioEmailNotifier`
  make it straightforward to add Slack/Teams notifiers later.
- The scraper registry pattern above makes new sources a one-class change.
- `database/models.py` keeps `body` stored in full, ready for future AI
  summarization or LLM relevance scoring to run against it.
- `DATABASE_URL`-only Postgres migration leaves room for a future REST
  API/admin panel to read the same tables directly.
