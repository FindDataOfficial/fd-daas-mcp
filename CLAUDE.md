# CLAUDE.md — cli-anything

Fork of [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything). The `CLI-Anything/` directory is the upstream — do not modify. Custom work lives in `akshare-agent-harness/`.

## Environment

Use **uv** for dependency and environment management. Python 3.10+.

```bash
uv sync                    # Create venv and install deps
uv run <command>           # Run in the project venv
```

## Construction Docs

Read these for architecture and construction decisions:

- `construction/mcp.md` — unified env, schema package (`mcp/models/`), single database (`mcp/daas.db`), all MCP servers
- `construction/dashboard.md` — Next.js dashboard architecture, sql.js access, schema mirrors
- `construction/daas-storage.md` — how daas stores datasources + columns + indicators (`sources`, `daas_function_columns`, `observations`, the `sources` vs `datasources` gotcha); reusable reference

## Env & Schema (unified)

**Single `.env`**: root `.env` holds `DAAS_DATABASE_URL`, proxy, CKAN portal, dashboard port. Every MCP `server.py` loads `dotenv` from root first, then its own `.env` with `override=True`. Per-MCP `.env` only contains overrides.

**Single schema package**: `mcp/models/` — installable `pyproject.toml` package (`pip install -e mcp/models`). One `Base`, 13 tables across all MCP domains. Schema changes go here first.

**Single database**: `mcp/daas.db` — all MCPs and the dashboard read/write here.

## MCP Servers (`mcp/`)

All MCP servers are under `mcp/`, each in its own `*-mcp` directory.

### mcp/models/ — Shared Schema Package

Installable package with the one SQLAlchemy `Base`. All MCPs depend on it. Tables: `functions`, `function_columns`, `data_snapshots`, `schedules`, `executions`, `tasks`, `sources`, `daas_functions`, `daas_function_columns`, `observations`, `scraw_configs`, `datasources`, `datasource_columns`.

### mcp/leader-mcp/ — Multi-Harness Registry + Data Gateway MCP

Query the unified registry across all harnesses, **and** the single client-facing gateway for live data from the project's data-fetch MCPs, **and** the CrewAI specialist-agent + data-workflow layer. Exposes registry tools (`list_harnesses`, `search_functions`, `get_function_detail`, `list_categories`, `find_functions_by_column`, `list_datasources`, `toggle_datasource`, `save_snapshot`, `list_snapshots`, `query_snapshots`, `get_column_provenance`, `update_column_meta`) **plus data-gateway tools** (`list_data_mcps`, `list_data_mcp_tools`, `call_data_mcp`, `ask_data_crew`, `add_data_mcp`, `remove_data_mcp`, `get_data_mcp`) **plus crewai-data-workflow tools** (`list_agent_models`, `create_specialist_agent`, `list_specialist_agents`, `create_workflow`, `add_workflow_step`, `get_workflow`, `list_workflows`, `run_workflow`, `run_workflow_step`, `get_workflow_run`).

**Data gateway**: the 10 data-fetch MCPs (`akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank`) are **removed from `.mcp.json`** and reached through `leader-mcp` instead. Their stdio launch configs live in the `leader_upstreams` table in `mcp/daas.db` (seeded from `.mcp.json` by `seed_upstreams.py`). `leader-mcp` launches them on demand as stdio subprocesses via `fastmcp.Client` (same primitive `combine-mcp` uses). `ask_data_crew` uses a CrewAI `DataCrew` agent to route NL data requests to the right upstream+tool; when `crewai` is unavailable or no LLM is configured, it falls back to a deterministic direct router. Both paths return the upstream's raw result. Registry-based upstreams (`yfinance`, `akshare`) expose a single dispatch tool (`call_yfinance_function` / `call_akshare_function`) taking `{name, params_json}`; the other 8 expose direct per-operation tools.

