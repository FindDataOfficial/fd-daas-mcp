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

Query the unified registry across all harnesses, **and** the single client-facing gateway for live data from the project's data-fetch MCPs, **and** the CrewAI specialist-agent + data-workflow layer. Exposes registry tools (`list_harnesses`, `search_functions`, `get_function_detail`, `list_categories`, `find_functions_by_column`, `list_datasources`, `toggle_datasource`, `save_snapshot`, `list_snapshots`, `query_snapshots`, `get_column_provenance`, `update_column_meta`) **plus data-gateway tools** (`list_data_mcps`, `list_data_mcp_tools`, `call_data_mcp`, `ask_data_crew`, `add_data_mcp`, `remove_data_mcp`, `get_data_mcp`) **plus crewai-data-workflow tools** (`list_agent_models`, `list_model_tiers`, `create_specialist_agent`, `list_specialist_agents`, `update_specialist_agent`, `delete_specialist_agent`, `create_workflow`, `add_workflow_step`, `get_workflow`, `list_workflows`, `build_workflow_from_goal`, `run_workflow`, `run_workflow_step`, `get_workflow_run`).

**Data gateway**: the 10 data-fetch MCPs (`akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank`) are **removed from `.mcp.json`** and reached through `leader-mcp` instead. Their stdio launch configs live in the `leader_upstreams` table in `mcp/daas.db` (seeded from `.mcp.json` by `seed_upstreams.py`). `leader-mcp` launches them on demand as stdio subprocesses via `fastmcp.Client` (same primitive `composite-mcp` uses). `ask_data_crew` uses a CrewAI `DataCrew` agent to route NL data requests to the right upstream+tool; when `crewai` is unavailable or no LLM is configured, it falls back to a deterministic direct router. Both paths return the upstream's raw result. Registry-based upstreams (`yfinance`, `akshare`) expose a single dispatch tool (`call_yfinance_function` / `call_akshare_function`) taking `{name, params_json}`; the other 8 expose direct per-operation tools.

