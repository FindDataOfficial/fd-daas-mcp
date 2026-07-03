## Context

daas-mcp is the project's source-based data registry. Today it models **datasources** (`sources` table — edgar, edinet, yfinance, cnstats, cnreport, hkex, akshare, ckan, worldbank) and, under each, **forms** + **sections** (`datasource_forms`, `datasource_sections`). Each section carries a routing instruction in a tiny grammar (`mcp=<mcp-name> tool=<tool-name> param=<k>=<v> ...`) so an agent can dispatch to the right sibling MCP. For the daas-internal sources (ckan/cnstats/worldbank) the registry also stores `daas_functions` + `daas_function_columns` (real column metadata). For external-MCP sources (edgar/edinet/yfinance/cnreport/hkex) the seed registers only forms/sections — columns live in the sibling MCP's own registry.

What is missing is the **entity** layer: the stocks, indices, and countries these datasources describe. There is no table of "all A-shares" or "all US-listed stocks" or "important countries", and no link from an entity to the datasources that cover it. So an agent cannot answer "I have company X — which datasources have data on it, how many columns can I get, and how do I fetch it?" without already knowing the ticker and the right MCP.

The cron-mcp already provides AI-agent-driven scheduling: a `Task` (name + shell command) and a `Schedule` (cron expression + task name) backed by APScheduler. The `process-mcp` change established the pattern of a `--run-rule` CLI branch on a stdio MCP server so cron can drive it; that pattern is reused here.

Constraints:
- Single shared schema package `mcp/models/` — new tables go there first.
- Single shared DB `mcp/daas.db` — new tables created via `Base.metadata.create_all`, idempotent, no Alembic (matches the `categories`/`datasource_forms` precedent).
- daas-mcp `server.py` is a stdio FastMCP app; long-running sync must be a separate script driven by cron, not a tool call.
- No new runtime dependencies — `akshare`, `fastmcp`, `sqlalchemy`, `python-dotenv` are all already present.

## Goals / Non-Goals

**Goals:**
- One `entities` table holding stocks (multi-market) and important countries, queryable by name/ticker/code/alias.
- A many-to-many link from entities to the existing daas `sources`, carrying the identifier to use inside each datasource.
- A coverage tool that, given an entity, returns per-datasource: identifier, available sections (routing instructions = how to get the data), and column count/list where the source has registered `daas_function_columns`.
- A sync script that populates entities + auto-derives links from akshare stock lists + a curated country seed, runnable on demand and on a cron schedule.
- Idempotent cron registration so the stock list refreshes weekly without manual intervention.
- Zero impact on existing daas-mcp tools and tables.

**Non-Goals:**
- Registering akshare/yfinance function catalogs into `daas_functions` (the external-MCP sources stay routed via section instructions, per the existing seed design). Column counts for those sources are answered via the section's sibling-MCP hint, not a local join.
- Real-time price data storage (entities are reference data — name/ticker/code/market — not time series; time series stay in `observations` / sibling MCPs).
- A dashboard UI for entities (the dashboard already has a collections workspace; an entity browser is a follow-up).
- Auto-resolving every identifier (e.g. EDGAR CIK). Where the datasource's lookup tool accepts the ticker directly, the ticker is stored; CIK resolution happens at fetch time inside that MCP.
- Delisting/delta detection beyond a `status` flag set by the sync (full corporate-action history is out of scope).

## Decisions

### Decision 1: One unified `entities` table with a type discriminator

**Chosen**: A single `entities` table with an `entity_type` column (`stock` | `country`, extensible) and nullable market-specific fields (`ticker`, `exchange`, `country_code`, `isin`).

**Rationale**: Stocks and countries are both "things datasources describe". A unified table lets `search_entities` and `get_entity_coverage` work identically across types, and lets a future `index`/`fund`/`commodity` type land as another row value rather than a new table. The shared fields (`name`, `code`, `country_code`, `aliases_json`, `metadata_json`, `status`) cover both; stock-only fields (`ticker`, `exchange`, `isin`) are nullable.

**Alternative considered**: Separate `stocks` and `countries` tables. Rejected — duplicates the link/coverage/tool logic for each type, and the coverage query ("what data can I get for this thing") is identical.

### Decision 2: Natural key is `(entity_type, code)`; `code` is the canonical market code

**Chosen**: `UNIQUE(entity_type, code)`. For stocks, `code` is the canonical market code (6-digit for A-shares e.g. `600519`, 5-digit for HK e.g. `00700`, ticker for US e.g. `AAPL`). For countries, `code` is ISO 3166-1 alpha-2 (`CN`, `US`, `JP`). `ticker` is stored separately for display and for sources that expect the ticker form.

**Rationale**: A single canonical `code` per type makes dedup across syncs trivial (upsert on `(entity_type, code)`), and akshare's stock-list functions already return a stable code per market. `ticker` is kept because yfinance/edgar expect tickers, not 6-digit codes.

