# CLAUDE.md - DAAS


## Architecture (skill + sqlite)

Data fetch is **skill-driven**: skills call Python data libraries (`akshare`, `yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`) directly and read/write `daas.db` via `sqlite3`. The consolidated **`fd-daas-mcp`** MCP server is the sole entry in repo-root `.mcp.json` - it hosts the `alerts`/`cron`/`composite`/`daas`/`dashboard`/`leader`/`pdf`/`research` tool groups (176 tools; `pdf` optional, gated on `sqlite-vec`) behind one stdio server and one `fd-daas-mcp` Click CLI. The thin consolidation layer is `fd-daas-mcp/daas/fd_daas_mcp/` (`server.py`/`registry.py`/`cli.py`/`selfcheck.py`); each group's tool code lives in-package at `fd-daas-mcp/<group>-mcp/`. Server and CLI both consume `registry.build()` so the surfaces cannot drift. Launch: `fd-daas-mcp/bin/fd-daas-mcp-server`; tests: `fd-daas-mcp/.venv/bin/python -m pytest fd-daas-mcp/tests`; selfcheck: `fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck`. The `leader` group's data-fetch gateway routes to a single **`fd-open-data-mcp`** upstream (a concept-based semantic fetcher with ranking/failover/caching) - a Python dependency sourced from the sibling `~/finddata/fd-open-data-mcp` repo, launched from the DAAS venv as `python -m fd_open_data_mcp.server`. It replaces the 11 former per-source data-fetch MCPs (akshare/yfinance/edgartools/edinet/dartlab/cnreport/hkreport/ckan/cnstats/worldbank/massive); `ask_data_crew` + the specialist-agent layer are removed (callers use `call_data_mcp('fd-open-data-mcp', 'read', …)` directly, or `build_workflow_from_goal` for multi-step fetches).

The replacement layer lives in `.claude/skills/fd-daas-based-data-fetch/`:
- `SKILL.md` - the resolve -> fetch -> persist workflow.
- `scripts/db.py` - shared sqlite3 helper (reads `DAAS_DATABASE_URL` from the repo-root `.env`, resolves relative `sqlite:///` paths against the repo root, `PRAGMA foreign_keys=ON`, backup helper).
- `scripts/dispatch.py` - maps each source prefix (`akshare_`/`yfinance_`/`edgar_`/`edinet_`/`dartlab_`/`worldbank_`/`wbdata_`/`cnstats_`/`ckan_`) to its Python import + call shape. Run `uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve <func>` to get the snippet for a function.
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

**Single `.env`** at repo root: `DAAS_DATABASE_URL` (currently `sqlite:///daas.db`, i.e. the git-tracked repo-root `daas.db`; **optional for external users** - unset, it defaults to `./daas.db` (writable cwd) or `~/.fd-daas-mcp/daas.db`, and `fd-daas-mcp init` provisions it), `HTTP_PROXY`, `EDGAR_IDENTITY`, `EDINET_API_KEY`, `LLM_*`/`LEADER_MODEL*` (leader agent), `ALERTS_FEISHU_WEBHOOK_URL`, `DASHBOARD_PORT`, `CKAN_PORTAL_URL`. The scripts load `.env` automatically.

## daas.db

SQLite file at the path in `DAAS_DATABASE_URL` (relative `sqlite:///` paths resolve against repo root; the canonical DB is the git-tracked repo-root `daas.db`). Holds the registry + data:
- `sources`, `daas_functions`, `daas_function_columns` - datasource/function/column catalog.
- `entities`, `entity_datasource_links` - stocks/countries + their source identifiers.
- `indicator_rules` - indicator bindings (name, datasource, source_table, date_column, value_column, op, params_json, indicator_name, enabled, score).
- `observations` - computed indicator series, keyed on `(source, function_name, indicator, date)`, `value` as VARCHAR(64).
- `dashboards` - standalone-HTML dashboard registry (slug, name, intro, source_tables, entity_coverage, time_range, refresh_cadence, chart_config, file_path, file_url).
- `scraw_<slug>` - scraped/fetched source-data tables (auto-created by `upsert.py`).
- `entity_collections`, `entity_collection_items`, `entity_collection_changes` - named entity groups + audit log (collections carry an optional `rule_id` -> `rules`).
- `indicator_collections`, `indicator_collection_items`, `indicator_collection_changes` - named indicator groups + audit log (collections carry an optional `rule_id` -> `rules`).
- `rules` - the unified rule store (`name`, `rule_type` ∈ json/script/position/llm, `target` ∈ entity_ids/indicator_names/rows, `config_json`, `enabled`); evaluated by `RuleEngine` (`fd-daas-mcp/daas-mcp/rule_engine.py`) and attached to collections via `rule_id`. `process_results` (LLM extraction output) now FK->`rules.id` (the legacy `process_rules` table is dropped; the `llm` rule type subsumes it).
- `pdf_documents`/`pdf_meta`/`pdf_chunks` (+ `pdf_chunks_vec` `vec0`) - local PDF/text vector-search store (sqlite-vec), populated by the `fd-daas-pdf` skill / `pdf` MCP group.
- `researches` - persisted research bundle (name, status, entity_collection_name, indicator_collection_name, dashboard_slug, pipeline_collection_name, component_refs JSON, report_md, report_path) tying a study's components + generated markdown report together; managed by the `research` MCP group (`research_create`/`get`/`list`/`update`/`delete`/`generate_report`/`refresh`/`add_component`/`remove_component`).

