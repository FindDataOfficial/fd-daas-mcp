## Why

daas-mcp catalogs 673+ data functions across 6+ datasources (edgar, edinet, yfinance, cnstats, cnreport, hkex, akshare) but has no concept of the *entities* those datasources describe. Today there is no way to ask "what can I get for Apple?" or "which datasources cover 平安银行?" — you must already know the ticker, the right MCP, and the right tool. An entity table (stocks + important countries) linked to the existing daas datasources lets you search one company name and immediately see (a) how many columns are available across the datasources that cover it and (b) the exact routing instruction to fetch each kind of data.

## What Changes

- **New `entities` table** in daas.db: unified store for stocks and countries, keyed by a type discriminator (`stock` | `country`), with name, ticker, code, exchange, country_code, ISIN, aliases (JSON), status, and metadata (JSON).
- **New `entity_datasource_links` table**: many-to-many between `entities` and `sources` (the existing daas datasources), carrying `identifier_in_source` (the ticker/code/CIK to use inside that datasource) and coverage metadata. Unique on `(entity_id, source_id)`.
- **6 new daas-mcp tools**: `search_entities`, `get_entity`, `list_entities`, `get_entity_coverage`, `link_entity_datasource`, `unlink_entity_datasource`. The coverage tool answers the example query — given an entity it returns each covering datasource with its identifier, the available sections (routing instructions = how to get the data), and the column count/list aggregated from `daas_function_columns` where the source has registered functions.
- **New `entity_sync.py` script** in daas-mcp: fetches stock lists from akshare (A-shares, HK, US, and other markets akshare covers) plus a curated country seed, upserts entities, and auto-derives datasource links by market/country rules (e.g. US stock → edgar + yfinance; A-share → cnreport + akshare; HK stock → hkex + akshare).
- **Cron auto-update**: a cron-mcp `Task` (`entity-sync-stocks`) + `Schedule` (weekly) registered idempotently by the sync script's `--register-cron` flag, so the stock list stays current without manual intervention.
- **Schema additions** in `mcp/models/models.py`: `Entity`, `EntityDatasourceLink` models; tables created via `Base.metadata.create_all` (idempotent, no Alembic).

## Capabilities

### New Capabilities
- `entity-registry`: Store and query entities (stocks + important countries) in daas.db — the `entities` table plus `search_entities`, `get_entity`, `list_entities` daas-mcp tools.
- `entity-datasource-coverage`: Link entities to the daas `sources` and answer "what data can I get for this entity" — `entity_datasource_links` table plus `get_entity_coverage`, `link_entity_datasource`, `unlink_entity_datasource` tools. Coverage returns per-datasource identifier, routing instructions (sections), and column counts.
- `entity-sync`: Auto-populate entities + links from akshare stock lists and a curated country seed on a cron schedule — `entity_sync.py` script + cron-mcp task/schedule registration.

### Modified Capabilities
None — additive only; no existing spec requirements change.

## Impact

- **`mcp/models/models.py`**: add `Entity`, `EntityDatasourceLink` models (2 new tables).
- **`mcp/daas.db`**: 2 new tables via `Base.metadata.create_all`.
- **`mcp/daas-mcp/`**: new `entity_tools.py` (6 tools) + new `entity_sync.py` (sync script); `server.py` registers the 6 tools.
- **`mcp/cron-mcp/`**: no code change — reuses existing `tasks`/`schedules` tables; the sync script registers the task + schedule via direct DB rows (idempotent on task name + schedule name).
- **Dependencies**: `akshare` already a project dep (akshare-mcp); `fastmcp`, `sqlalchemy`, `python-dotenv` already used by daas-mcp. No new deps.
- **Existing tools unaffected** — new tables and tools are purely additive.