**Alternative considered**: `isin` as natural key. Rejected — ISIN is unavailable for many markets akshare lists and is overkill for countries.

### Decision 3: Link table carries `identifier_in_source`

**Chosen**: `entity_datasource_links(entity_id, source_id, identifier_in_source, coverage, metadata_json, last_fetched_at)` with `UNIQUE(entity_id, source_id)`. `identifier_in_source` is the value to plug into the source's lookup tool (e.g. for AAPL → yfinance: `AAPL`; → edgar: `AAPL` since `get_company` accepts a ticker; → cnreport for 平安银行: `000001`).

**Rationale**: The same entity is identified differently in different datasources. Storing the per-source identifier at link time means the coverage tool can hand the agent a ready-to-use routing instruction (`mcp=edgartools-mcp tool=get_company param=ticker_or_cik=AAPL`) with zero extra lookups. This directly answers "how to get the data".

**Alternative considered**: Store one identifier on the entity and let each source translate. Rejected — translation rules differ per source and per market; storing the resolved identifier is simpler and the sync already knows the market.

### Decision 4: Coverage tool resolves columns from `daas_function_columns`; falls back to section hints for external-MCP sources

**Chosen**: `get_entity_coverage(entity_id)` returns, per linked source:
- `identifier_in_source`
- `sections`: list of `{form_type, section_name, instruction}` — the routing instructions (this is "how to get the data")
- `column_count` + `columns`: aggregated from `daas_function_columns` joined to `daas_functions` for that `source_id` (real column metadata)
- where `column_count == 0` (external-MCP sources with no `daas_functions`), a `column_hint` naming the sibling MCP + the function name embedded in the section instruction, so the caller can run that MCP's `get_function_info` to retrieve columns

**Rationale**: daas-internal sources (ckan/cnstats/worldbank) have real column metadata in `daas_function_columns` — use it. External-MCP sources (edgar/edinet/yfinance/cnreport/hkex) deliberately don't (per the seed design); their "data shape" lives in the sibling MCP. The section instruction already names the sibling MCP and tool, so the coverage tool parses it once and returns the hint rather than silently returning 0 columns. This keeps the answer honest without coupling daas-mcp to every sibling's registry.

**Alternative considered**: Mirror every sibling MCP's function catalog into `daas_functions` during seed. Rejected — large row count (akshare alone is 673 functions), duplicates the harness registries, and the section-instruction routing already exists for these sources.

### Decision 5: Sync uses akshare for stock lists; countries are a static curated seed

**Chosen**: `entity_sync.py` calls akshare's market-list functions (`stock_info_a_code_name` for A-shares, `stock_hk_spot_em` for HK, `stock_us_spot_em` for US, plus the TW/SG markets akshare covers) via the akshare harness / akshare-mcp, upserting `entities` with `entity_type='stock'`. Countries come from a hard-coded `COUNTRIES` list (ISO alpha-2 + name for ~30 "important" markets) upserted with `entity_type='country'`.

**Rationale**: akshare is already a project dependency and uniquely offers *list-all* endpoints across multiple markets (yfinance is ticker-only — it cannot enumerate "all US-listed stocks"). Countries are a small, stable reference set; a static seed is simpler and more reliable than scraping an ISO source. akshare's list functions are the single source of truth for "which stocks exist".

**Alternative considered**: yfinance for US stocks. Rejected — no list-all capability. EDGAR's company index for US. Rejected — heavier and US-only; akshare already covers US via `stock_us_spot_em`.

### Decision 6: Auto-derive links by market/country rules at sync time

**Chosen**: The sync applies a small rule table to derive `entity_datasource_links` from each entity's market/country:
- US stock → `edgar` (identifier=ticker), `yfinance` (ticker)
- A-share (SSE/SZSE) → `cnreport` (6-digit code), `akshare` (6-digit code), `yfinance` (ticker, via `.SS`/`.SZ` suffix)
- HK stock → `hkex` (5-digit code), `akshare` (5-digit code), `yfinance` (`.HK` suffix)
- Japan stock → `edinet` (4-digit ticker)
- Country entity → `cnstats` (for CN), `worldbank` (all), `ckan` (best-effort)

Manual `link_entity_datasource` / `unlink_entity_datasource` tools let users override.

**Rationale**: Auto-derivation makes the link table useful immediately after sync without manual curation. The rules are deterministic from market/country, which the sync already has. Manual override handles edge cases (ADRs, dual-listings, indices).

**Alternative considered**: No auto-derivation — manual links only. Rejected — the table would start empty and the coverage tool would be useless until each of thousands of stocks is hand-linked.

### Decision 7: Identifier strategy — store the value the datasource's lookup tool accepts