Query it directly: `sqlite3 daas.db "SELECT ..."` (from repo root). `PRAGMA foreign_keys=ON` for FK cascade.

## Skills (`.claude/skills/`)

- `fd-daas-based-data-fetch` - resolve entity+indicator via sqlite3, call the Python lib, persist (the core fetch skill; formerly `skill-based-data-fetch`).
- `fd-daas-fetch-data` - entity -> coverage -> indicator workflow (sqlite3 + the scripts).
- `fd-datasource-akshare` - A-share OHLCV/fundamentals via the external `scraw-akshare` Scrapy project (PostgreSQL at `localhost:5432/finddata`).
- `fd-daas-indicators-creator` - persist a series to a `scraw_<slug>` table (no cron - manual refresh).
- `fd-daas-dashboard` / `fd-daas-dashboard-creator` - browse/build standalone HTML dashboards.
- `fd-daas-research` - orchestrate analyze -> [collection] -> indicators -> dashboard -> persist as a `research` bundle + generate a markdown report via the `research_*` MCP tools (`research_create`/`research_generate_report`/`research_refresh`); auto-detects prior researches + brainstorm plans (refresh vs. rebuild) and emits a `skill-run-notification` block.
- `fd-daas-brainstorm` - clarify a research goal via dialogue + investment-method/master references -> `daas-doc/research/<plan>.md` (no `daas.db` state); offers hand-off to `fd-daas-research`.
- `fd-daas-entities-collection` / `fd-daas-entities-collection-creator` - entity collections + rules.
- `fd-daas-indicators-collection-creator` - indicator collections + CSV/md export.
- `fd-daas-rules-creator` - author a unified rule (json/script/position/llm) via `daas_create_rule`, attach to a collection, dry-run, sync.
- `fd-daas-pdf` - local PDF/text semantic vector search (sqlite-vec + sentence-transformers into `daas.db`); backs the `pdf` MCP group.
- `fd-daas-scrapling-official` - web scraping with anti-bot bypass via the Scrapling library (a skill, not the dropped scrapling MCP group).
- `fd-daas-skill-creator` / `fd-daas-skill-review` - create/inspect and review/test+repair daas skills (wrap `fd-coding-skill-creator` + the `skill_smoke_test.py` L1 harness; share the `skill-run-notification` convention + the `fd-daas-skills-test-suite` defect vocabulary).
- `fd-coding-daas-scraw-builder` - scaffold `scraw-*` Scrapy projects (scrapy + scrapy-redis + scrapyd + scrapyd-web stack).
- `fd-coding-skill-creator`, `fd-coding-daas-datasource-builder` (+ `-workspace`), `fd-coding-daas-reset-project` (reset `daas.db` to clean at 3 guarded levels: test-artifacts/data-only/full-baseline; backup + dry-run + `--yes`), `openspec-*` - infra/workflow skills.
- `fd-coding-bore-tunnel` / `fd-coding-cloudflare-tunnel` - expose local services (e.g. dashboards) to the internet.

**Removed** (do not reference): all `fd-*` CLI harnesses (`fd-akshare`/`fd-yfinance`/`fd-dartlab`/`fd-edgar`/`fd-edinet`/`fd-world`), `fd-daas-workflow-creator`, `fd-daas-scraw-scrapling`, `fd-daas-scrapling-scraw-creator`, `fd-daas-cli-datasource-entities-builder`, and the per-source `mcp__*` tools. The cron scheduler, alert engine, workflow layer (leader, reworked to direct `fd-open-data-mcp` gateway calls; `ask_data_crew` + specialist agents removed), and composite/pipeline MCPs are **not removed** - they are folded into `fd-daas-mcp` as `cron-mcp`/`alerts-mcp`/`leader-mcp`/`composite-mcp` and register under `<group>_<tool>` on the consolidated server. MCP groups: `pdf` was **restored** (optional, gated on `sqlite-vec`); `scrapling`/`firecrawl`/`massive` remain dropped (archived restore-specs in `registry.py`). The `fd-daas-scrapling-official` skill drives the Scrapling library directly and is unrelated to the dropped scrapling MCP group. For skill-driven fetches, refresh is manual (re-run the fetch+upsert).

## Construction Docs

- `construction/mcp.md` - (stale - describes the removed MCP servers; to be updated). `construction/daas-storage.md` was removed; the live schema reference is the `daas.db` table list above plus `db.py`/`upsert.py`.



# the related data provider project
project root dir
~/finddata

dataprovider porject
fd-aksahre
fd-yfinance
fd-world
fd-cn-report
fd-cn-gov