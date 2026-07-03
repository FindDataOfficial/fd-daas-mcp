## Context

The user wants a *managed* "datasource collection": create a named collection, add datasources to it, and have the system **automatically** (i) fetch history data and (ii) register a `cron-mcp` schedule that keeps fetching on a cadence — all managed through `daas-mcp` (or `leader-mcp`) tools, reproducible across many collections, and testable with the akshare `datasource-mapping.md` catalog.

Current state:

- **`daas-mcp`** owns datasource management (CRUD, categories, forms/sections, entity coverage) and a `fetch_data(function_name, params_json)` executor — though `fetch_data` is currently non-functional for routing (its `daas-agent-harness` path is mis-resolved to `mcp/daas-agent-harness` while the real harness is at repo root, and `daas_functions` has no akshare entries). The actual working data gateways are the per-domain MCPs: `akshare-mcp.call_akshare_function`, `yfinance-mcp.call_yfinance_function`, `worldbank-mcp.call_worldbank_function`, `ckan-mcp.call_ckan_function`, `cnstats-mcp.call_cnstats_function`, plus the purpose-built MCPs (`edgartools-mcp`, `edinet-mcp`, `dartlab-mcp`, `cnreport-mcp`, `hkreport-mcp`). daas-mcp also owns a curation-only `datasource_collections` / `datasource_collection_items` pair (groups datasources/sections for the NotebookLM-style workspace — **no** fetch/storage/cron semantics).
- **`cron-mcp`** today schedules **shell-command** tasks: `create_task(name, command)` + `create_schedule(name, cron, task, timezone)`. The richer `data_job` / `cron_fetch_results` / `create_schedule(data_job=...)` abstraction from `add-cron-mcp-data-fetch` is specced but **not implemented** (`schedules.task_name` is still `NOT NULL`, no `data_job_id` column).
- **`akshare-cron-data-pipeline`** (also specced, not implemented) ships standalone helper scripts — `datasets.py` catalog, `fetch_to_store.py` bridge (spawns `akshare-mcp` via `fastmcp.Client`), `register_cron.py` wiring — that are akshare-specific and not managed by any MCP.
- **`mcp/daas.db`** is the shared database. Project convention for raw fetched data is `scraw_<slug>` tables, introspected by `process-mcp.list_source_tables` and queryable by `dashboard-mcp.query_table`.
- **`process-mcp`** sets the precedent for a `python server.py --run-rule <name>` CLI branch that runs a path in-process and exits — the pattern reused here for `--fetch-item`.

Constraints: use the **current** MCPs as-is (`cron-mcp` and `akshare-mcp` consumed, not modified); `uv` + Python 3.10+; no new runtime dependencies (`fastmcp` + `pandas` already present); schema changes go in `mcp/models/` first; `mcp/daas.db` is the single database.

## Goals / Non-Goals

**Goals:**
- A managed, **source-agnostic** "pipeline collection" in `daas-mcp`: a named collection of fetch items, each binding a daas source + function + params to a `scraw_<slug>` storage target and a cron cadence.
- **Automatic** history backfill + `cron-mcp` schedule registration when an enabled item is added; automatic **unwiring** on remove/disable.
- Management tools to create/list/get/delete collections and add/remove/list/update/enable/disable items, plus a bulk `sync_pipeline_cron`.
- A `--fetch-item` CLI branch so `cron-mcp` shell tasks invoke the same in-process fetch-to-store path.
- Test the whole path end-to-end by seeding the akshare `datasource-mapping.md` examples into a collection.

**Non-Goals:**
- Implementing the `add-cron-mcp-data-fetch` `data_job` / `cron_fetch_results` abstraction — separate, already-specced change. This change is compatible with it but does not build it.
- Replacing the curation `datasource-collections` capability — the new tables are distinct and additive.
- Building dashboard UI — the dashboard already reads `scraw_*` via `dashboard-mcp.query_table`; collection management is via daas-mcp tools.
- LLM extraction / indicator computation on fetched data — `process-mcp` already does this and consumes `scraw_*` as rule source tables.
- Real-time streaming or intraday polling — cron cadence only.
- A collection-level "fetch all" cron — item-level cron only (per-item cadence, per-item pause/inspect).

## Decisions

### Decision 1 — Home is `daas-mcp`, not `leader-mcp`

`daas-mcp` gains the new tables, tools, and fetch-to-store bridge. `leader-mcp` stays a metadata/router layer (and the unimplemented `leader-mcp-data-gateway` change positions it as a live-data gateway, not a management home).

