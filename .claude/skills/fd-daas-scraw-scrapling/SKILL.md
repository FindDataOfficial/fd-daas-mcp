---
name: fd-daas-scraw-scrapling
description: |
  Scrape structured data from URLs and save scraping configurations to a SQLite
  database. When the user provides a URL and wants to extract data from it
  (tables, lists, news items, product grids, search results), use this skill.
  It fetches the page via scrapling (uv or Docker), helps clarify target columns
  with the user when not specified, creates reusable scraper scripts, and persists
  the scraping configuration (URL + columns) to the DAAS scraw database. Has
  two MCP servers available: scrapling-uv-mcp (preferred, uv-managed Python) and
  scrapling-docker-mcp (Docker container). Triggers on phrases like "scrape this
  URL", "get data from this page", "extract columns from", "爬取", "抓取数据",
  "save this scraping config", "add this source to the database", or whenever
  the user pastes a URL and asks to pull structured data from it.
---

# fd-daas-scraw-scrapling

Scrape data from URLs, clarify target columns with the user, and save scraping
configurations to a SQLite database.

## Two runtimes

This skill works with two scrapling MCP servers. Prefer uv (faster, no Docker
overhead); fall back to Docker when scrapling isn't installed or the user
prefers isolation.

| Runtime | MCP server | How scripts run |
|---------|-----------|-----------------|
| **uv** (preferred) | `scrapling-uv-mcp` | `uv run --directory mcp/scrapling-uv-mcp python scripts/<script>.py` |
| **docker** | `scrapling-docker-mcp` | `docker run -i --rm -v ... scrapling-mcp python /app/scripts/<script>.py` |

Both share the same DB schema and the same `daas.db` file at `mcp/daas.db`.

### Runtime detection

Check which runtime is available:

```bash
# uv path
uv run --directory mcp/scrapling-uv-mcp python -c "from scrapling.fetchers import Fetcher; print('ok')" 2>&1

# docker path
docker image inspect scrapling-mcp >/dev/null 2>&1 && echo "ok" || echo "not built"
```

Use whichever returns "ok". If both work, use uv. If neither works, build the
Docker image: `cd mcp/scrapling-docker-mcp && docker build -t scrapling-mcp .`

## Workflow

### Step 1: Receive the URL

User gives a URL. They may or may not specify what data they want.

### Step 2: Determine if columns are specified

**If the user specified target columns** (e.g., "get the title, date, and link"):
- Skip to Step 4.

**If the user did NOT specify columns** (e.g., "scrape this page"):
- Go to Step 3.

### Step 3: Fetch and show structure (discovery mode)

Fetch the page using scrapling to understand its structure.

**uv path:**

```bash
uv run --directory mcp/scrapling-uv-mcp python -c "
from scrapling.fetchers import Fetcher
page = Fetcher().get('<URL>')
print(page.get_all_text(strip=True)[:3000])
"
```

**docker path:**

```bash
docker run -i --rm scrapling-mcp python -c "
from scrapling.fetchers import Fetcher
page = Fetcher().get('<URL>')
print(page.get_all_text(strip=True)[:3000])
"
```

Analyze the page content and present the user with:

1. **What data is on this page** (categories, tables, lists)
2. **Suggested columns** — the natural fields you can extract (e.g., title, date, URL, description)
3. **Column meanings** — explain what each column represents

Ask the user to confirm or adjust. Wait for the user's response before proceeding.

### Step 4: Create or reuse a scraper script

Once columns are confirmed, write a Python script in the active runtime's
`scripts/` directory that:

1. Fetches the page with scrapling (`Fetcher().get(url)`)
2. Extracts the agreed columns using CSS selectors
3. Outputs JSON to stdout (`json.dumps(records, ensure_ascii=False, indent=2)`)

If a script for the same URL pattern already exists, update it instead of creating a new one.

**Script location:**
- uv: `mcp/scrapling-uv-mcp/scripts/<name>.py`
- docker: `mcp/scrapling-docker-mcp/scripts/<name>.py`

