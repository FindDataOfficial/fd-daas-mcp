## Why

Today, wiring a datasource to fetch on a schedule into storage is either (a) **manual and akshare-specific** — the `akshare-cron-data-pipeline` change ships standalone `datasets.py` / `fetch_to_store.py` / `register_cron.py` helper scripts that are not managed by any MCP — or (b) dependent on the `data_job` / `cron_fetch_results` abstraction from `add-cron-mcp-data-fetch`, which is specced but **not implemented**. Neither gives the user what they asked for: a *managed*, source-agnostic "datasource collection" where creating a collection, adding a datasource, and getting history backfill + a cron-mcp schedule is one operation, reproducible across many collections, with the wiring inspected/managed through daas-mcp tools.

## What Changes

- **New — managed pipeline collections in `daas-mcp`**: a named collection of fetch *items*, where each item binds a source MCP (`source_mcp` + `tool` + `arguments_json` — e.g. `source_mcp="akshare-mcp"`, `tool="call_akshare_function"`, `arguments_json='{"name":"stock_zh_a_hist","params_json":"{\"symbol\":\"000001\"}"}'`) to a storage target (`scraw_<slug>` table + upsert keys) and a cadence (cron expression + timezone). This is the same `source_mcp`/`tool`/`arguments` shape specced by `add-cron-mcp-data-fetch`'s `data_job`, so items migrate 1:1 later. Stored in **two new tables** (`pipeline_collections`, `pipeline_collection_items`) — distinct from the existing curation-only `datasource_collections` / `datasource_collection_items`, which group datasources for the NotebookLM-style workspace and carry no fetch/storage/cron semantics.
- **New — daas-mcp management tools**: `create_pipeline_collection`, `list_pipeline_collections`, `get_pipeline_collection`, `delete_pipeline_collection`, `add_pipeline_item`, `remove_pipeline_item`, `list_pipeline_items`, `update_pipeline_item`, `enable_pipeline_item`, `disable_pipeline_item`, `sync_pipeline_cron`.
- **New — auto backfill + auto cron on add**: when `add_pipeline_item` adds an enabled item, daas-mcp (i) runs an immediate history backfill via a fetch-to-store bridge that spawns the item's `source_mcp` via `fastmcp.Client` (launch config read from `.mcp.json`), calls `tool` with `arguments_json`, and upserts the returned records into the item's `scraw_<slug>` table, then (ii) calls `cron-mcp` via `fastmcp.Client` to idempotently `create_task` + `create_schedule`. Removing or disabling an item unwires (deletes) the corresponding cron-mcp task + schedule.
- **New — daas-mcp fetch-to-store CLI branch**: `python server.py --fetch-item <item_id>` (and `--register-cron <item_id>` / `--unregister-cron <item_id>`) so cron-mcp shell tasks invoke the bridge — mirrors `process-mcp`'s `--run-rule` cron pattern.
- **New — seed/test from the akshare mapping**: `seed_pipeline_from_mapping.py` loads the `openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md` examples (沪深日行情, 成交概况, AH比价, 大宗交易, 港股日行情, 研报, …) into a `pipeline_collection` named e.g. `akshare-t-md` and exercises the full create → add → backfill → cron path end-to-end.

No **BREAKING** changes. `daas-mcp`'s existing tool surface and the curation `datasource-collections` capability are unchanged. `cron-mcp` and `akshare-mcp` are consumed as-is (no new tools, no schema change) — `cron-mcp` gains only `tasks` + `schedules` rows.

## Capabilities

### New Capabilities

- `pipeline-collections`: Managed, source-agnostic "datasource collections" in `daas-mcp` — a named collection of fetch items (daas source + function + params + `scraw_<slug>` storage + upsert keys + cron + timezone), with management tools and automatic history backfill + `cron-mcp` schedule registration on add (and unwiring on remove/disable). Distinct from the curation-only `datasource-collections` capability.

### Modified Capabilities

<!-- None. The existing datasource-collections (curation), datasource-management, and cron-mcp capabilities are consumed as-is; no spec-level requirement of an existing capability changes. -->

## Impact

- **`mcp/models/models.py`**: +2 tables — `PipelineCollection` (id, name UNIQUE, description, created_at) and `PipelineCollectionItem` (id, collection_id FK CASCADE, name, source_mcp, tool, arguments_json, storage_table, upsert_keys_json, cron_expr, timezone, enabled, task_name, last_run_at, last_status, last_row_count, error_message, created_at). Created via `Base.metadata.create_all`; no Alembic.
- **`mcp/daas-mcp/`**: new `pipeline_tools.py` (collection/item CRUD + fetch-to-store bridge + `cron-mcp` client wiring), extend `server.py` (register ~11 new tools + the `--fetch-item` / `--register-cron` / `--unregister-cron` / `--sync-cron` CLI branches), new `seed_pipeline_from_mapping.py`. Uses the `daas_database.Database` singleton pattern.
- **`mcp/daas.db`**: new `pipeline_collections` / `pipeline_collection_items` tables auto-created; new `scraw_<slug>` tables auto-created on first fetch (queryable via `dashboard-mcp.query_table` and usable as `process-mcp` rule source tables).
- **`cron-mcp`**: new `tasks` + `schedules` rows only — **no schema change**, no new tools (called as a `fastmcp.Client` client; `create_task` / `create_schedule` / `delete_schedule` / `run_now`).
- **Source MCPs** (`akshare-mcp`, `yfinance-mcp`, …): unchanged — each is spawned as a stdio subprocess by the bridge via `fastmcp.Client` using the launch command already in `.mcp.json`, and its `call_<source>_function` (or other) tool is called with `arguments_json`. `daas-mcp`'s own `fetch_data` is intentionally not used (its `daas-agent-harness` path is mis-resolved and the daas registry has no akshare functions).
- **Dependencies**: `fastmcp` (already present — now used by the bridge to reach the source MCP and `cron-mcp`), `pandas` (already present). No new runtime dependency.
- **Related work**: supersedes the *managed-path* portion of `akshare-cron-data-pipeline` (its `datasets.py` catalog and `datasource-mapping.md` become the seed source for this capability; its standalone `register_cron.py` / `fetch_to_store.py` helpers are no longer needed for collections managed through daas-mcp, though they remain a valid manual path). Compatible with `add-cron-mcp-data-fetch`: each `pipeline_collection_item` already has the `source_mcp`/`tool`/`arguments` shape, so it maps 1:1 to a future `create_data_job` + `create_schedule(data_job=...)` and the shell-task bridge can be retired.
