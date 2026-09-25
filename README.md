# Sports API

A read-only, normalized sports API backed by MySQL. A separate importer populates the
database from the [ESPN endpoint catalog in the requested Gist](https://gist.github.com/bhaidar/b2fdd34004250932a4a354a2cc15ddd4).
The public API never calls ESPN; it only reads the local database.

## What is included

- **Python 3.10+ / FastAPI** application with OpenAPI documentation.
- **MySQL 8.4** schema managed by Alembic migrations.
- **Current-snapshot ingestion**: a successful league sync replaces that league's current
  events, news, and rankings, and removes teams no longer returned by the source. Failed
  base-resource requests do not erase the last good snapshot.
- **Raw payload preservation** in JSON columns in addition to the normalized columns.
  This keeps sport-specific fields available without making every ESPN-specific field a
  migration. Raw summary/article fields may contain upstream HTML; sanitize them before
  rendering in a browser.
- **Parameterized endpoint coverage**: the team-list response supplies the team identifiers
  used by every team-detail route, and the college-football scoreboard supplies the event
  identifiers used by the summary route.
- **Configurable soccer coverage**: soccer is a route template in the Gist rather than one
  concrete league, so `eng.1` and `usa.1` are enabled by default and more slugs can be added
  with `ESPN_SOCCER_LEAGUES`.

## Gist endpoint coverage

| Gist section | Imported resources |
| --- | --- |
| College Football | news, scoreboard, team list, each team detail, event summaries, rankings |
| NFL | news, scoreboard, team list, each team detail |
| MLB | news, scoreboard, team list, each team detail |
| College Baseball | scoreboard |
| NHL | news, scoreboard, team list, each team detail |
| NBA | news, scoreboard, team list, each team detail |
| WNBA | news, scoreboard, team list, each team detail |
| Women's College Basketball | news, scoreboard, team list, each team detail |
| Men's College Basketball | news, scoreboard, team list, each team detail |
| Soccer | scoreboard, news, team list, and each team detail for every configured league slug |

The ESPN site API is undocumented and can change or reject automated requests. The
importer uses the current `site.web.api.espn.com` host, retries rate limits and transient 5xx
responses, limits concurrency, and records failures in `sync_states`. The news endpoint
currently caps `limit` at 50, so the importer stores the latest 50 articles per league. Set
a permitted `ESPN_USER_AGENT` if the upstream service requires one.

## Quick start with Docker

Requirements: Docker Desktop (including Compose).

```bash
cp .env.example .env
docker compose up -d db
docker compose run --rm api sync
docker compose up -d api
```

The API is then available at:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health: <http://localhost:8000/api/v1/health>
- Leagues: <http://localhost:8000/api/v1/leagues>

The one-shot `sync` service waits for MySQL, applies migrations, and runs the importer. Run
it on a schedule (cron, Kubernetes CronJob, or your preferred scheduler) to refresh the
current snapshot. It replaces data only after all required base resources for a league
have been fetched successfully. The default `ESPN_STRICT_SYNC=false` allows an individual team-detail or
summary request to fail while retaining a partial, clearly reported current snapshot; set
`ESPN_STRICT_SYNC=true` when a complete all-or-nothing league import is required. A
committed partial snapshot returns exit code `2` by default so schedulers can detect it;
use `--allow-partial` when that is acceptable.

Compose passes the importer settings from `.env` to the API container while intentionally
using the internal `db:3306` database hostname. The `DATABASE_URL` in `.env.example` is for
local commands run outside Docker. `RUN_MIGRATIONS=true` is convenient for a single API
container; in a multi-replica deployment, run `docker compose run --rm api migrate` as a
one-shot deployment step and set `RUN_MIGRATIONS=false` on the replicas.

To add soccer leagues, edit `ESPN_SOCCER_LEAGUES` in `.env`, for example:

```dotenv
ESPN_SOCCER_LEAGUES=eng.1,usa.1,esp.1,ger.1,uefa.champions
```

## Local development

Use Python 3.10 or newer and a running MySQL 8-compatible server:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
sports-sync leagues
sports-sync sync
uvicorn app.main:app --reload
```

Useful importer options:

```bash
# Synchronize every configured league
sports-sync sync

# Synchronize selected leagues
sports-sync sync --league nfl --league basketball.nba

# Use a scoreboard date and omit the many team-detail requests while testing
sports-sync sync --league nfl --dates 20260924 --no-team-details

# Force team details even when ESPN_INCLUDE_TEAM_DETAILS=false
sports-sync sync --league nfl --team-details

# Abort a league snapshot if any detail request fails
sports-sync sync --league football.college-football --strict

# Allow a committed snapshot with detail warnings to exit successfully
sports-sync sync --league nfl --allow-partial
```

Run the local checks with:

```bash
pytest
ruff check app alembic tests
mypy app
```

## Database design

The migration creates these tables:

- `sports` and `leagues` identify the source and its sport.
- `teams` stores the normalized team identity, branding, record, and source JSON.
- `events` stores scoreboard/summary event identity, time, status, venue, and source JSON.
- `event_competitors` stores each event participant, score, linescores, records, statistics,
  and leaders.
- `news_articles` stores current articles and categories.
- `rankings` and `ranking_entries` store polls and their team positions.
- `sync_states` records the last attempt, successful sync, item count, and error for each
  source resource.

All tables are scoped to a league where source data can belong to more than one league. The
API uses local numeric IDs in URLs and also exposes the upstream `source_id` on resources.
IDs for unchanged event/news/ranking rows are preserved across syncs, but a source item that
disappears and later reappears can receive a new local ID; use `source_id` as the stable
integration key. Timestamps are stored as UTC and serialized with a `Z` suffix.

## Public REST API

All routes are read-only and live under `/api/v1`.

| Route | Description |
| --- | --- |
| `GET /health` | Database connectivity check |
| `GET /leagues` | List leagues; filter with `sport` |
| `GET /leagues/{league_id}` | Get one league |
| `GET /teams` | List teams; filter with `league_id`, `sport`, `source_id`, or `search` |
| `GET /teams/{team_id}` | Team detail, including raw source JSON |
| `GET /events` | Current events; filter by league, sport, source ID, team, status, and date range |
| `GET /events/{event_id}` | Event detail, competitors, and optional college-football summary |
| `GET /news` | Current news; filter by league, sport, source ID, text, and publication date |
| `GET /news/{article_id}` | Article detail and categories |
| `GET /rankings` | Current rankings; filter by league, source ID, season, and week |
| `GET /rankings/{ranking_id}` | Ranking detail and entries |
| `GET /sync-status` | Last source synchronization state |

List endpoints return lightweight event/ranking summaries; use the corresponding detail
route when you need linescores, statistics, leaders, or raw source JSON.

List responses use:

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

Example event query:

```bash
curl 'http://localhost:8000/api/v1/events?sport=basketball&status_state=post&limit=25'
```

## Current-snapshot behavior

This project intentionally does not maintain a historical time series. On a successful
league sync:

1. Stale `events`, `news_articles`, `rankings`, and team rows are removed; unchanged
   event/news/ranking rows are updated in place so their local IDs remain stable.
2. Normalized rows, child competitors/entries, and source JSON are written in one database
   transaction.
3. Teams are upserted by `(league_id, source_id)` and stale teams are removed.
4. `sync_states` records the status, item count, and last successful sync for each resource.

If a required scoreboard, news, team-list, or rankings request fails, the importer records
the error and leaves the previous current rows in place. The importer also uses a MySQL
advisory lock per league to prevent two concurrent syncs from interleaving replacements.

## Configuration

All settings can be supplied as environment variables. See `.env.example` for the complete
list. Important settings are:

- `DATABASE_URL`: SQLAlchemy async MySQL URL.
- `ESPN_BASE_URL`: upstream API base URL.
- `ESPN_SOCCER_LEAGUES`: comma-separated ESPN soccer league slugs.
- `ESPN_INCLUDE_TEAM_DETAILS`: whether to call every parameterized team route.
- `ESPN_STRICT_SYNC`: whether individual detail failures abort a league transaction.
- `ESPN_CONCURRENCY`, `ESPN_TIMEOUT_SECONDS`, and `ESPN_MAX_RETRIES`: importer controls.
- `ESPN_NEWS_LIMIT` and `ESPN_TEAM_LIMIT`: upstream result limits (currently 50 and 1000).
- `CORS_ORIGINS`: comma-separated browser origins allowed by the API.
- `RUN_MIGRATIONS`: Docker-only switch for running Alembic during API startup.

Do not commit `.env` or production credentials.