- **Why**: `daas-mcp` already owns datasource management, the `sources`/`daas_functions` registry, and the existing curation collections — the new capability is a natural extension of "manage datasources". Its new tables sit beside the existing datasource tables, and it already depends on `fastmcp` (needed to reach the source MCPs and `cron-mcp` as clients).
- **Alternatives**: `leader-mcp` — rejected: it has no datasource-management surface today and would duplicate `daas-mcp`'s registry access. The user said "leader-mcp **or** daas-mcp"; daas-mcp is the coherent home.

### Decision 2 — New tables, distinct from the curation `datasource_collections`

Two new tables: `pipeline_collections` (id, name UNIQUE, description, created_at) and `pipeline_collection_items` (id, collection_id FK CASCADE, name, source_mcp, tool, arguments_json, storage_table, upsert_keys_json, cron_expr, timezone, enabled, task_name, last_run_at, last_status, last_row_count, error_message, created_at). The item's `task_name` is the cron-mcp task name (`pipeline_<collection>_<item>`), stored so remove/disable can delete the right rows.

- **Why**: the user explicitly asked for a **new table**; the existing `datasource_collections` carries no fetch/storage/cron fields and overloading it (e.g. a `kind` column) would muddy the curation capability's spec.
- **Alternatives**: a `kind` discriminator on `datasource_collections` — rejected (user said new table; keeps the two capabilities' specs clean).
- **Item = source MCP + tool + arguments + storage + cron**: a datasource alone (without params) cannot be fetched, so the item carries `source_mcp` (e.g. `akshare-mcp`) + `tool` (e.g. `call_akshare_function`) + `arguments_json` (the tool's kwargs, e.g. `{"name":"stock_zh_a_hist","params_json":"{\"symbol\":\"000001\"}"}`) + `storage_table` + `upsert_keys_json` + `cron_expr`. This is the `data_job` shape from `add-cron-mcp-data-fetch`, so items migrate 1:1 later. `source_mcp` is validated against `.mcp.json`'s `mcpServers` on add; `tool` is validated lazily on first fetch (a live tool-list check at add time would spawn the MCP — slow).

### Decision 3 — Fetch-to-store bridge spawns the source MCP via `fastmcp.Client`

The bridge reads the item's `source_mcp` launch config from `.mcp.json` (`mcpServers[<source_mcp>]` → command/args/cwd/env), spawns it as a stdio subprocess via `fastmcp.Client`, calls the item's `tool` with `arguments_json` (spread as kwargs), and extracts the returned records (the registry-style MCPs return `{"type":"dataframe","columns":[...],"data":[{...},...]}` via their `_serialize_result`; the bridge reads `data` + `columns`). It converts `data` to a `DataFrame` and upserts into the item's `scraw_<slug>` table (`CREATE TABLE IF NOT EXISTS` with inferred columns; `CREATE UNIQUE INDEX IF NOT EXISTS` on `upsert_keys`; `ALTER TABLE ADD COLUMN` for new columns on later fetches; `INSERT ... ON CONFLICT(keys) DO UPDATE`).

- **Why**: `daas-mcp`'s own `fetch_data` executor is non-functional today — its `daas-agent-harness` path is mis-resolved (`mcp/daas-agent-harness` vs the real repo-root `daas-agent-harness/`) and the daas registry (`daas_functions`) has no akshare functions seeded. The per-domain MCPs (`akshare-mcp.call_akshare_function`, `yfinance-mcp.call_yfinance_function`, `worldbank-mcp.call_worldbank_function`, …) are the actual working data gateways. Spawning them via `fastmcp.Client` is the proven pattern (`combine-mcp`, the specced `add-cron-mcp-data-fetch`, the `akshare-cron-data-pipeline` change) and generalizes to any MCP — including the purpose-built ones (`edgartools-mcp`, etc.) whose tool surfaces are not `call_*_function`.
- **Alternatives**:
  - (a) Fix `fetch_data`'s path + seed akshare into the daas registry, then call `fetch_data` in-process — rejected: larger scope (fixing the router, seeding the registry), and still doesn't cover purpose-built MCPs. Out of scope for this change.
  - (b) Wait for `cron-mcp`'s `data_job` path — rejected: not implemented; the user wants data now.
- **Trade-off**: one subprocess spawn per fetch (the source MCP) plus a JSON-RPC handshake. Acceptable at daily/weekly/quarterly cron cadence; the bridge reuses one client per fetch and closes it.

### Decision 4 — Cron wiring via `fastmcp.Client` to `cron-mcp`, idempotent

`daas-mcp` resolves the `cron-mcp` launch command from `.mcp.json` (override via `CRON_MCP_COMMAND`), connects via `fastmcp.Client`, and for each enabled item calls `create_task` (or `update_task` on name conflict) then `create_schedule` (delete+recreate only if `cron`/`timezone` changed, preserving `enabled`). The task `command` is `uv run --directory <abs_repo>/mcp/daas-mcp python server.py --fetch-item <item_id>` (absolute path so `cron-mcp` runs from any CWD). `task_name = pipeline_<collection_name>_<item_name>` is stored on the item row.

- **Why**: proven pattern (`combine-mcp`, the specced `add-cron-mcp-data-fetch`); `cron-mcp` owns APScheduler registration + validation, so calls go through its tools, not direct DB writes. Idempotency gives reproducibility across many collections while each job remains a plain, inspectable `cron-mcp` row.
- **Alternatives**: direct DB inserts into `tasks`/`schedules` — rejected: bypasses `cron-mcp` validation and APScheduler registration.

### Decision 5 — `add_pipeline_item` is synchronous: backfill then register cron

When an enabled item is added, `add_pipeline_item` (i) runs the history backfill via the in-process bridge, (ii) registers the cron-mcp task + schedule, and (iii) records `last_run_at` / `last_status` / `last_row_count` / `error_message` on the item. Both steps are best-effort with independent status: a backfill failure still registers cron (so the schedule retries); a cron-registration failure still leaves the backfilled data and marks `last_status="cron_failed"`. The tool returns a JSON summary `{item, backfill: {status, rows}, cron: {status, task, schedule}}`.

- **Why**: the user wants "add a datasource → automatically fetch history + create cron" as one operation. Synchronous gives immediate feedback and a populated table the user can query. Independent status fields mean a partial failure is recoverable via `sync_pipeline_cron` / re-running `--fetch-item`.
- **Alternatives**: async (return immediately, fetch in background) — rejected for now: adds a background runner `daas-mcp` doesn't have, and the user wants the history data on add. Revisit if large history fetches block the tool call unacceptably (Open Questions).
- **Disabled items**: `add_pipeline_item(enabled=False)` (or `enable_pipeline_item=False`) skips both backfill and cron — stores the item only. `enable_pipeline_item` later triggers backfill + cron.

### Decision 6 — Remove / disable unwires cron

`remove_pipeline_item` deletes the cron-mcp task + schedule (via `delete_schedule` + `delete_task`) before deleting the item row; the `scraw_<slug>` table is left intact (inert, queryable). `disable_pipeline_item` deletes only the schedule (keeps the task row so re-enable is cheap) and sets `enabled=0`. `delete_pipeline_collection` cascades: unwires cron for every item, then deletes the collection (FK CASCADE removes items).

- **Why**: keeps `cron-mcp` rows in sync with managed items — no orphan schedules. Leaves fetched data in place so accidental removal isn't destructive.
- **Alternatives**: leave cron rows on remove — rejected: orphans would keep fetching into a table no managed item points at.

### Decision 7 — `sync_pipeline_cron` for bulk re-wiring

A `sync_pipeline_cron` tool (and `python server.py --sync-cron` CLI branch) re-applies cron-mcp wiring for all enabled items idempotently (create-or-update task + schedule), and unwires schedules for disabled items. Used after `cron-mcp`/`daas-mcp` restarts, config changes, or to recover from a `cron_failed` status.

- **Why**: `cron-mcp` schedules live in its own DB/process; a restart or a missed `add` must be recoverable in one operation.
- **Alternatives**: per-item retry only — rejected: with many collections, bulk sync is the practical recovery path.

### Decision 8 — Seed/test from `datasource-mapping.md`

`seed_pipeline_from_mapping.py` creates a `pipeline_collection` (e.g. `akshare-t-md`) and adds one item per mapped `t.md` need from `openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md` (沪深日行情 → `stock_zh_a_hist`, 成交概况 → `stock_sse_summary`/`stock_szse_summary`, AH比价 → `stock_zh_ah_spot_em`, 大宗交易 → `stock_dzjy_mrmx`, 港股日行情 → `stock_hk_hist`, 研报 → `stock_research_report_em`, 盈利预测 → `stock_profit_forecast_em`, 主营构成 → `stock_zygc_em`, …) with per-item `scraw_<slug>`, upsert keys, and cadence from the akshare change's design table. `--dry-run` plans; `--only <name>` seeds one; `--unseed` removes the collection (cascading cron unwiring). Idempotent on collection name + item name.

- **Why**: the user explicitly asked to test with the akshare mapping; it is a ready-made, real catalog covering ~17 datasets across multiple akshare portals — a meaningful end-to-end exercise of the capability.
- **Cadence** (carried from the akshare change, `timezone="Asia/Shanghai"`, off-minute staggered): daily weekdays ~16:30–17:30 for A-share close datasets; `0 18 * * 1-5` for HK; ~18:30 for research/forecast; weekly Friday for low-churn; monthly/quarterly for event-driven.

## Risks / Trade-offs

- **[akshare rate-limiting / IP blocking under many concurrent crons]** → off-minute staggered cron times (no two items at the same `:00`/`:30`); one fetch per item per cadence; rely on the source MCPs' existing call path.
- **[One source-MCP subprocess spawn per fetch adds latency]** → acceptable at cron cadence; the bridge opens one `fastmcp.Client` per fetch and closes it. Revisit only if latency matters.
- **[`scraw_<slug>` schema drift if a source changes columns]** → bridge derives columns from the first DataFrame; new columns on later fetches appended via guarded `ALTER TABLE`; dropped columns left NULL.
- **[Item references a non-existent `tool` on `source_mcp`]** → `add_pipeline_item` validates `source_mcp` against `.mcp.json` before any fetch; a wrong `tool` surfaces on the first backfill as `last_status="backfill_failed"` with the source MCP's error message.
- **[`cron-mcp` unreachable during `add_pipeline_item`]** → backfill still runs and data is stored; cron step records `last_status="cron_failed"` + `error_message`; `sync_pipeline_cron` retries later.
- **[Idempotent upsert needs a unique index on keys]** → bridge issues `CREATE UNIQUE INDEX IF NOT EXISTS` on `upsert_keys` after table creation; upsert uses `INSERT ... ON CONFLICT(...) DO UPDATE`.
- **[Synchronous backfill blocks the tool call for large history]** → acceptable for the seed datasets (single-symbol daily history); if a fetch exceeds a timeout, `last_status="backfill_failed"` and cron retries. Revisit async in Open Questions.
- **[`cron-mcp` has no `update_schedule`]** → wiring helper fetches the existing schedule's `enabled`/`prompt`/`agent` and recreates with the same values when only `cron`/`timezone` changed; otherwise leaves it.
- **[Per-symbol functions need a symbol universe]** → seed uses a representative symbol per item; multi-symbol watchlist is Open Question (carry-forward from the akshare change).

## Migration Plan

- **Deploy**: add `PipelineCollection` / `PipelineCollectionItem` to `mcp/models/models.py` (auto-created via `Base.metadata.create_all` — no Alembic); add `pipeline_tools.py` + `server.py` registration + CLI branches; add `seed_pipeline_from_mapping.py`. No data migration. Preview with `seed_pipeline_from_mapping.py --dry-run`, then seed to exercise create → add → backfill → cron. Trigger a re-fetch via `cron-mcp.run_now` or `python server.py --fetch-item <id>`.
- **Rollback**: `delete_pipeline_collection("akshare-t-md")` cascades item deletion + unwires all cron rows; `scraw_*` tables can be dropped via `sqlite3 mcp/daas.db "DROP TABLE scraw_<slug>"` (or left inert). Remove the new tools/tables in a follow-up — no other code depends on them.
- **Future migration to `data_job`**: when `add-cron-mcp-data-fetch` lands, each `pipeline_collection_item` already has the `source_mcp`/`tool`/`arguments_json` shape and maps 1:1 to `create_data_job(source_mcp=…, tool=…, arguments=…)` + `create_schedule(data_job=…)`. The `--fetch-item` shell-task bridge can retire in favor of `cron-mcp`'s built-in fetch+persist; `scraw_*` tables remain the storage format (or migrate to `cron_fetch_results`).

## Open Questions

- **Per-symbol watchlist**: one item per (function, params) with a fixed symbol, vs. a params template that iterates `mcp/akshare-mcp/watchlist.txt`. Lean: **one item per (function, params)** for v1 (matches the item model cleanly); multi-symbol is a follow-on that either spawns N items or adds a `watchlist` field to the item. To confirm with the user at apply time.
- **Synchronous vs. async backfill on add**: synchronous is simple and matches "automatically fetch the history data", but a very large history fetch could block. Lean: **synchronous with a per-fetch timeout** (e.g. 120s); items that time out get `last_status="backfill_timeout"` and are retried by cron. Revisit if the seed exposes problems.
- **Collection-level cadence override**: should a collection carry a default `cron`/`timezone` that items inherit when omitted? Lean: **no** — every item declares its own cadence (per-item pause/inspect is the point); a collection is purely a grouping. Revisit if the user wants collection-level defaults.
- **Fetch provenance log**: `cron-mcp.executions` already records task runs. A dedicated `pipeline_fetch_log` (run_at, item_id, row_count, status) is a possible follow-on; out of scope unless the user wants per-item history beyond `last_*` fields.