**Run the script:**

uv path:
```bash
uv run --directory mcp/scrapling-uv-mcp python scripts/<name>.py
```

docker path:
```bash
docker run -i --rm \
  -v "$(pwd)/mcp/scrapling-docker-mcp/scripts:/app/scripts:ro" \
  --entrypoint python scrapling-mcp /app/scripts/<name>.py
```

Present the extracted data to the user.

### Step 5: Save config to database

After the user confirms the data looks correct, ensure the DB tables exist,
then save the configuration.

**uv path:**

```bash
uv run --directory mcp/scrapling-uv-mcp python scripts/init_db.py
uv run --directory mcp/scrapling-uv-mcp python scripts/db_helper.py save "<name>" "<url>" '<columns_json>'
```

**docker path:**

```bash
docker run -i --rm \
  -v "$(pwd)/mcp/scrapling-docker-mcp/scripts:/app/scripts:ro" \
  --entrypoint python scrapling-mcp /app/scripts/init_db.py

docker run -i --rm \
  -v "$(pwd)/mcp/scrapling-docker-mcp/scripts:/app/scripts:ro" \
  --entrypoint python scrapling-mcp /app/scripts/db_helper.py save "<name>" "<url>" '<columns_json>'
```

The `columns_json` is a JSON array:
```json
[
  {"name": "title", "type": "string", "description": "news headline"},
  {"name": "date", "type": "string", "description": "publish date"},
  {"name": "url", "type": "string", "description": "full article link"}
]
```

## Scripts

### uv runtime (mcp/scrapling-uv-mcp/)

| File | Purpose |
|------|---------|
| `.env` | `DAAS_SCRAW_DATABASE_URL=sqlite:///../daas.db` |
| `scripts/init_db.py` | Create `scraw_configs` table (SQLAlchemy, idempotent) |
| `scripts/db_helper.py` | CRUD: save/list/get/delete scraping configs |

### docker runtime (mcp/scrapling-docker-mcp/)

| File | Purpose |
|------|---------|
| `.env` | `DAAS_SCRAW_DATABASE_URL` + `SCRAPLING_DOCKER_IMAGE` |
| `scripts/init_db.py` | Create `scraw_configs` table |
| `scripts/db_helper.py` | CRUD: save/list/get/delete scraping configs |
| `scripts/fetch_mofcom_news.py` | Example: MOFCOM news scraper (reference) |
| `scripts/fetch_mofcom_news.sh` | Shell wrapper for the MOFCOM scraper |

## Database schema

Table: `scraw_configs` (shared by both runtimes, stored in `mcp/daas.db`)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| url | VARCHAR(2048) | The scraped URL |
| name | VARCHAR(255) | Human-readable name |
| columns_json | JSON | Array of `{name, type, description}` objects |
| created_at | DATETIME | Auto-set on creation |
| updated_at | DATETIME | Auto-set on update |

## Querying saved configs

**uv:** `uv run --directory mcp/scrapling-uv-mcp python scripts/db_helper.py list`

**docker:** `docker run -i --rm -v "$(pwd)/mcp/scrapling-docker-mcp/scripts:/app/scripts:ro" --entrypoint python scrapling-mcp /app/scripts/db_helper.py list`

## Principles

- **Prefer uv over Docker.** It's faster and doesn't need a build step. Only use Docker when uv isn't available.
- **Discover before asking.** If the user didn't specify columns, fetch the page first so you can show them what's actually there — don't make them guess.
- **Clarify column meanings.** Each column needs a description so future users know what it contains.
- **Save after confirming.** Never save to the database until the user has seen the extracted data and approved it.
- **Reuse scripts.** If a scraper script already exists for the same URL pattern, update it rather than creating a new one.
- **Sync scripts between runtimes.** When you create a scraper script for one runtime, mirror it to the other runtime's `scripts/` directory so it's available regardless of which path is active.