**crewai-data-workflow** (`crewai-data-workflow` spec): specialist CrewAI agents (one per data-fetch MCP, each bound to one upstream via a curried `call_data_mcp` so it can only fetch from its MCP) composed into persisted, step-by-step, resumable workflows. Per-agent LLM control via the `LEADER_MODELS` JSON env (`{name: {model, base_url?, api_key?, provider?, vision?}}`, mirroring `process-mcp`'s `PROCESS_MODELS`; shared `LLM_*` fallback). `run_workflow` runs all steps sequentially and returns every step's raw `call_data_mcp` output; `run_workflow_step` runs one step (resume-or-create `in_progress` run); `depends_on` injects a prior step's raw output as text context; `on_fail` ∈ {continue, stop}. Falls back to a deterministic direct `call_data_mcp` call (keyword-parsed, reused from `data_crew`) when `crewai` is unavailable or the agent's model is soft-unconfigured — the fallback is recorded in the step's `meta` so a workflow runs end-to-end without an LLM. A named-but-missing model is a hard error (no fetch). Step `output_json` capped at 1 MB. `--run-workflow <name>` CLI branch runs a workflow in-process for `cron-mcp` scheduling.

- **Entry**: `python3 server.py` (FastMCP, stdio transport). CLI branch: `python3 server.py --run-workflow <name>` (in-process run, prints JSON run summary, exits; for cron-mcp).
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL` env var
- **Models**: `from models import Function, FunctionColumn, DataSnapshot, LeaderUpstream, SpecialistAgent, Workflow, WorkflowStep, WorkflowRun, WorkflowStepResult`
- **Key files**: `server.py`, `leader_tools.py`, `leader_database.py`, `unified_models.py`, `database.py`, `migrate_registry.py`, `registry_service.py`, `leader_crew.py`, `gateway_database.py` (upstream registry + `build_client`), `gateway_tools.py` (gateway + management tools), `data_crew.py` (CrewAI `DataCrew` + direct fallback), `seed_upstreams.py` (migrate `.mcp.json` → `leader_upstreams`), `selfcheck_gateway.py` (offline self-check with stub upstream), `specialist_agents.py` (LLM registry `LEADER_MODELS` + specialist CrewAI tools + `run_specialist_step` + `_direct_fetch`), `workflow_database.py` (agent/workflow/run CRUD singleton), `workflow_tools.py` (the 10 workflow MCP tools + runner), `seed_specialist_agents.py` (one default agent per enabled upstream), `selfcheck_workflow.py` (offline workflow self-check, forces direct fallback)
- **Schema**: `leader_upstreams` table (name, transport, command, args_json, env_json, cwd, enabled, description) + 5 workflow tables (`specialist_agents`, `workflows`, `workflow_steps`, `workflow_runs`, `workflow_step_results`) created via `Base.metadata.create_all` (no Alembic). `workflow→step` and `run→result` are real FKs with `ON DELETE CASCADE`; `agents.upstream` and `steps.agent` are soft refs (validated at write time, no FK).
- **Optional extra**: `[crew]` adds `crewai` + `litellm` (the CrewAI router; gateway + specialist agents fall back to a direct router without it). The CrewAI LLM is built from `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` (the project's shared OpenAI-compatible endpoint) when `OPENAI_API_KEY` is absent. Per-agent override via `LEADER_MODELS` JSON.
- **Seed**: `uv run --directory mcp/leader-mcp python seed_upstreams.py` (idempotent; `--dry-run` plans; `--unseed` removes the rows and prints the `.mcp.json` snippet for rollback). Then `uv run --directory mcp/leader-mcp python seed_specialist_agents.py` (one default `<upstream>-agent` per enabled upstream; idempotent; `--dry-run` / `--unseed`; preserves user-set per-agent `model` on re-seed).
- **Self-check**: `uv run --directory mcp/leader-mcp python selfcheck_gateway.py` (temp DB; stub upstream; no LLM call). `uv run --directory mcp/leader-mcp python selfcheck_workflow.py` (temp DB; stub gateway; forces direct-fallback path; no LLM call).
- Imports use direct relative imports — run from within `mcp/leader-mcp/`

### mcp/cron-mcp/ — Agent Scheduler MCP

AI-agent-driven cron scheduling with SQLite + APScheduler.

- **Entry**: `python3 server.py` or `uv run python server.py`
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Schedule, Execution, Task` (local `models.py` deleted)
- **Key files**: `server.py`, `database.py`, `scheduler.py`, `agent_runner.py`, `registry.py`
- **Dependencies**: `apscheduler>=3.11.2`, `sqlalchemy>=2.0.51`
- Uses relative imports — run from within `mcp/cron-mcp/`

### mcp/daas-mcp/ — DaaS Multi-Source Data MCP

Source-based registry with live function execution, plus datasource management (CRUD, hierarchical categories, form/section/instruction metadata, collections, multi-level search).

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`. SQLite `PRAGMA foreign_keys=ON` enabled per-connection (required for `ON DELETE CASCADE`).
- **Models**: `from models import DaasSource, DaasFunction, DaasFunctionColumn, Observation, Category, DatasourceForm, DatasourceSection, DatasourceCollection, DatasourceCollectionItem, Entity, EntityDatasourceLink` (local `models.py` deleted)
- **Read tools** (5, unchanged): `list_sources`, `search_functions`, `get_function_detail`, `list_categories`, `fetch_data`
- **Management tools** (15): `create_datasource`, `update_datasource`, `delete_datasource`, `create_category`, `move_category`, `delete_category`, `get_category_tree`, `add_form`, `add_section`, `list_forms`, `create_collection`, `add_to_collection`, `list_collection`, `remove_from_collection`, `search_datasources`
- **Entity tools** (6): `search_entities`, `get_entity`, `list_entities`, `get_entity_coverage`, `link_entity_datasource`, `unlink_entity_datasource`. Coverage answers "I have company X — which datasources cover it, how many columns, how do I fetch it": per linked source it returns `identifier_in_source`, the sections (routing instructions with an identifier-prefilled variant), and `column_count`/`columns` from `daas_function_columns` (real for daas-internal sources; `column_hint` → sibling MCP `get_function_info` for external-MCP sources).
- **Schema**: 5 management tables (`categories`, `datasource_forms`, `datasource_sections`, `datasource_collections`, `datasource_collection_items`) + nullable `sources.category_id`; plus 2 entity tables (`entities`, `entity_datasource_links`) for the entity→datasource coverage layer. Created via `Base.metadata.create_all`; existing `daas.db` gets `category_id` via a guarded `ALTER TABLE` in `daas_database.Database._migrate_sources_category_id` (idempotent, no Alembic).
- **Key files**: `server.py`, `daas_tools.py`, `entity_tools.py`, `daas_database.py`, `registry_service.py`, `entity_sync.py`
- **Self-check (collection writer)**: `uv run --directory mcp/daas-mcp python selfcheck_collection_writer.py` — temp DB, no network. Guards the dashboard's `collection_writer.py` sidecar: the `create`/`update`/`delete` subcommands land rows in the connected DB, the duplicate-name error path fires, the `__file__`-based `REPO_ROOT = parents[2]` anchor points at the repo root (and the repo-root `.env` defining `DAAS_DATABASE_URL` lives there), and the TS-side `findRepoRoot()` (`dashboard/scripts/check-repo-root.mjs`, run from a non-`dashboard/` cwd) agrees with the Python anchor. This is the regression guard for the "create new collection" error caused by the writer and the sql.js read path resolving to different DBs.
- **Seed external MCPs into the registry** with `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py` — registers `edgar`, `edinet`, `yfinance`, `cnreport`, `hkex` as datasources and enriches `cnstats`, with category tree, forms/sections (routing grammar `mcp=… tool=… param=k=v` in each `instruction`), and a `core` collection. Idempotent; `--unseed` rolls back; `--dry-run` plans.
- **Sync entities + links** with `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --with akshare --directory mcp/daas-mcp python entity_sync.py --sync-all` — upserts stock entities from akshare (A-shares/HK/US) + a curated country list into `entities`, and auto-derives `entity_datasource_links` by market/country rules (US→edgar+yfinance; A-share→cnreport+yfinance; HK→hkex+yfinance; country→worldbank, +cnstats for CN). Per-market failure isolation; stale codes marked `status='delisted'`. Idempotent upsert on `(entity_type, code)`. Flags: `--sync-stocks`, `--sync-countries`, `--dry-run`, `--register-cron` (installs a weekly cron-mcp `Task` `entity-sync-stocks` + `Schedule` `entity-sync-weekly`, idempotent on names; takes effect on next cron-mcp start). akshare is imported lazily so the daas-mcp server starts without it; `--sync-stocks`/`--sync-all` print a clear error if akshare is absent.
- **Pipeline collections** (managed fetch+cron collections, distinct from the curation `datasource_collections`): 2 tables (`pipeline_collections`, `pipeline_collection_items`) where each item binds a source MCP (`source_mcp` + `tool` + `arguments_json`, e.g. `akshare-mcp` + `call_akshare_function` + `{"name":"stock_zh_a_hist","params_json":"…"}`) to a `scraw_<slug>` storage table + upsert keys + cron cadence. This is the `data_job` shape from `add-cron-mcp-data-fetch`, so items migrate 1:1 later. Adding an enabled item triggers an immediate history backfill (spawn `source_mcp` via `fastmcp.Client`, call `tool`, upsert into `scraw_<slug>`) **and** an idempotent `cron-mcp` `create_task` + `create_schedule`; removing/disabling unwires the schedule. `scraw_<slug>` tables are auto-created on first fetch (queryable via `dashboard-mcp.query_table`; usable as `process-mcp` rule source tables).
  - **Models**: `from models import PipelineCollection, PipelineCollectionItem` (in `mcp/models/`; auto-created via `Base.metadata.create_all`, no Alembic).
  - **Tools** (11): `create_pipeline_collection`, `list_pipeline_collections`, `get_pipeline_collection`, `delete_pipeline_collection`, `list_pipeline_items`, `add_pipeline_item`, `remove_pipeline_item`, `enable_pipeline_item`, `disable_pipeline_item`, `update_pipeline_item`, `sync_pipeline_cron`.
  - **CLI branches** (cron-mcp shell tasks): `python server.py --fetch-item <id>` (re-fetch + upsert), `--register-cron <id>`, `--unregister-cron <id>`, `--sync-cron`. The cron task command is `uv run --directory <repo>/mcp/daas-mcp python server.py --fetch-item <id>`.
  - **Launch-config resolver**: `source_mcp` resolves via `.mcp.json` `mcpServers` OR a `mcp/<source_mcp>/server.py` convention dir; `mcp/models` is injected into `PYTHONPATH` so spawned servers can `import models`. daas-mcp's own `fetch_data` is intentionally NOT used (its `daas-agent-harness` path is mis-resolved and the daas registry has no akshare functions) — the bridge calls the source MCPs directly.
  - **Key files**: `pipeline_tools.py`, `selfcheck_pipeline.py` (`uv run --directory mcp/daas-mcp python selfcheck_pipeline.py`; `AKSHARE_LIVE=1` for a live akshare backfill smoke), `seed_pipeline_from_mapping.py`.
  - **Seed the akshare example**: `uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py` loads the `openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md` needs (沪深日行情, 成交概况, AH比价, 大宗交易, 港股日行情, 研报, 盈利预测, 主营构成, …) into a `pipeline_collection` named `akshare-t-md` (17 items, each driving `akshare-mcp.call_akshare_function` on an off-minute `Asia/Shanghai` cron). Flags: `--dry-run`, `--only <name>`, `--unseed`, `--collection <name>`. Idempotent on collection + item name (re-run updates, no duplicate cron rows). Schedules fire on the next `cron-mcp` start (cron-mcp `load_schedules()` loads enabled rows into APScheduler).

### mcp/dashboard-mcp/ — Dashboard MCP

Browse databases, query tables, manage datasources, get stats.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Datasource, DatasourceColumn, ...` (no more inline CREATE TABLE)
- **Key files**: `server.py`

The Next.js dashboard at `dashboard/` also ships a **NotebookLM-style collections workspace** at `/collections` (and `/collections/[name]`). Three panes: catalog (left, draggable datasources/sections grouped by category) → collection (center, droppable + sortable) → chat (right, scoped to the active collection). Writes go through `dashboard/src/app/api/collections/*` which spawns `uv run --directory mcp/daas-mcp python collection_writer.py …`. Chat uses the same `streamText` + MCP-tools wiring as `/api/chat` but with a collection-aware system prompt; configure `CHAT_PROVIDER`, an API key (e.g. `ANTHROPIC_API_KEY`), and `MCP_SERVER=daas-mcp` in root `.env`.

### mcp/akshare-mcp/ — AKShare Financial Data MCP

Registry queries + live function execution for AKShare (673+ Chinese financial data functions).

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `akshare`, `pandas`, `fastmcp`, plus `akshare-agent-harness/` on `sys.path`

### mcp/yfinance-mcp/ — yfinance (Yahoo Finance) Global Data MCP

Registry queries + live function execution for yfinance (global / US-market data). Mirrors `mcp/akshare-mcp/`. Tools: `search_functions`, `get_function_info`, `list_categories`, `list_functions`, `call_yfinance_function`. Commands starting `ticker_` dispatch via `yfinance.Ticker(symbol).<method>(...)`; top-level commands (`download`, `search`) call `yfinance.<name>(...)` directly.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `yfinance`, `pandas`, `fastmcp`, `sqlalchemy`, `click`, plus `yfinance-agent-harness/` on `sys.path`
- **Database**: harness `yfinance-agent-harness/.../metadata/registry.db` via `YFINANCE_DATABASE_URL` (empty = harness default)
- **Registered in `.mcp.json`** via `uv run --directory mcp/yfinance-mcp python server.py`

### mcp/edgartools-mcp/ — EdgarTools (SEC EDGAR) MCP

Purpose-built (not a registry/harness) live-execution MCP wrapping the `edgar` (EdgarTools) library for SEC EDGAR: company facts, filings, financial statements, and insider trades. Tools: `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_insider_trades`. `edgar` exposes an object model (`Company`/`Filing`/`Financials`), not a flat function catalog, so the yfinance/akshare registry pattern does not apply.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `edgartools`, `pandas`, `fastmcp`, `python-dotenv` (no `sqlalchemy`/`click` — no registry, no CLI)
- **Identity**: SEC requires a descriptive User-Agent; set `EDGAR_IDENTITY="Name email@domain"` in root `.env` (read at startup via `edgar.set_identity`). Tools return a clear error if unset.
- **Database**: none — does not touch `mcp/daas.db` (live-execution only, like `yfinance-mcp`)
- **Registered in `.mcp.json`** via `uv run --directory mcp/edgartools-mcp python server.py`

### mcp/edinet-mcp/ — edinet-tools (Japan EDINET) MCP

Purpose-built (not a registry/harness) live-execution MCP wrapping the `edinet_tools` library for Japan's EDINET disclosure system: entity lookup, document listings, and parsed reports (securities reports, quarterly, large-shareholding, tender offers, ...). Tools: `search_entities`, `get_entity`, `list_documents`, `get_document`, `supported_doc_types`. `edinet_tools` exposes a small object/functional model (`Entity`/`Document`/`ParsedReport`), not a flat function catalog, so the yfinance/akshare registry pattern does not apply.

- **Entry**: `python3 server.py` (FastMCP, stdio transport). Self-check: `python3 server.py --selfcheck`.
- **Dependencies**: `edinet-tools`, `pandas`, `fastmcp`, `python-dotenv` (no `sqlalchemy`/`click` — no registry, no CLI)
- **API key**: `EDINET_API_KEY` required ONLY for `list_documents` / `get_document` (document fetching). `search_entities`, `get_entity`, `supported_doc_types` work keyless. Set in root `.env`; document tools return a clear error if unset.
- **Database**: none — does not touch `mcp/daas.db` (live-execution only, like `edgartools-mcp`)
- **Registered in `.mcp.json`** via `uv run --directory mcp/edinet-mcp python server.py`

### mcp/dartlab-mcp/ — dartlab (Korea DART + US EDGAR) MCP

Purpose-built (not a registry/harness) live-execution MCP wrapping the `dartlab` library for Korea DART (and US EDGAR) corporate filings: normalized financial panels, in-filing text search, filing links, independent credit ratings (dCR), deep analysis, and market-wide scans. Tools: `company_panel`, `panel_search`, `list_filings`, `get_credit`, `analyze`, `scan`. `dartlab` exposes an object model (`Company(ticker)` → `.panel()`/`.credit()`/`.analysis()`; top-level `scan`), not a flat function catalog, so the registry pattern does not apply. dartlab ships a built-in `dartlab mcp`, but it exposes generic agent tools (`ask`/`RunPython`/`WebSearch`), not its data surface — this server wraps the data API directly.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `dartlab`, `pandas`, `fastmcp`, `python-dotenv` (no `sqlalchemy`/`click` — no registry, no CLI). `requires-python>=3.12` (dartlab's floor) — isolated in this MCP's own venv.
- **API key**: KEYLESS for basic use (pre-built parquet auto-downloads from HuggingFace on first call). An optional `DART_API_KEY` (free, opendart.fss.or.kr; multi-key `DART_API_KEYS`) in root `.env` enables raw re-collection via `dartlab.OpenDart()` — not required for the tools here.
- **Database**: none — does not touch `mcp/daas.db` (live-execution only, like `edgartools-mcp`)
- **Registered in `.mcp.json`** via `uv run --directory mcp/dartlab-mcp python server.py`

### mcp/cnreport-mcp/ — Chinese Annual Report MCP

Purpose-built MCP for Chinese A-share filings: edgartools-style company API (CNINFO-backed lookup, filings list, structured financials via akshare) **plus** PDF section extraction, LLM structured extraction, and Elasticsearch store/search. Thirteen tools total:

- **Company API** (7, CNINFO-backed): `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_section`, `list_report_types`, `get_special_report`. `get_company` accepts a 6-digit ticker or Chinese/English name. `list_filings` filters by `form` (`年度报告` / `半年度报告` / `第一季度报告` / `第三季度报告`) **or** `category` (any CNINFO category code or Chinese name from the catalog, e.g. `招股说明书` / `category_sf_szsh`); `form` and `category` are mutually exclusive. `get_financials` returns three statements (`income_statement` / `balance_sheet` / `cashflow`) as `{columns, data}` records — shape matches `edgartools-mcp.get_financials`. `get_section` is the bridge: `(ticker, year, section)` → resolved PDF URL → existing outline-extraction pipeline. `list_report_types` browses the CNINFO disclosure category catalog (grouped). `get_special_report` retrieves a special-type report by category (招股说明书 / 收购报告书 / 业绩预告 / …), with optional section extraction reusing the outline pipeline.
- **Outline extraction** (2): `list_outline`, `extract_section` — fetch a report URL/path, parse 目录, extract one section's body text by exact title / regex / 1-based ordinal.
- **AI processing** (1): `ai_extract` — LLM structured extraction against a JSON Schema.
- **Elasticsearch** (3): `index_records`, `search_reports`, `delete_index` — bulk index extracted records into `cnreport-{year}`, BM25 + filter search with highlights.
- **Category registry**: `cninfo_categories.json` (data-driven, sourced from CNINFO's own `history-notice.js` via akshare) is the source of truth for CNINFO category codes. `_FORM_CATEGORIES` is derived from it at import. Adding a report type = editing that JSON (no code change); see `load_categories()` / `resolve_category()` in `cninfo_client.py`.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `fastmcp`, `httpx`, `pypdf`, `jsonschema`, `elasticsearch`, `akshare>=1.13`, `pandas`, `mcp-models`
- **API key**: KEYLESS for CNINFO + akshare (the company API). `ai_extract` needs `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`; the ES tools need `ES_URL` (optional `ES_API_KEY` or `ES_USERNAME` / `ES_PASSWORD`). No `EDGAR_IDENTITY`-equivalent required.
- **Database**: writes provenance to `mcp/daas.db` via `mcp-models` (`Document` / `Section` / `EsIndex` rows); company-API tools are stateless and do NOT touch the DB.
- **Self-check**: `uv run python selfcheck.py` (uses a temp DB; CNINFO + akshare mocked)
- **Tests**: `uv run --with pytest python -m pytest test_cnreport.py -v -p no:logfire` (offline)
- **Registered in `.mcp.json`** via `uv run --directory mcp/cnreport-mcp python server.py`

### mcp/combine-mcp/ — Composite MCP

Curate a composite MCP: pick named tools from multiple upstream MCP servers (proxied verbatim) and define chained tools (linear pipelines across upstreams). One composite served per process, selected by `COMPOSITE` env. Selection persisted in `daas.db`; management tools (`list_composites`, `add_upstream`, `list_available_tools`, `add_tool`, `add_chained_tool`, ...) always present. Served tool names are `<upstream>_<tool>` (mount namespace). Selection changes apply on restart.

- **Entry**: `python3 server.py` (FastMCP, stdio). `.mcp.json` entry sets `COMPOSITE=example`.
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Composite, Upstream, CompositeTool, CompositeChain`
- **Key files**: `server.py`, `combine_database.py`, `combine_tools.py`, `seed_example.py`, `selfcheck.py`
- **Self-check**: `uv run python selfcheck.py` (uses a temp DB; does not touch `daas.db`)
- **Seed shipped example**: `uv run python seed_example.py`
- Imports use direct relative imports — run from within `mcp/combine-mcp/`

### mcp/hkreport-mcp/ — Hong Kong Stock Exchange Report MCP

Purpose-built (not a registry/harness) live-execution MCP for HK-listed companies. Same shape as `edgartools-mcp` (five tools, four names identical) with `get_disclosure_calendar` replacing `get_insider_trades` (HK has no Form-4 equivalent agents query). Tools: `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_disclosure_calendar`. Hand-rolled HKEXnews HTTP client (no maintained Python library exists) plus `akshare`'s `stock_financial_hk_report_em` for normalized income/balance/cashflow.

- **Entry**: `python3 server.py` (FastMCP, stdio transport). Self-check: `uv run python selfcheck.py`.
- **Dependencies**: `fastmcp`, `httpx`, `pypdf`, `akshare>=1.13`, `pandas`, `python-dotenv` (no `sqlalchemy`/`click` — no registry, no CLI)
- **API key**: KEYLESS — HKEXnews + akshare HK endpoints are public. Optional `HTTPS_PROXY`/`HTTP_PROXY` honored.
- **Database**: none — does not touch `mcp/daas.db` (live-execution only, like `edgartools-mcp`)
- **Tests**: `uv run --with pytest python -m pytest test_hkreport.py -v -p no:logfire` (offline; HTTP mocked via `respx`, akshare patched). `HKREPORT_LIVE=1` enables two live smoke tests against ticker `00700`.
- **Registered in `.mcp.json`** via `uv run --directory mcp/hkreport-mcp python server.py`

### mcp/process-mcp/ — Multi-Model LLM Extraction + Math Indicators MCP

Env-configurable LLM extraction (long text + images) with persisted rules drivable by `cron-mcp`. Generalizes `cnreport-mcp.ai_extract`: chunked map-reduce so long text is **not** truncated, optional vision via a `vision`-flagged model, multi-model registry via one `PROCESS_MODELS` JSON env. Reads scraped source data from `scraw_<slug>` tables (created by the scrape skills / scrapling-mcp; the slug matches `scraw_configs.name` and `sources.config.scraw_config`) and writes extracted records to a shared `process_results` table.

Also computes **deterministic math indicators** (pandas one-liners: `sma`, `ema`, `rsi`, `pct_change`, `log_return`, `diff`, `rolling_std`, `rolling_min`, `rolling_max`, `zscore`, `ratio`, `level`) over a datasource's columns and upserts the resulting series into the daas `observations` table — reusing the project's existing indicator store (see `construction/daas-storage.md`). The LLM path and the indicator path share storage but not logic: the LLM path is forbidden from touching daas tables; only the indicator path writes `observations`.

- **Tools (19 = 11 LLM + 8 indicator)**:
  - LLM (11): `list_models`, `list_source_tables`, `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`.
  - Indicator (8): `list_indicator_ops`, `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`, `calculate`. Ad-hoc `calculate` computes without persisting; rule tools persist a binding for replay.
- **Entry**: `python3 server.py` (FastMCP, stdio transport). Self-check: `uv run python selfcheck.py` (uses a temp DB; no LLM call required; exercises the indicator round-trip too).
- **Cron CLI branches**: `python server.py --run-rule <name>` (LLM) or `--run-indicator <name>` (indicator) runs the path in-process, prints a JSON summary, exits — no stdio server. Wire a cron job via `cron-mcp`: `create_task(name="proc_<rule>", command="uv run --directory /Users/chengsishi/code/cli-anything/mcp/process-mcp python server.py --run-rule <name>")` (or `--run-indicator`) + `create_schedule(name=..., cron_expr=..., task="proc_<rule>")`.
- **Dependencies**: `fastmcp`, `httpx`, `jsonschema`, `pypdf`, `sqlalchemy`, `python-dotenv`, `mcp-models`, `pandas>=2.0` (no `openai` SDK — OpenAI-compatible `/chat/completions` via `httpx`; numpy comes transitively via pandas).
- **Env**: `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (shared single-model fallback) and optional `PROCESS_MODELS` JSON. Each entry maps a name to `{model, vision?, base_url?, api_key?}` — per-model values override the shared `LLM_*`. Example: `PROCESS_MODELS={"fast":{"model":"gpt-4o-mini"},"eyes":{"model":"gpt-4o","vision":true}}`. Extraction tools return a clear `{"error":...}` (no network call) when the chosen model is unconfigured or a vision tool targets a non-vision model. Indicator tools need no LLM key.
- **Database**: shared `mcp/daas.db` via `DAAS_DATABASE_URL`. Three tables — `process_rules` (rule name, source_table, text_column, schema_json, prompt, model, max_chars, enabled, `last_rowid` cursor, optional `datasource` for daas traceability) and `process_results` (rule_id FK CASCADE, source_table, source_rowid, extracted_json, model, run_at; unique on `(rule_id, source_table, source_rowid)` → idempotent upsert) for the LLM path; `indicator_rules` (name, datasource, function_name, source_table, date_column, value_column, op, params_json, indicator_name, enabled; soft ref to `sources.name`, no FK) for the indicator path. `run_rule` reads `rowid > last_rowid`, batch-capped at 500 per tick; `run_indicator` does a full recompute (no cursor — windowed ops need lookback) and upserts into `observations` on `(source=datasource, function_name, indicator=indicator_name, date)`, `value` stored as `str()`, `metadata` carrying `{rule_name, op, params, value_column}`. SQLite `PRAGMA foreign_keys=ON` is set per-connection so `delete_rule` cascades to `process_results`. Relative `sqlite:///` URLs are resolved against the repo root so the `--run-rule` / `--run-indicator` cron path works under `uv run --directory`.
- **Source-data naming rule (`scraw_<slug>`)**: scraped data tables follow this convention; `list_source_tables` introspects `sqlite_master` for `scraw_*` (excluding `scraw_configs`) and returns each with row count + columns. `create_rule` / `create_indicator` validate the source table + columns exist in `sqlite_master` / `PRAGMA table_info` and validate identifiers against `^[A-Za-z_][A-Za-z0-9_]*$` before any SQL — guard against injection on the dynamic table/column names (they cannot be bind parameters). Indicator rules accept any table in `daas.db`, not just `scraw_*`.
- **daas integration**: the LLM path (`run_rule` / `extract_*`) is traceability only — a rule's optional `datasource` points at `sources.name`; it does NOT read or write daas registry tables (`sources`, `daas_functions`, `observations`, `datasource_*`). The indicator path is the exception: `run_indicator` writes computed series to `observations` (no new results table). `process_results` and `observations` are both queryable via `dashboard-mcp.query_table(database="daas", table=...)`.
- **Key files**: `server.py`, `process_tools.py` (LLM call + ad-hoc extract tools), `indicator_tools.py` (math-op catalog + ad-hoc `calculate`), `process_database.py` (singleton, rule/indicator CRUD, source discovery, identifier guard, `observations` upsert, `run_indicator`), `selfcheck.py`.
- **Registered in `.mcp.json`** via `uv run --directory mcp/process-mcp python server.py`

### Other MCPs

`ckan-mcp/`, `cnstats-mcp/`, `worldbank-mcp/` — dotenv loading added, otherwise unchanged. `scrapling-*-mcp/` — own `init_db.py`.

## akshare-agent-harness

CLI wrapper for AKShare (673+ Chinese financial data functions). Click-based, with REPL.

```bash
# Install (from akshare-agent-harness/)
uv pip install -e ".[dev,repl]"

# Run CLI
uv run cli-anything-akshare              # REPL mode (default)
uv run cli-anything-akshare search 历史行情
uv run cli-anything-akshare call stock_zh_a_hist symbol=000001 start_date=20250101
uv run cli-anything-akshare --json call stock_sse_summary

# Run tests
uv run pytest -v                         # 8 unit + 6 E2E (from akshare-agent-harness/)
```

- Python >=3.10, depends on `click`, `pandas`, `akshare`
- Registry at `cli_anything/akshare/metadata/registry.json` (673 functions, 430 categories)
- `AKSHARE_REGISTRY` env var overrides registry path (falls back to auto-detected paths)
- Tests skip if `akshare` package not installed (`@pytest.mark.skipif`)
- E2E CLI tests use `_resolve_cli("cli-anything-akshare")` — falls back to `python -m`
- Two skill files: canonical at `skills/cli-anything-akshare/SKILL.md`, compatibility copy at `cli_anything/akshare/skills/SKILL.md`
- Run `AKSHARE.md` for agent-specific analysis of the AKShare adaptation

## yfinance-agent-harness

CLI wrapper for yfinance (Yahoo Finance global / US-market data). Click-based, with REPL. Mirrors the akshare harness layout; the proxy subcommand group is omitted (yfinance does not need it).

```bash
# Install (from yfinance-agent-harness/)
uv pip install -e ".[dev,repl]"

# Run CLI
.venv/bin/cli-anything-yfinance                       # REPL mode (default)
.venv/bin/cli-anything-yfinance search history
.venv/bin/cli-anything-yfinance call ticker_history symbol=AAPL period=1mo
.venv/bin/cli-anything-yfinance list --json

# Seed the registry DB
.venv/bin/python -m cli_anything.yfinance.core.migrate_registry

# Run tests (from yfinance-agent-harness/)
.venv/bin/python -m pytest -v                         # 17 tests
```

- Python >=3.10, depends on `click`, `pandas`, `yfinance`, `sqlalchemy`
- Curated registry at `cli_anything/yfinance/core/seed.py` (hand-curated, not scraped); mirrored into `cli_anything/yfinance/metadata/registry.db` via `migrate_registry.py`
- Two-table schema (`functions` / `function_columns`), same as the akshare harness
- `YFINANCE_DATABASE_URL` env var overrides the DB URL (empty = harness default)
- Command convention: `ticker_<method>` → `yfinance.Ticker(symbol).<method>(...)`; top-level (`download`, `search`) → `yfinance.<name>(...)`
- Tests skip live calls when `yfinance` not installed (`@pytest.mark.skipif`); E2E uses `_resolve_cli("cli-anything-yfinance")` → falls back to `python -m`
- Skill file: `skills/cli-anything-yfinance/SKILL.md`

## CLI-Anything (upstream)

Contains 60+ generated CLI harnesses in `<software>/agent-harness/` directories.

- **All use the same pattern**: `setup.py`, `cli_anything/<name>/` namespace (PEP 420 — no `__init__.py` in `cli_anything/`)
- **Generated by** `/cli-anything <path>` command (available via Claude Code plugin or OpenCode commands)
- **HARNESS.md** at `CLI-Anything/cli-anything-plugin/HARNESS.md` — the authoritative methodology spec
- Run harness tests: `cd <software>/agent-harness && uv run pytest -v`
- Force-installed mode: `CLI_ANYTHING_FORCE_INSTALLED=1 uv run pytest -v -s`
- CI: `check-root-skills.yml` validates root SKILL.md matches packaged copy on PR

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at /Users/chengsishi/code/cli-anything/specs/001-daas-provider/plan.md
<!-- SPECKIT END -->
