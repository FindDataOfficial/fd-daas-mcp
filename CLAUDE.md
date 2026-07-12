# CLAUDE.md - cli-anything

Fork of [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything). The `CLI-Anything/` directory is the upstream - do not modify.

## Architecture (skill + sqlite)

Data fetch is **skill-driven**: skills call Python data libraries (`akshare`, `yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`) directly and read/write `daas.db` via `sqlite3`. The consolidated **`fd-daas-mcp`** MCP server is the sole entry in repo-root `.mcp.json` - it hosts the `alerts`/`cron`/`composite`/`daas`/`dashboard`/`leader` tool groups (170 tools) behind one stdio server and one `fd-daas-mcp` Click CLI. The thin consolidation layer is `fd-daas-mcp/cli_anything/fd_daas_mcp/` (`server.py`/`registry.py`/`cli.py`/`selfcheck.py`); each group's tool code lives in-package at `fd-daas-mcp/<group>-mcp/`. Server and CLI both consume `registry.build()` so the surfaces cannot drift. Launch: `fd-daas-mcp/bin/fd-daas-mcp-server`; tests: `fd-daas-mcp/.venv/bin/python -m pytest fd-daas-mcp/tests`; selfcheck: `fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.selfcheck`.

The replacement layer lives in `.claude/skills/skill-based-data-fetch/`:
- `SKILL.md` - the resolve -> fetch -> persist workflow.
- `scripts/db.py` - shared sqlite3 helper (reads `DAAS_DATABASE_URL` from the repo-root `.env`, resolves relative `sqlite:///` paths against the repo root, `PRAGMA foreign_keys=ON`, backup helper).
- `scripts/dispatch.py` - maps each source prefix (`akshare_`/`yfinance_`/`edgar_`/`edinet_`/`dartlab_`/`worldbank_`/`wbdata_`/`cnstats_`/`ckan_`) to its Python import + call shape. Run `uv run python .claude/skills/skill-based-data-fetch/scripts/dispatch.py --resolve <func>` to get the snippet for a function.
- `scripts/run_indicator.py` - deterministic math indicators (`sma`/`ema`/`rsi`/`pct_change`/`log_return`/`diff`/`rolling_std`/`rolling_min`/`rolling_max`/`zscore`/`ratio`/`level`); reads `indicator_rules` + a source table, upserts into `observations`. Usage: `<name>` | `--calc <table> <date> <value> <op> [k=v ...]` | `--list-ops`.
- `scripts/upsert.py` - persist fetched records into `scraw_<slug>` (auto-CREATE + ALTER + INSERT OR REPLACE) or `observations`. Backs up `daas.db` first.

Dashboard registry: `.claude/skills/fd-daas-dashboard-creator/scripts/register_dashboard.py` (CRUD over the `dashboards` table + regenerates `dashboards/index.html` + `daas.md`; idempotent upsert by slug). Dashboard HTML lives at repo-root `dashboards/` (configurable via `DASHBOARDS_DIR`).

## Environment

Use **uv**. Python 3.10+ (dartlab needs 3.12 - run it via `uv run --python 3.12 --with dartlab ...`).

```bash
uv sync                    # provision the root venv (data libs as deps)
uv run python <script>     # run a script
uv run --with <lib> python -c "..."   # ad-hoc with an extra lib
```

**Single `.env`** at repo root: `DAAS_DATABASE_URL` (currently `sqlite:///mcp/daas.db`), proxy, `EDGAR_IDENTITY`, `EDINET_API_KEY`, `MASSIVE_API_KEY`. The scripts load `.env` automatically.

## daas.db

SQLite file at the path in `DAAS_DATABASE_URL` (resolved against repo root). Holds the registry + data:
- `sources`, `daas_functions`, `daas_function_columns` - datasource/function/column catalog.
- `entities`, `entity_datasource_links` - stocks/countries + their source identifiers.
- `indicator_rules` - indicator bindings (name, datasource, source_table, date_column, value_column, op, params_json, indicator_name, enabled, score).
- `observations` - computed indicator series, keyed on `(source, function_name, indicator, date)`, `value` as VARCHAR(64).
- `dashboards` - standalone-HTML dashboard registry (slug, name, intro, source_tables, entity_coverage, time_range, refresh_cadence, chart_config, file_path, file_url).
- `scraw_<slug>` - scraped/fetched source-data tables (auto-created by `upsert.py`).
- `entity_collections`, `entity_collection_items`, `entity_collection_changes` - named entity groups + audit log.
- `indicator_collections`, `indicator_collection_items`, `indicator_collection_changes` - named indicator groups + audit log.

Query it directly: `sqlite3 mcp/daas.db "SELECT ..."` (from repo root). `PRAGMA foreign_keys=ON` for FK cascade.

## Skills (`.claude/skills/`)

- `skill-based-data-fetch` - resolve entity+indicator via sqlite3, call the Python lib, persist (the core fetch skill).
- `fd-daas-fetch-data` - entity -> coverage -> indicator workflow (sqlite3 + the scripts).
- `fd-daas-indicators-creator` - persist a series to a `scraw_<slug>` table (no cron - manual refresh).
- `fd-daas-dashboard` / `fd-daas-dashboard-creator` - browse/build standalone HTML dashboards.
- `fd-daas-research` - orchestrate analyze -> [collection] -> indicators -> dashboard.
- `fd-daas-entities-collection` / `fd-daas-entities-collection-creator` - entity collections + rules.
- `fd-daas-indicators-collection-creator` - indicator collections + CSV/md export.
- `fd-skill-creator`, `openspec-*` - infra/workflow skills.

**Removed** (do not reference): all `fd-*` CLI harnesses (`fd-akshare`/`fd-yfinance`/`fd-dartlab`/`fd-edgar`/`fd-edinet`/`fd-world`), `fd-daas-workflow-creator`, `fd-daas-scraw-scrapling`, `fd-daas-scrapling-scraw-creator`, `fd-daas-cli-datasource-entities-builder`, and the per-source `mcp__*` tools. The cron scheduler, alert engine, CrewAI workflow layer (leader), and composite/pipeline MCPs are **not removed** - they are folded into `fd-daas-mcp` as `cron-mcp`/`alerts-mcp`/`leader-mcp`/`composite-mcp` and register under `<group>_<tool>` on the consolidated server. The `pdf`/`scrapling`/`firecrawl`/`massive` groups were lost with the prior `fd-daas-mcp` and are dropped (documented in `registry.py` with archived-restore-spec pointers). For skill-driven fetches, refresh is manual (re-run the fetch+upsert).

## Construction Docs

- `construction/mcp.md` - (stale - describes the removed MCP servers; to be updated)
- `construction/daas-storage.md` - `sources`/`daas_function_columns`/`observations` schema reference (data model still valid; access is sqlite3 not MCP tools)

## CLI-Anything (upstream)

Contains 60+ generated CLI harnesses in `<software>/agent-harness/` directories. `CLI-Anything/` is the upstream - do not modify.