**Chosen**: `identifier_in_source` is whatever the section's routing instruction's `<ask-agent>` placeholder expects, pre-resolved. Concretely:
- edgar → ticker (edgartools `get_company` accepts ticker)
- yfinance → ticker (yfinance `Ticker(symbol)`)
- cnreport → 6-digit A-share code (`get_company` accepts ticker)
- hkex → 5-digit HK code (`get_company` accepts `ticker_or_name`)
- edinet → 4-digit ticker (`get_entity` accepts ticker)
- akshare → the code the relevant akshare function expects (6-digit A-share / 5-digit HK / etc.)

**Rationale**: This makes the coverage tool's routing instruction directly executable — the agent copies `param=ticker_or_cik=AAPL` and calls the tool. No second lookup, no CIK table to maintain.

**Alternative considered**: Store EDGAR CIK during sync by calling `get_company` per stock. Rejected — thousands of round-trips at sync time; the ticker already works with `get_company`.

### Decision 8: Cron wiring via direct DB rows, idempotent on names

**Chosen**: `entity_sync.py --register-cron` inserts a cron-mcp `Task` (name `entity-sync-stocks`, command `uv run --directory mcp/daas-mcp python entity_sync.py --sync-stocks`) and a `Schedule` (name `entity-sync-weekly`, cron `17 3 * * 1` — weekly Mon 03:17 local) directly into the `tasks`/`schedules` tables, idempotent on the `name` unique key. APScheduler picks the schedule up on next cron-mcp start (or immediately if cron-mcp exposes a reload; otherwise on restart).

**Rationale**: The cron-mcp `create_task`/`create_schedule` tools are MCP tool calls — awkward to invoke from a shell script. Direct DB insert into the same tables (using the shared `models.Task`/`Schedule`) is simple and idempotent. The schedule name is the dedup key.

**Alternative considered**: Drive the sync as a cron-mcp `agent` task (LLM-driven). Rejected — this is a deterministic fetch+upsert, not an agent task; a shell command is cheaper and more reliable. Make the cron-mcp server call the tool. Rejected — would couple cron-mcp to daas-mcp internals.

## Risks / Trade-offs

- **akshare list functions change / rate limits** → Mitigation: sync is idempotent and re-runnable; failures log and leave prior data intact; weekly cadence is gentle. The sync catches per-market exceptions independently so one market's failure doesn't abort the others.
- **Identifier drift** (ticker changes, delistings) → Mitigation: `status` field (`active`/`delisted`); sync sets `delisted` for codes that vanish from the akshare list (doesn't delete the row, preserving link history). Manual `link_entity_datasource` covers corporate-action edge cases.
- **Column counts are 0 for external-MCP sources** → Mitigation: coverage tool returns a `column_hint` (sibling MCP + tool name) so the caller can fetch columns via that MCP's `get_function_info`. Documented in the tool output, not silently 0.
- **Cron schedule not loaded until cron-mcp restart** → Mitigation: `--register-cron` prints a note that the schedule takes effect on next cron-mcp start (consistent with how `load_schedules()` works at startup). Acceptable for a weekly job.
- **Large entity count** (A-shares ~5000, US ~3000, HK ~2600) → Mitigation: indexes on `(entity_type, code)`, `name`, `ticker`; `search_entities` uses LIKE + alias JSON search with a `limit`. Upsert is batched.
- **akshare dependency in daas-mcp venv** → Mitigation: `entity_sync.py` imports akshare lazily inside `--sync-stocks` so the daas-mcp server (which doesn't need akshare) still starts if akshare is absent; the sync prints a clear error if akshare isn't installed.

## Migration Plan

1. Add `Entity`, `EntityDatasourceLink` to `mcp/models/models.py` (additive — no existing column changes).
2. On next daas-mcp / dashboard-mcp / cron-mcp start, `Base.metadata.create_all` creates the two new tables in `daas.db`. No data migration — tables start empty.
3. Run `uv run --directory mcp/daas-mcp python entity_sync.py --sync-all` once to populate entities + links.
4. Run `uv run --directory mcp/daas-mcp python entity_sync.py --register-cron` once to install the weekly refresh schedule.
5. Restart cron-mcp so APScheduler loads the new schedule.

**Rollback**: drop the two tables (`DROP TABLE entity_datasource_links; DROP TABLE entities;`), delete the `entity-sync-stocks` task + `entity-sync-weekly` schedule, remove the new tool registrations from `server.py`. No existing data is touched.

## Open Questions

- Should the country seed lean on the existing `cnstats`/`worldbank` category tree for its "important" list, or stay a hard-coded set? → Current decision: hard-coded ~30 markets, overridable later.
- Do we want `get_entity_coverage` to optionally call the sibling MCPs live to fetch real column lists for external-MCP sources? → Deferred; the `column_hint` is enough for v1 and avoids cross-MCP call latency in the coverage tool.