**crewai-data-workflow** (`crewai-data-workflow` spec): specialist CrewAI agents (one per data-fetch MCP, each bound to one upstream via a curried `call_data_mcp` so it can only fetch from its MCP) composed into persisted, step-by-step, resumable workflows. Per-agent LLM control via the `LEADER_MODELS` JSON env (`{name: {model, base_url?, api_key?, provider?, vision?}}`, mirroring daas-mcp's `PROCESS_MODELS`; shared `LLM_*` fallback). **Model tiers**: three role aliases `high` / `balance` / `fast` map to `LEADER_MODELS` entries via the `LEADER_MODEL_HIGH` / `LEADER_MODEL_BALANCE` / `LEADER_MODEL_FAST` env vars; a tier alias is accepted anywhere a `model` is accepted (agents, steps, builder). A workflow step with `model=null` defaults to the `fast` tier at run time (data-fetch default); `build_workflow_from_goal(goal, name?, description?, model="high")` decomposes a natural-language goal into an ordered set of specialist-agent steps via a `high`-tier LLM and persists them. `run_workflow` runs all steps sequentially and returns every step's raw `call_data_mcp` output; `run_workflow_step` runs one step (resume-or-create `in_progress` run); `depends_on` injects a prior step's raw output as text context; `on_fail` ∈ {continue, stop}. Falls back to a deterministic direct `call_data_mcp` call (keyword-parsed, reused from `data_crew`) when `crewai` is unavailable or the agent's model is soft-unconfigured — the fallback is recorded in the step's `meta` so a workflow runs end-to-end without an LLM. `build_workflow_from_goal` falls back to a deterministic single-step workflow under the same conditions. A named-but-missing model (or a dangling tier alias) is a hard error (no fetch). Step `output_json` capped at 1 MB. `--run-workflow <name>` CLI branch runs a workflow in-process for `cron-mcp` scheduling. **Agent CRUD**: `create_specialist_agent` + `list_specialist_agents` are joined by `update_specialist_agent` (editable `role`/`goal`/`backstory`/`model`/`enabled`/`upstream`; `name` immutable; `model` omitted = unchanged via a `_UNSET` sentinel, `model=null` = clear the override → shared `LLM_*` fallback; re-validates a changed `upstream`) and `delete_specialist_agent` (refuses with a clear error naming the referencing workflow(s) when a `workflow_steps.agent` row still points at the agent — soft ref, no cascade; delete or re-point the step first).

- **Entry**: `python3 server.py` (FastMCP, stdio transport). CLI branch: `python3 server.py --run-workflow <name>` (in-process run, prints JSON run summary, exits; for cron-mcp).
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL` env var
- **Models**: `from models import Function, FunctionColumn, DataSnapshot, LeaderUpstream, SpecialistAgent, Workflow, WorkflowStep, WorkflowRun, WorkflowStepResult`
- **Key files**: `server.py`, `leader_tools.py`, `leader_database.py`, `unified_models.py`, `database.py`, `migrate_registry.py`, `registry_service.py`, `leader_crew.py`, `gateway_database.py` (upstream registry + `build_client`), `gateway_tools.py` (gateway + management tools), `data_crew.py` (CrewAI `DataCrew` + direct fallback), `seed_upstreams.py` (migrate `.mcp.json` → `leader_upstreams`), `selfcheck_gateway.py` (offline self-check with stub upstream), `specialist_agents.py` (LLM registry `LEADER_MODELS` + model-tier resolver `high`/`balance`/`fast` + specialist CrewAI tools + `run_specialist_step` + `_direct_fetch`; null step model defaults to `fast`), `workflow_database.py` (agent/workflow/run CRUD singleton), `workflow_tools.py` (the 14 workflow MCP tools + runner + `build_workflow_from_goal` LLM builder), `seed_specialist_agents.py` (one default agent per enabled upstream, `model="fast"`), `selfcheck_workflow.py` (offline workflow self-check, forces direct fallback), `selfcheck_tiers.py` (offline tier-resolver self-check: set/unset/dangling tiers + `list_model_tiers` shape)
- **Schema**: `leader_upstreams` table (name, transport, command, args_json, env_json, cwd, enabled, description) + 5 workflow tables (`specialist_agents`, `workflows`, `workflow_steps`, `workflow_runs`, `workflow_step_results`) created via `Base.metadata.create_all` (no Alembic). `workflow→step` and `run→result` are real FKs with `ON DELETE CASCADE`; `agents.upstream` and `steps.agent` are soft refs (validated at write time, no FK).
- **Optional extra**: `[crew]` adds `crewai` + `litellm` (the CrewAI router; gateway + specialist agents fall back to a direct router without it). The CrewAI LLM is built from `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` (the project's shared OpenAI-compatible endpoint) when `OPENAI_API_KEY` is absent. Per-agent override via `LEADER_MODELS` JSON; role-based tier aliases (`LEADER_MODEL_HIGH` / `_BALANCE` / `_FAST`) name `LEADER_MODELS` entries and are accepted wherever a `model` is accepted.
- **Seed**: `uv run --directory mcp/leader-mcp python seed_upstreams.py` (idempotent; `--dry-run` plans; `--unseed` removes the rows and prints the `.mcp.json` snippet for rollback). Then `uv run --directory mcp/leader-mcp python seed_specialist_agents.py` (one default `<upstream>-agent` per enabled upstream with `model="fast"`; idempotent; `--dry-run` / `--unseed`; preserves user-set per-agent `model` on re-seed).
- **Self-check**: `uv run --directory mcp/leader-mcp python selfcheck_gateway.py` (temp DB; stub upstream; no LLM call). `uv run --directory mcp/leader-mcp python selfcheck_workflow.py` (temp DB; stub gateway; forces direct-fallback path; no LLM call). `uv run --directory mcp/leader-mcp python selfcheck_tiers.py` (hermetic; tier resolver set/unset/dangling + `list_model_tiers` shape; no LLM call).
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
- **Management tools** (16): `create_datasource`, `update_datasource`, `delete_datasource`, `create_category`, `move_category`, `delete_category`, `get_category_tree`, `add_form`, `add_section`, `list_forms`, `create_collection`, `add_to_collection`, `list_collection`, `remove_from_collection`, `set_collection_item_score`, `search_datasources`. `create_datasource`/`update_datasource` accept an optional `score` (default priority/quality weight; `update_datasource` also takes `clear_score=true` to reset to NULL). `add_to_collection` accepts an optional `score` to set a per-collection override at add time. `set_collection_item_score(collection_name, source_name, section_name?, score)` sets/clears (`score=null`) a per-collection override on an existing item. `list_collection` returns each item's resolved `score` (item override if set, else datasource default, else NULL) plus raw `item_score` and `source_default_score`. The `score` columns live on `sources` (default) and `datasource_collection_items` (override); added via guarded `ALTER TABLE` migrations `_migrate_sources_score` / `_migrate_collection_items_score` in `daas_database.py`.
- **Entity tools** (6): `search_entities`, `get_entity`, `list_entities`, `get_entity_coverage`, `link_entity_datasource`, `unlink_entity_datasource`. Coverage answers "I have company X — which datasources cover it, how many columns, how do I fetch it": per linked source it returns `identifier_in_source`, the sections (routing instructions with an identifier-prefilled variant), and `column_count`/`columns` from `daas_function_columns` (real for daas-internal sources; `column_hint` → sibling MCP `get_function_info` for external-MCP sources).
- **Schema**: 5 management tables (`categories`, `datasource_forms`, `datasource_sections`, `datasource_collections`, `datasource_collection_items`) + nullable `sources.category_id`; plus 2 entity tables (`entities`, `entity_datasource_links`) for the entity→datasource coverage layer. Created via `Base.metadata.create_all`; existing `daas.db` gets `category_id` via a guarded `ALTER TABLE` in `daas_database.Database._migrate_sources_category_id` (idempotent, no Alembic).
- **Key files**: `server.py`, `daas_tools.py`, `entity_tools.py`, `daas_database.py`, `registry_service.py`, `entity_sync.py`
- **Self-check (collection writer)**: `uv run --directory mcp/daas-mcp python selfcheck_collection_writer.py` — temp DB, no network. Guards the dashboard's `collection_writer.py` sidecar: the `create`/`update`/`delete` subcommands land rows in the connected DB, the duplicate-name error path fires, the `__file__`-based `REPO_ROOT = parents[2]` anchor points at the repo root (and the repo-root `.env` defining `DAAS_DATABASE_URL` lives there), and the TS-side `findRepoRoot()` (`dashboard/scripts/check-repo-root.mjs`, run from a non-`dashboard/` cwd) agrees with the Python anchor. This is the regression guard for the "create new collection" error caused by the writer and the sql.js read path resolving to different DBs.
- **Self-check (scores)**: `uv run --directory mcp/daas-mcp python selfcheck_scores.py` — temp DB, no network. Guards the score concept end-to-end through the `collection_writer.py set-source-score` / `set-item-score` subcommands + `RegistryService`: default-score set/clear, `add_to_collection(score=…)`, per-item override set/clear with the item-overrides-default resolution rule, `list_collection` surfacing `item_score` / `source_default_score` / resolved `score`, and the not-found error paths.
- **Seed external MCPs into the registry** with `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py` — registers `edgar`, `edinet`, `yfinance`, `cnreport`, `hkex` as datasources and enriches `cnstats`, with category tree, forms/sections (routing grammar `mcp=… tool=… param=k=v` in each `instruction`), and a `core` collection. Idempotent; `--unseed` rolls back; `--dry-run` plans.
- **Seed Massive.com endpoints + indicators** with `uv run --directory mcp/daas-mcp python seed_massive_endpoints.py` — registers Massive.com's 37 REST endpoints as `daas_functions` under the existing `massive` source (organized by asset-class `category`: Reference/Stocks/Options/Crypto/Forex/Futures/Indices/Economy/Alternative), each with `daas_function_columns` (response columns, sampled once via `search_endpoints`/`call_api` and hard-coded) + a `parameters` JSON `{path, method, query_params, gated}`, AND creates `indicator_rules` (sma/ema/pct_change/zscore/rolling_std/level) over the 4 Economy time-series endpoints (Treasury yields, inflation, inflation expectations, labor market) pointing at `scraw_massive_<slug>` tables. 12 endpoints are entitlement-gated (HTTP 403: real-time crypto/forex/indices, options last-trade, forex conversion, futures snapshot/quotes/trades, alt merchant data) → registered as metadata (`parameters.gated=true`), not backfilled, no indicators. No-network at seed time (hard-coded constants; runs without `massive`/`fastmcp` installed). Idempotent; `--dry-run` plans; `--unseed` removes only the functions+columns+indicators it owns (leaves the `massive` source / `default` form / 3 sections / `core` item intact); `--no-indicators` skips indicators. Run order: seed → backfill → `run_indicator`.
- **Backfill Massive Economy data** with `uv run --directory mcp/daas-mcp python backfill_massive.py` — standalone script using a persistent `fastmcp.Client` (`StdioTransport`) against the `massive` `leader_upstreams` row to fetch the 4 Economy endpoints via `call_api`+`query_data` (the gateway's per-call spawn tears down store_as tables, so a persistent client is required), auto-create `scraw_massive_<slug>` tables, and `INSERT OR REPLACE` upsert on `date`. Routes around the broken pipeline-bridge (server-context `_cron_call` fails; `add_pipeline_item`/`sync_pipeline_cron` silently fail) by being a standalone process. Auth via `MASSIVE_API_KEY` (root `.env`). Flags: `--only <slug>`, `--drop`, `--dry-run`. Re-runnable; idempotent on `date`.
- **Self-check (massive endpoints)**: `uv run --directory mcp/daas-mcp python selfcheck_massive_endpoints.py` — temp DB, no network, no LLM. Pre-creates the `massive` source + `default` form + 3 sections, runs the seeder, asserts ≥37 functions each with ≥1 column, 5 representative endpoints carry the verified column sets, 12 gated endpoints carry `parameters.gated=true`, ≥25 indicator rules with `datasource=massive` + `source_table LIKE scraw_massive_%`, second-run idempotency, and `--unseed` cleanup that preserves the massive source/form/sections.
- **Sync entities + links** with `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --with akshare --directory mcp/daas-mcp python entity_sync.py --sync-all` — upserts stock entities from akshare (A-shares/HK/US) + a curated country list into `entities`, and auto-derives `entity_datasource_links` by market/country rules (US→edgar+yfinance; A-share→cnreport+yfinance; HK→hkex+yfinance; country→worldbank, +cnstats for CN). Per-market failure isolation; stale codes marked `status='delisted'`. Idempotent upsert on `(entity_type, code)`. Flags: `--sync-stocks`, `--sync-countries`, `--dry-run`, `--register-cron` (installs a weekly cron-mcp `Task` `entity-sync-stocks` + `Schedule` `entity-sync-weekly`, idempotent on names; takes effect on next cron-mcp start). akshare is imported lazily so the daas-mcp server starts without it; `--sync-stocks`/`--sync-all` print a clear error if akshare is absent.
- **Entity collections** (named groups of entities — watchlists/portfolios; distinct from `datasource_collections`). 3 tables: `entity_collections` (id, name UNIQUE, description, `rule_json` nullable, `rule_script` nullable), `entity_collection_items` (current membership; FK CASCADE to `entity_collections` + `entities`; UNIQUE(collection_id, entity_id)), `entity_collection_changes` (append-only **add-in / remove-out audit log**: `action` ∈ {add_in, remove_out}, `source` ∈ {manual, cron}, `reason`, `changed_at`). Created via `Base.metadata.create_all`; the `rule_script` column is added to a pre-existing `entity_collections` table by a guarded `ALTER TABLE` (`_migrate_entity_collections_rule_script` in `daas_database.py`, mirroring `_migrate_sources_score`). `rule_json` is an optional declarative membership rule (`entity_type`, `exchange`, `country_code`, `codes` list, `name_regex`) — a Python-side SQLite `REGEXP` function is registered on the daas engine in `daas_database.py`'s connect listener for `name_regex`. `rule_script` is the **script analogue**: a repo-root-relative path to a Python file defining `members(ctx) -> list` (mutually exclusive with `rule_json`); `sync_entity_collection` execs the script, which gets a read-only `ctx.query(sql, params=()) -> list[dict]` over daas.db so a rule can express cross-table logic the declarative JSON cannot (stocks in today's `scraw_*` table, union of two other collections, observation-threshold filters). Runner: `entity_rule_script.py` (`RuleScriptContext` opens `mode=ro`; `run_rule_script` resolves repo-root-relative paths so the stored path works under `uv run --directory` and in-process). Returned items may be a code `str`, `{"entity_type","code"}`, `{"entity_id":int}`, or an `int`; unknown codes are skipped (a sync never fails the whole collection over one delisted code).
  - **Tools (11)**: `create_entity_collection` (accepts `rule` JSON string OR `rule_script` path — mutually exclusive), `list_entity_collections`, `get_entity_collection`, `update_entity_collection` (`rule_script`/`clear_rule` switches; setting one clears the other), `delete_entity_collection`, `add_entity_to_collection`, `remove_entity_from_collection`, `list_entity_collection_items`, `reorder_entity_collection_items`, `list_entity_collection_changes`, `sync_entity_collection`. Adding/removing records an `add_in`/`remove_out` event (no-op + `action='already_member'`/`'not_member'` if the membership is already in the target state, with no event recorded). `sync_entity_collection(name)` re-derives rule-based membership from `rule_json` (filter) OR `rule_script` (script exec), applies add_in/remove_out diffs with `source='cron'`, returns `{rule: "json"|"script", added, removed, unchanged}`; idempotent; a manual collection (both rules NULL) is a no-op returning `action='manual_collection'`. **The rule is authoritative** — a sync remove_out's members not in the intended set, including manual adds; mix rule + manual via separate collections or by editing the rule.
  - **Cron CLI branch**: `python server.py --sync-entity-collection <name>` runs the sync in-process (works for both `rule_json` and `rule_script`), prints a JSON summary, exits (mirrors `--run-rule`). cron-mcp task command: `uv run --directory mcp/daas-mcp python server.py --sync-entity-collection <name>`.
  - **`entity_collection_sync.py`**: `--sync <name>` (ad-hoc, with `--dry-run` — reports `rule_kind` json/script + `rule`/`rule_script` + `intended_members`), `--register-cron <name>` (idempotently inserts cron-mcp `Task` `entity-collection-sync-<name>` + `Schedule` `entity-collection-sync-<name>-daily`, daily off-minute cron, tz from env; takes effect on next cron-mcp start — mirrors `entity_sync.py --register-cron`), `--unregister-cron <name>`.
  - **Dashboard `/entities`**: list + `/entities/new` + `/entities/[name]` (member table with add/remove, "Sync now" for rule-based collections, "Delete", and a History panel filtering add-in/remove-out). Writes via `/api/entities/*` → `collection_writer.py` entity-collection subcommands (`create-entity-collection`/`update-entity-collection` accept `rule_script`; `delete-entity-collection`, `add-entity-item`, `remove-entity-item`, `reorder-entity-items`, `sync-entity-collection`); reads via sql.js (`dashboard/src/lib/entity-collections.ts`). Nav entry "Entities".
  - **Key files**: `entity_collection_tools.py` (11 tool wrappers), `entity_rule_script.py` (`RuleScriptContext` + `run_rule_script`), `entity_collection_sync.py` (`--sync`/`--register-cron`/`--unregister-cron`), `selfcheck_entity_collections.py`, `selfcheck_entity_collection_script.py`, plus `EntityCollectionService` in `registry_service.py` (CRUD + membership + audit + rule-json/script sync; `_script_entity_ids` + `_normalize_member_items`) and the entity-collection subcommands in `collection_writer.py`. **Self-checks**: `uv run --directory mcp/daas-mcp python selfcheck_entity_collections.py` (temp DB; no network; no LLM; covers cascade + CRUD + add-in/remove-out recording + reorder + history filters + rule-json sync + idempotency + manual no-op + CLI branch + cron registration) and `uv run --directory mcp/daas-mcp python selfcheck_entity_collection_script.py` (temp DB + temp rule script; no network; no LLM; covers `rule_script` create/sync/diff, return-value normalization, `ctx.query` cross-table read, read-only enforcement, mutual-exclusivity + missing-script errors, manual no-op, CLI branch, `--dry-run`).
- **Pipeline collections** (managed fetch+cron collections, distinct from the curation `datasource_collections`): 2 tables (`pipeline_collections`, `pipeline_collection_items`) where each item binds a source MCP (`source_mcp` + `tool` + `arguments_json`, e.g. `akshare-mcp` + `call_akshare_function` + `{"name":"stock_zh_a_hist","params_json":"…"}`) to a `scraw_<slug>` storage table + upsert keys + cron cadence. This is the `data_job` shape from `add-cron-mcp-data-fetch`, so items migrate 1:1 later. Adding an enabled item triggers an immediate history backfill (spawn `source_mcp` via `fastmcp.Client`, call `tool`, upsert into `scraw_<slug>`) **and** an idempotent `cron-mcp` `create_task` + `create_schedule`; removing/disabling unwires the schedule. `scraw_<slug>` tables are auto-created on first fetch (queryable via `dashboard-mcp.query_table`; usable as daas-mcp process-rule source tables).
  - **Models**: `from models import PipelineCollection, PipelineCollectionItem` (in `mcp/models/`; auto-created via `Base.metadata.create_all`, no Alembic).
  - **Tools** (11): `create_pipeline_collection`, `list_pipeline_collections`, `get_pipeline_collection`, `delete_pipeline_collection`, `list_pipeline_items`, `add_pipeline_item`, `remove_pipeline_item`, `enable_pipeline_item`, `disable_pipeline_item`, `update_pipeline_item`, `sync_pipeline_cron`.
  - **CLI branches** (cron-mcp shell tasks): `python server.py --fetch-item <id>` (re-fetch + upsert), `--register-cron <id>`, `--unregister-cron <id>`, `--sync-cron`. The cron task command is `uv run --directory <repo>/mcp/daas-mcp python server.py --fetch-item <id>`.
  - **Launch-config resolver**: `source_mcp` resolves via `.mcp.json` `mcpServers` OR a `mcp/<source_mcp>/server.py` convention dir; `mcp/models` is injected into `PYTHONPATH` so spawned servers can `import models`. daas-mcp's own `fetch_data` is intentionally NOT used (its `daas-agent-harness` path is mis-resolved and the daas registry has no akshare functions) — the bridge calls the source MCPs directly.
  - **Key files**: `pipeline_tools.py`, `selfcheck_pipeline.py` (`uv run --directory mcp/daas-mcp python selfcheck_pipeline.py`; `AKSHARE_LIVE=1` for a live akshare backfill smoke), `seed_pipeline_from_mapping.py`.
  - **Seed the akshare example**: `uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py` loads the `openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md` needs (沪深日行情, 成交概况, AH比价, 大宗交易, 港股日行情, 研报, 盈利预测, 主营构成, …) into a `pipeline_collection` named `akshare-t-md` (17 items, each driving `akshare-mcp.call_akshare_function` on an off-minute `Asia/Shanghai` cron). Flags: `--dry-run`, `--only <name>`, `--unseed`, `--collection <name>`. Idempotent on collection + item name (re-run updates, no duplicate cron rows). Schedules fire on the next `cron-mcp` start (cron-mcp `load_schedules()` loads enabled rows into APScheduler).
- **Process tools** (LLM extraction + math indicators — relocated from the former `process-mcp`, now hosted by daas-mcp). Env-configurable LLM extraction (long text + images) with persisted rules drivable by `cron-mcp`. Generalizes `cnreport-mcp.ai_extract`: chunked map-reduce so long text is **not** truncated, optional vision via a `vision`-flagged model, multi-model registry via one `PROCESS_MODELS` JSON env. Reads scraped source data from `scraw_<slug>` tables and writes extracted records to a shared `process_results` table. Also computes **deterministic math indicators** (pandas one-liners: `sma`, `ema`, `rsi`, `pct_change`, `log_return`, `diff`, `rolling_std`, `rolling_min`, `rolling_max`, `zscore`, `ratio`, `level`) over a datasource's columns and upserts the resulting series into the daas `observations` table. The LLM path writes only `process_results`; only the indicator path writes `observations`.
  - **Tools (20 = 11 LLM + 9 indicator)**:
    - LLM (11): `list_models`, `list_source_tables`, `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`.
    - Indicator (9): `list_indicator_ops`, `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `set_indicator_score`, `delete_indicator`, `run_indicator`, `calculate`. Ad-hoc `calculate` computes without persisting; rule tools persist a binding for replay. `create_indicator`/`update_indicator` accept an optional `score` (default priority/quality weight); `update_indicator(clear_score=True)` clears it. `list_indicators`/`get_indicator` return `score` (raw) + `effective_default_score` = `COALESCE(indicator_rules.score, sources.score)` (NULL = inherit the datasource default).
  - **Cron CLI branches**: `python server.py --run-rule <name>` (LLM) or `--run-indicator <name>` (indicator) runs the path in-process, prints a JSON summary, exits — no stdio server. Wire a cron job via `cron-mcp`: `create_task(name="proc_<rule>", command="uv run --directory /Users/chengsishi/code/cli-anything/mcp/daas-mcp python server.py --run-rule <name>")` (or `--run-indicator`) + `create_schedule(name=..., cron_expr=..., task="proc_<rule>")`.
  - **Env**: `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (shared single-model fallback) and optional `PROCESS_MODELS` JSON (name retained from the former process-mcp). Each entry maps a name to `{model, vision?, base_url?, api_key?}` — per-model values override the shared `LLM_*`. Example: `PROCESS_MODELS={"fast":{"model":"gpt-4o-mini"},"eyes":{"model":"gpt-4o","vision":true}}`. Extraction tools return a clear `{"error":...}` (no network call) when the chosen model is unconfigured or a vision tool targets a non-vision model. Indicator tools need no LLM key.
  - **Database**: shared `mcp/daas.db` via `DAAS_DATABASE_URL`. Three tables (names retained as legacy labels) — `process_rules` and `process_results` for the LLM path; `indicator_rules` (name, datasource, function_name, source_table, date_column, value_column, op, params_json, indicator_name, enabled; soft ref to `sources.name`, no FK) for the indicator path. `run_rule` reads `rowid > last_rowid`, batch-capped at 500 per tick; `run_indicator` does a full recompute (no cursor — windowed ops need lookback) and upserts into `observations` on `(source=datasource, function_name, indicator=indicator_name, date)`, `value` stored as `str()`, `metadata` carrying `{rule_name, op, params, value_column}`. SQLite `PRAGMA foreign_keys=ON` is set per-connection so `delete_rule` cascades to `process_results`. Relative `sqlite:///` URLs are resolved against the repo root so the `--run-rule` / `--run-indicator` cron path works under `uv run --directory`.
  - **Source-data naming rule (`scraw_<slug>`)**: scraped data tables follow this convention; `list_source_tables` introspects `sqlite_master` for `scraw_*` (excluding `scraw_configs`) and returns each with row count + columns. `create_rule` / `create_indicator` validate the source table + columns exist in `sqlite_master` / `PRAGMA table_info` and validate identifiers against `^[A-Za-z_][A-Za-z0-9_]*$` before any SQL — guard against injection on the dynamic table/column names (they cannot be bind parameters). Indicator rules accept any table in `daas.db`, not just `scraw_*`.
  - **Key files** (all under `mcp/daas-mcp/`): `process_api.py` (the 19 tool wrappers + `--run-rule`/`--run-indicator` CLI helpers + `_run_rule_impl`), `process_tools.py` (LLM call + ad-hoc extract tools), `indicator_tools.py` (math-op catalog + ad-hoc `calculate`), `process_database.py` (`ProcessDatabase` singleton: rule/indicator CRUD, source discovery, identifier guard, `observations` upsert, `run_indicator`), `selfcheck_process.py` (temp DB; no LLM call required; exercises the indicator round-trip too), `migrate_process_cron.py` (one-shot rewrite of cron-mcp `tasks.command` rows from `mcp/process-mcp` → `mcp/daas-mcp`; `--dry-run` / `--revert`).
  - **Self-check**: `uv run --directory mcp/daas-mcp python selfcheck_process.py` (uses a temp DB; no LLM call required; exercises the indicator round-trip too).
  - **No separate `.mcp.json` entry** — the process tools ride on the `daas-mcp` server entry.

- **Indicator scores + indicator collections** (mirrors `datasource-scores` + `datasource-collections`/`entity-collections` for indicators). Adds a 3-level effective-score inheritance chain: **datasource score (`sources.score`) → indicator score (`indicator_rules.score`, NULL = inherit) → indicator-collection-item score (`indicator_collection_items.score`, NULL = inherit/override)**. Resolved effective score = `COALESCE(item.score, indicator_rules.score, sources.score)`.
  - **Tables** (in `mcp/models/models.py`, created via `Base.metadata.create_all`, additive — no Alembic): `indicator_rules.score` (Float nullable; added by guarded `ALTER TABLE` `_migrate_indicator_rules_score` in `process_database.py`, mirroring `_migrate_sources_score`); `indicator_collections` (id, unique `name`, `description`, timestamps); `indicator_collection_items` (collection_id FK→`indicator_collections.id` ON DELETE CASCADE, indicator_id FK→`indicator_rules.id` ON DELETE CASCADE, `sort_order`, `score` Float nullable override, UNIQUE `(collection_id, indicator_id)`); `indicator_collection_changes` (append-only add_in/remove_out audit log; `indicator_name` denormalized so the row survives indicator-rule deletion; FK→`indicator_collections.id` ON DELETE CASCADE).
  - **Tools (12)**: `set_indicator_score` (set/clear an indicator's default score; `score=null` clears → inherit datasource default). Plus 11 indicator-collection tools: `create_indicator_collection`, `list_indicator_collections`, `get_indicator_collection`, `update_indicator_collection`, `delete_indicator_collection`, `add_indicator_to_collection` (optional `score`), `remove_indicator_from_collection`, `list_indicator_collection_items` (3-level resolved `score` + raw `item_score`/`indicator_default_score`/`source_default_score` per item), `reorder_indicator_collection_items` (full item-id list), `set_indicator_collection_item_score` (set/clear per-item override; `score=null` clears), `list_indicator_collection_changes` (audit log, newest-first, enriched with collection name). Membership add/remove records add_in/remove_out (no-op `already_member`/`not_member` when already in the target state). Rule-based sync is deferred (manual membership only, mirroring the initial entity-collections cut).
  - **Key files**: `indicator_collection_tools.py` (11 tool wrappers), `IndicatorCollectionService` in `registry_service.py` (CRUD + membership + 3-level resolution + audit; mirrors `EntityCollectionService`), `selfcheck_indicator_scores.py` (temp DB; no network; no LLM; covers score migration + 3-level resolution all 4 scenarios + per-item override set/clear + audit log + cascade on collection/rule delete).
  - **`collection_writer.py` subcommands**: `set-indicator-score` (`{name, score}`; routes to `ProcessDatabase.set_indicator_score`), `create-indicator-collection`, `update-indicator-collection`, `delete-indicator-collection`, `add-indicator-item` (`{collection_name, indicator_name, score?, reason?}`), `remove-indicator-item`, `reorder-indicator-items`, `set-indicator-collection-item-score` (`{collection_name, indicator_name, score}`; `score=null` clears).
  - **Dashboard**: inline-editable score column on `/process/indicators` (with read-only datasource-default hint + resolved effective score); new `/process/indicators/collections` (list) + `/process/indicators/collections/new` (create) + `/process/indicators/collections/[name]` (detail with add/remove/reorder + inline per-item score override + resolved effective score + add-in/remove-out history panel). Reads via sql.js (`dashboard/src/lib/indicator-scores.ts`); writes via `/api/indicators/*` routes → `collection_writer.py` subcommands. Nav entries "Indicators" + "Indicator Collections".
  - **Self-check**: `uv run --directory mcp/daas-mcp python selfcheck_indicator_scores.py` (temp DB; no network; no LLM; 57 assertions: score migration + create/update/clear + effective_default_score inheritance + set_indicator_score errors + collection CRUD/membership/reorder + 3-level resolution all 4 scenarios + per-item override + audit log survives deletion + cascade).

### mcp/dashboard-mcp/ — Dashboard MCP

Browse databases, query tables, manage datasources, get stats, **and manage the standalone-HTML dashboard registry**.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`, resolved against the repo root (relative `sqlite:///mcp/daas.db` → `<repo-root>/mcp/daas.db`; fallback is the canonical repo-root DB, never `mcp/dashboard-mcp/daas.db` — closes the stale-DB gotcha for `query_table` too).
- **Models**: `from models import Datasource, DatasourceColumn, Dashboard, ...` (no more inline CREATE TABLE)
- **Dashboard registry** (`dashboards` table, single source of truth for standalone-HTML dashboard metadata): 6 tools — `register_dashboard` (upsert by slug + regenerate `index.html`/`daas.md`), `list_dashboards`, `get_dashboard`, `search_dashboards` (keyword over name + intro + source_tables), `update_dashboard`, `delete_dashboard`. `index.html` + `daas.md` are regenerated from the DB on every write (idempotent, no hand-append). JSON fields (`source_tables` / `entity_coverage` / `time_range` / `chart_config`) accept a JSON string or list/dict. Backs the `fd-daas-dashboard-creator` (build) and `fd-daas-dashboard` (use) skills.
- **Key files**: `server.py`, `dashboard_database.py` (`DashboardDatabase` singleton: CRUD + `_regenerate_index_and_daas` + repo-root URL resolution), `backfill_dashboards.py` (one-time backfill of the legacy `us-leaders-trend-monitor` dashboard), `selfcheck_dashboards.py` (offline self-check: temp DB; register→get→search→update→list→delete + index/daas.md regen + URL resolution).
- **Self-check**: `uv run --directory mcp/dashboard-mcp python selfcheck_dashboards.py` (temp DB; no network).
- **Backfill**: `uv run --directory mcp/dashboard-mcp python backfill_dashboards.py` (`--dry-run` supported; idempotent upsert).

The Next.js dashboard at `dashboard/` also ships a **NotebookLM-style collections workspace** at `/collections` (and `/collections/[name]`). Three panes: catalog (left, draggable datasources/sections grouped by category) → collection (center, droppable + sortable) → chat (right, scoped to the active collection). Writes go through `dashboard/src/app/api/collections/*` which spawns `uv run --directory mcp/daas-mcp python collection_writer.py …`. Chat uses the same `streamText` + MCP-tools wiring as `/api/chat` but with a collection-aware system prompt; configure `CHAT_PROVIDER`, an API key (e.g. `ANTHROPIC_API_KEY`), and `MCP_SERVER=daas-mcp` in root `.env`.

The dashboard `/chat` page (`add-ai-chat`, adapted by `add-mcp-ui-chat`) renders **MCP-Apps UI resources** inline via `@mcp-ui/client`'s `AppRenderer`: when a tool result carries `_meta.ui.resourceUri` (a `ui://…` URI), `message-bubble` renders `<UiResourceBlock>` instead of `ToolCallCard`, mounting a sandboxed iframe (`public/mcp-ui-sandbox-proxy.html`) that loads the guest HTML and relays `AppBridge` `postMessage`s. The browser drives the server-side raw `@modelcontextprotocol/sdk` `Client` (singleton in `src/lib/mcp-ui-server.ts`) via same-origin `/api/mcp-ui/[op]` routes (`read-resource` / `call-tool` / `list-resources`). A `<select>` in the header picks the MCP server per session — **`composite-mcp` is the default** (curated multi-upstream surface; ships the `render_stock_summary` demo UI tool), `leader-mcp` preserves the ECharts flow. `composite-mcp` uses the raw client (so `_meta` survives and the same client backs `AppRenderer`); other servers use `@ai-sdk/mcp` unchanged. The global `mcp-client.ts` `defaultServer()` stays `leader-mcp` so the workflows + collections APIs are unaffected. New dashboard deps: `@mcp-ui/client`, `@modelcontextprotocol/ext-apps` (`@modelcontextprotocol/sdk` was already present). See `construction/dashboard.md` "MCP-UI chat" section.

The dashboard also has a **Scores page** at `/scores` for managing the daas-mcp score concept. Two sections: a **Default scores** table (every datasource's `sources.score`, inline-editable) and a **Collection scores** section (pick a `datasource_collection`, see its items with an inline-editable per-item override plus a read-only default column and the resolved effective score). Reads go through sql.js (`loadSourceScores` / `loadCollectionScores` in `dashboard/src/lib/scores.ts`); writes go through `dashboard/src/app/api/scores/*` → the `collection_writer.py set-source-score` / `set-item-score` subcommands (same sidecar as the collections workspace). `score=null` clears (inherit the default). Resolved score = item override if set, else datasource default, else NULL.

The dashboard also has an **Agents workspace** at `/agents` (list / `/agents/new` / `/agents/[name]` / `/agents/[name]/edit`) for full CRUD on leader-mcp's specialist agents (`specialist_agents` table). List/detail pages read directly from `mcp/daas.db` via sql.js (`getDb('daas')` + `queryAll`, no leader-mcp spawn); create/update/delete go through `dashboard/src/app/api/agents/*` which calls leader-mcp tools (`create_specialist_agent` / `update_specialist_agent` / `delete_specialist_agent`) via `getMCPTools()` and then `invalidateDb('daas')` — the same write path as `/api/workflows/[name]/runs`. Form dropdowns for `upstream` and `model` are populated from `list_data_mcps()` + `list_agent_models()` with a free-text fallback when leader-mcp is unavailable.

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

Purpose-built MCP for Chinese A-share filings: edgartools-style company API (CNINFO-backed lookup, filings list, structured financials via akshare) **plus** PDF section extraction, LLM structured extraction, Elasticsearch store/search, and an on-disk report cache. Sixteen tools total:

- **Company API** (8, CNINFO-backed): `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_financial_statements`, `get_section`, `list_report_types`, `get_special_report`. `get_company` accepts a 6-digit ticker or Chinese/English name. `list_filings` filters by `form` (`年度报告` / `半年度报告` / `第一季度报告` / `第三季度报告`) **or** `category` (any CNINFO category code or Chinese name from the catalog, e.g. `招股说明书` / `category_sf_szsh`); `form` and `category` are mutually exclusive. `get_financials` returns three statements (`income_statement` / `balance_sheet` / `cashflow`) as `{columns, data}` records — shape matches `edgartools-mcp.get_financials`. `get_financial_statements` pulls the 三大报表 (`合并利润表` / `合并资产负债表` / `合并现金流量表`, un-prefixed fallback) as **text** from the annual-report PDF via the TOC — complementing `get_financials`'s akshare numbers with the report's actual section text; statements not found are listed in `missing` + `available`. `get_section` is the bridge: `(ticker, year, section)` → resolved PDF URL → outline-extraction pipeline. `list_report_types` browses the CNINFO disclosure category catalog (grouped). `get_special_report` retrieves a special-type report by category (招股说明书 / 收购报告书 / 业绩预告 / …), with optional section extraction reusing the outline pipeline.
- **Outline extraction** (2): `list_outline`, `extract_section` — fetch a report URL/path (cache-aware), parse 目录, extract one section's body text by exact title / regex / 1-based ordinal.
- **AI processing** (1): `ai_extract` — LLM structured extraction against a JSON Schema.
- **Elasticsearch** (3): `index_records`, `search_reports`, `delete_index` — bulk index extracted records into `cnreport-{year}`, BM25 + filter search with highlights.
- **Report cache** (2): `list_cache`, `clear_cache`. Every fetch path (`list_outline`, `extract_section`, `get_section`, `get_special_report`, `get_financial_statements`) goes through an on-disk cache (`report_cache.py` → `CNREPORT_CACHE_DIR`, default `mcp/cnreport-mcp/.cache/reports/`): first fetch downloads the PDF + extracts text + outline and stores `{stock}_{year}_{form}_{announcement_id}.{pdf,txt,outline.json}` (URL-hash fallback for raw `extract_section`); subsequent fetches read from disk (no re-download, no re-`pypdf`-parse). `list_cache` lists entries; `clear_cache(stock_code?, year?)` evicts (all / by company / by company+year). No TTL — CNINFO reports are immutable. Cache dir is `.gitignore`d.
- **Category registry**: `cninfo_categories.json` (data-driven, sourced from CNINFO's own `history-notice.js` via akshare) is the source of truth for CNINFO category codes. `_FORM_CATEGORIES` is derived from it at import. Adding a report type = editing that JSON (no code change); see `load_categories()` / `resolve_category()` in `cninfo_client.py`.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `fastmcp`, `httpx`, `pypdf`, `jsonschema`, `elasticsearch`, `akshare>=1.13`, `pandas`, `mcp-models`
- **API key**: KEYLESS for CNINFO + akshare (the company API). `ai_extract` needs `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`; the ES tools need `ES_URL` (optional `ES_API_KEY` or `ES_USERNAME` / `ES_PASSWORD`). No `EDGAR_IDENTITY`-equivalent required.
- **Database**: writes provenance to `mcp/daas.db` via `mcp-models` (`Document` / `Section` / `EsIndex` rows); company-API tools are stateless and do NOT touch the DB.
- **Self-check**: `uv run python selfcheck.py` (temp DB; CNINFO + akshare mocked) and `uv run python selfcheck_cache.py` (temp cache dir; report cache + three-statements extraction; fetch stubbed)
- **Tests**: `uv run --with pytest python -m pytest test_cnreport.py -v -p no:logfire` (offline)
- **Registered in `.mcp.json`** via `uv run --directory mcp/cnreport-mcp python server.py`

### mcp/composite-mcp/ — Composite MCP

Curate a composite MCP: pick named tools from multiple upstream MCP servers (proxied verbatim) and define chained tools (linear pipelines across upstreams). One composite served per process, selected by `COMPOSITE` env. Selection persisted in `daas.db`; management tools (`list_composites`, `add_upstream`, `list_available_tools`, `add_tool`, `add_chained_tool`, ...) always present. Served tool names are `<upstream>_<tool>` (mount namespace). Selection changes apply on restart.

- **Entry**: `python3 server.py` (FastMCP, stdio). `.mcp.json` entry sets `COMPOSITE=example`.
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Composite, Upstream, CompositeTool, CompositeChain`
- **Key files**: `server.py`, `composite_database.py`, `composite_tools.py`, `seed_example.py`, `selfcheck.py`, `ui_tools.py` (demo MCP-Apps UI tool), `selfcheck_ui_tool.py`
- **Demo MCP-Apps UI tool** (`add-mcp-ui-chat`): `ui_tools.register(app)` adds an always-present `render_stock_summary(symbol)` tool + a FastMCP resource template at `ui://composite-mcp/stock-summary/{symbol}` (`mimeType: text/html;profile=mcp-app`). The tool returns `_meta.ui.resourceUri` via `ToolResult.meta`; the resource returns the HTML via `ResourceResult([ResourceContent(html, mime_type=...)])` (plain `str` returns drop to `text/plain` — the `ResourceResult` is required). Pure FastMCP, no extra Python dep. The dashboard `/chat` renders this via `@mcp-ui/client`'s `AppRenderer`.
- **Self-check**: `uv run python selfcheck.py` (uses a temp DB; does not touch `daas.db`). `uv run --directory mcp/composite-mcp python selfcheck_ui_tool.py` (hermetic; in-process `Client`; asserts the tool `_meta.ui.resourceUri` + resource `mimeType`).
- **Seed shipped example**: `uv run python seed_example.py`
- Imports use direct relative imports — run from within `mcp/composite-mcp/`

### mcp/hkreport-mcp/ — Hong Kong Stock Exchange Report MCP

Purpose-built (not a registry/harness) live-execution MCP for HK-listed companies. Same shape as `edgartools-mcp` (five tools, four names identical) with `get_disclosure_calendar` replacing `get_insider_trades` (HK has no Form-4 equivalent agents query). Tools: `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_disclosure_calendar`. Hand-rolled HKEXnews HTTP client (no maintained Python library exists) plus `akshare`'s `stock_financial_hk_report_em` for normalized income/balance/cashflow.

- **Entry**: `python3 server.py` (FastMCP, stdio transport). Self-check: `uv run python selfcheck.py`.
- **Dependencies**: `fastmcp`, `httpx`, `pypdf`, `akshare>=1.13`, `pandas`, `python-dotenv` (no `sqlalchemy`/`click` — no registry, no CLI)
- **API key**: KEYLESS — HKEXnews + akshare HK endpoints are public. Optional `HTTPS_PROXY`/`HTTP_PROXY` honored.
- **Database**: none — does not touch `mcp/daas.db` (live-execution only, like `edgartools-mcp`)
- **Tests**: `uv run --with pytest python -m pytest test_hkreport.py -v -p no:logfire` (offline; HTTP mocked via `respx`, akshare patched). `HKREPORT_LIVE=1` enables two live smoke tests against ticker `00700`.
- **Registered in `.mcp.json`** via `uv run --directory mcp/hkreport-mcp python server.py`

### mcp/alerts-mcp/ — Trigger-Rule + Social Notification MCP

Watches series in `mcp/daas.db` (the `observations` table daas-mcp computes, plus any `scraw_*` table), evaluates user-defined trigger rules on a cron schedule, and dispatches notifications to social/chat channels. Read-only w.r.t. other MCPs' tables — writes only its own `alert_rules` / `alert_events`. No LLM call (no `LLM_*` keys); message bodies come from templates.

- **Tools (10)**: `list_series`, `get_series_latest` (alert-scoped inspection, NOT a SQL browser — `dashboard-mcp.query_table` owns that), `create_alert_rule`, `list_alert_rules`, `get_alert_rule`, `update_alert_rule`, `delete_alert_rule`, `list_channels`, `run_rule` (ad-hoc evaluate + dispatch one rule now), `list_events`.
- **Entry**: `python3 server.py` (FastMCP, stdio transport). CLI branches: `python3 server.py --run-rule <name>` (one rule) and `--run-all` (every enabled rule, single tick) — prints a JSON summary and exits, no stdio server start; for `cron-mcp` scheduling. The cron task command is `uv run --directory /Users/chengsishi/code/cli-anything/mcp/alerts-mcp python server.py --run-rule <name>`.
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`. Two tables: `alert_rules` (name UNIQUE, enabled, source_table default `observations`, series_filter_json, date_column, value_column, condition, fire_mode, cooldown_seconds, channels_json, message_template, last_state, last_fired_at, last_value) and `alert_events` (rule_id FK CASCADE, fired_at, value_json, message_rendered, channels_results_json). Created via `Base.metadata.create_all` (no Alembic). `PRAGMA foreign_keys=ON` per-connection so `delete_alert_rule` cascades to `alert_events`. Relative `sqlite:///` URLs resolved against repo root (mirrors the daas-mcp process tools) so `--run-rule` works under `uv run --directory`.
- **Models**: `from models import AlertRule, AlertEvent` (added to `mcp/models/`).
- **Series source**: a rule points at `source_table` + `series_filter_json` (key→value WHERE pairs, e.g. `{"source":"akshare","function_name":"stock_zh_a_hist","indicator":"close"}`) + `date_column` + `value_column`. Identifiers validated against `^[A-Za-z_][A-Za-z0-9_]*$` (same guard as the daas-mcp process tools); filter values are bind params.
- **Condition DSL**: `expressions.evaluate` compiles with `ast.parse(mode="eval")` and walks a strict whitelist (`BoolOp`/`UnaryOp`/`Compare`/`BinOp`/`Name`/`Constant`/`Call`) — no `eval`/`exec`, no `Attribute`/`Subscript`/comprehensions. Names: `latest`, `prev`. Whitelisted funcs: `crosses_above(t)`, `crosses_below(t)`, `pct_change(n)`, `value(n)`, `avg(n)`, `min(n)`, `max(n)` over `ctx["series"]` (newest-first).
- **Fire modes**: `every_match` (fires every true eval subject to `cooldown_seconds` vs `last_fired_at`) or `on_change` (fires only on false→true transition, using `last_state`). False eval sets `last_state=False`, inserts no event. State persists across cron ticks.
- **Notifiers**: pluggable `Notifier` ABC + registry (`notifiers/`) with 7 adapters — `telegram` (Bot API), `discord` + `slack` (webhooks), `dingtalk` (钉钉, optional HMAC-SHA256 sign), `feishu` (飞书, optional HMAC-SHA256 sign in `X-Lark-Signature`), `wecowork` (企业微信, key-in-URL), `twitter` (OAuth 1.0a HMAC-SHA1 hand-rolled over stdlib, no new dep). Dispatch fans out to every channel in `channels_json` with try/except per channel — one failure is recorded in `channels_results_json`, not raised. `channels_json` is a list of names OR a `{name: override}` object (e.g. `{"telegram": {"chat_id": "…"}}` overrides the env default).
- **Env**: all channel credentials in root `.env` under `ALERTS_*` prefixes (`ALERTS_TELEGRAM_BOT_TOKEN` / `ALERTS_TELEGRAM_CHAT_ID`, `ALERTS_DISCORD_WEBHOOK_URL`, `ALERTS_SLACK_WEBHOOK_URL`, `ALERTS_DINGTALK_WEBHOOK_URL` / `_SECRET`, `ALERTS_FEISHU_WEBHOOK_URL` / `_SECRET`, `ALERTS_WECOM_WEBHOOK_URL` / `_SECRET`, `ALERTS_TWITTER_CONSUMER_KEY`/`_SECRET` + `ALERTS_TWITTER_ACCESS_TOKEN`/`_SECRET`). No channel is required — unconfigured channels report `configured: false` and are skipped. `list_channels` returns `{name, configured, missing_keys}` and NEVER returns credential values.
- **Message rendering**: `string.Template(template).safe_substitute(...)` (not `str.format` — `string.Template` cannot access attributes). Vars: `$latest $prev $date $rule_name $source $indicator $value $pct_change`.
- **Key files**: `server.py`, `alert_tools.py` (tool functions), `alert_database.py` (singleton, CRUD, identifier guard, `record_firing`), `expressions.py` (DSL), `messaging.py` (template render), `engine.py` (load series + eval + fire-mode + dispatch), `notifiers/` (`base.py`, `registry.py`, 7 adapters), `selfcheck.py`.
- **Self-check**: `uv run --directory mcp/alerts-mcp python selfcheck.py` (temp DB; stubs the dispatch path so no network and no real posts; verifies DSL incl. malicious-expression rejection, the on_change false→true→false→true cycle, cooldown gating, fault-isolated dispatch, event insertion + cascade, `list_channels` secret-redaction, and Twitter OAuth signing vs an oauthlib-verified vector; passes with no `ALERTS_*` env set).
- **Registered in `.mcp.json`** via `uv run --directory mcp/alerts-mcp python server.py`

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
