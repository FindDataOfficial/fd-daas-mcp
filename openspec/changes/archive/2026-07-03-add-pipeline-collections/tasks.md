## 1. Schema (`mcp/models/models.py`)

- [x] 1.1 Add `PipelineCollection` model: `id` (PK), `name` (UNIQUE, non-null), `description` (Text, nullable), `created_at` (DateTime, default now). Table name `pipeline_collections`.
- [x] 1.2 Add `PipelineCollectionItem` model: `id` (PK), `collection_id` (FK → `pipeline_collections.id`, `ON DELETE CASCADE`), `name` (non-null), `source_mcp` (e.g. `akshare-mcp`), `tool` (e.g. `call_akshare_function`), `arguments_json` (Text — the tool's kwargs, e.g. `{"name":"stock_zh_a_hist","params_json":"{...}"}`), `storage_table`, `upsert_keys_json` (Text), `cron_expr`, `timezone` (default `"Asia/Shanghai"`), `enabled` (Boolean, default True), `task_name` (nullable), `last_run_at` (nullable DateTime), `last_status` (nullable), `last_row_count` (nullable Integer), `error_message` (nullable Text), `created_at` (DateTime, default now). Table name `pipeline_collection_items`. Add a unique constraint on `(collection_id, name)`.
- [x] 1.3 Confirm both tables are exported from `mcp/models/__init__.py` and that `Base.metadata.create_all` creates them in a temp DB without affecting existing tables.

## 2. `daas-mcp` database wiring (`daas_database.py`)

- [x] 2.1 Ensure `pipeline_collections` / `pipeline_collection_items` are created on `daas-mcp` startup via `Base.metadata.create_all` (no Alembic). Add a helper `get_collection_by_name`, `list_collections`, `get_item(collection_id, name)`, `upsert_item`, `delete_item`.
- [x] 2.2 Add an identifier/cron validator reused by tools: `storage_table` matches `^scraw_[a-z0-9_]+$`, `upsert_keys` items match `^[A-Za-z_][A-Za-z0-9_]*$`, `cron_expr` is 5-field — reject with a clear error before any SQL or fetch.
- [x] 2.3 Add a launch-config resolver + validator: `source_mcp` resolves if it is either an entry in root `.mcp.json`'s `mcpServers` OR a `mcp/<source_mcp>/server.py` convention directory (akshare-mcp etc. are not in `.mcp.json`). Add a helper to return the resolved launch config (command/args/cwd/env) for the bridge + cron client. (`tool` is validated lazily on first fetch.)

## 3. Fetch-to-store bridge (`fastmcp.Client` → source MCP → `scraw_<slug>`)

- [x] 3.1 Create `mcp/daas-mcp/pipeline_tools.py` with a `fetch_to_store(item)` function that reads the item's `source_mcp` launch config from `.mcp.json`, spawns it via `fastmcp.Client` (stdio subprocess transport), calls the item's `tool` with `arguments_json` (parsed dict, spread as kwargs), extracts the `data` records from the returned result (registry-style MCPs return `{"type":"dataframe","columns":[...],"data":[...]}`), converts `data` to a `pandas.DataFrame`, and returns `(row_count, status, error)`. Close the client at the end.
- [x] 3.2 Implement storage: `CREATE TABLE IF NOT EXISTS <storage_table>` with columns inferred from the DataFrame; `CREATE UNIQUE INDEX IF NOT EXISTS` on `upsert_keys`; detect new columns and `ALTER TABLE ... ADD COLUMN` (inferred type, default NULL) before upserting; `INSERT ... ON CONFLICT(<keys>) DO UPDATE SET <non-key cols>`; commit once per run. Roll back on any error (no partial commit).
- [x] 3.3 Resolve `DAAS_DATABASE_URL`; resolve relative `sqlite:///` against the repo root (mirror `process-mcp`'s resolution) so the `--fetch-item` cron path works under `uv run --directory`.
- [x] 3.4 Set SQLite `PRAGMA foreign_keys=ON` per connection (consistent with `daas-mcp`'s existing convention).

## 4. `cron-mcp` client wiring (`pipeline_tools.py`)

- [x] 4.1 Resolve the `cron-mcp` launch command from `.mcp.json` (override via `CRON_MCP_COMMAND` env); connect via `fastmcp.Client` (subprocess transport).
- [x] 4.2 Wrap the `cron-mcp` calls used: `list_db_tasks`, `create_task`, `update_task`, `delete_task`, `list_schedules`, `create_schedule`, `delete_schedule`, `run_now`.
- [x] 4.3 Implement `register_cron_for_item(item)`: build `command = "uv run --directory <abs_repo>/mcp/daas-mcp python server.py --fetch-item <item_id>"` (absolute path from `Path(__file__).resolve().parents[1]`); `task_name = pipeline_<collection_name>_<item_name>`; idempotent create-or-update task; `create_schedule(name=task_name, cron=cron_expr, task=task_name, timezone=timezone)`. If a schedule exists and only `cron`/`timezone` changed, delete + recreate preserving `enabled`. Return `(status, error)`.
- [x] 4.4 Implement `unregister_cron_for_item(item)`: `delete_schedule` then `delete_task` for `task_name`; tolerate "not found" (idempotent).

## 5. `daas-mcp` CLI branches (`server.py`)

- [x] 5.1 Add `--fetch-item <item_id>`: resolve the item, run `fetch_to_store`, update `last_run_at`/`last_status`/`last_row_count`/`error_message`, print JSON `{"status":"ok","item":...,"rows":N}` (exit 0) or `{"status":"failed","error":...}` (exit non-zero). No stdio server.
- [x] 5.2 Add `--register-cron <item_id>` and `--unregister-cron <item_id>`: run the cron wiring/unwiring for one item, print JSON summary, exit.
- [x] 5.3 Add `--sync-cron`: run `sync_pipeline_cron` for all items, print JSON summary, exit.
- [x] 5.4 Mirror `process-mcp`'s arg-parsing pattern; ensure the server still starts normally when no CLI branch is given.

## 6. Collection + item management tools (`pipeline_tools.py` + `server.py`)

- [x] 6.1 `create_pipeline_collection(name, description)` → create row; reject duplicate name.
- [x] 6.2 `list_pipeline_collections()` → all collections with item counts; `get_pipeline_collection(name)` → collection + items.
- [x] 6.3 `delete_pipeline_collection(name)` → for each enabled item `unregister_cron_for_item`, then delete the collection row (FK CASCADE removes items). Leave `scraw_*` intact.
- [x] 6.4 `list_pipeline_items(collection_name=None)` → items (filtered by collection if given) with status fields + `task_name`.
- [x] 6.5 `add_pipeline_item(collection_name, name, source_mcp, tool, arguments_json, storage_table, upsert_keys, cron_expr, timezone="Asia/Shanghai", enabled=True, backfill=True)` → validate (§2.2, §2.3), store the row, set `task_name`. If `enabled and backfill`: run `fetch_to_store` then `register_cron_for_item`; record `last_*` fields independently for each step. Return `{item, backfill:{status,rows}, cron:{status,task,schedule}}`.
- [x] 6.6 `remove_pipeline_item(collection_name, name)` → `unregister_cron_for_item` then delete the item row. Leave `scraw_*` intact.
- [x] 6.7 `enable_pipeline_item(collection_name, name)` → run `fetch_to_store` + `register_cron_for_item`, set `enabled=1`. `disable_pipeline_item(collection_name, name)` → `delete_schedule` (keep task row), set `enabled=0`.
- [x] 6.8 `update_pipeline_item(collection_name, name, ...)` → update mutable fields (`arguments_json`, `cron_expr`, `timezone`, `upsert_keys`, `description`, `enabled`); if `cron_expr`/`timezone` changed, re-sync the schedule; if `enabled` toggled, run enable/disable path. Changing `arguments_json` does NOT auto-backfill.
- [x] 6.9 `sync_pipeline_cron()` → for each enabled item, idempotent `register_cron_for_item`; for each disabled item, ensure schedule removed. Update `last_status` to reflect the sync.
- [x] 6.10 Register all tools on `server.py`'s FastMCP instance.

## 7. Seed script (`mcp/daas-mcp/seed_pipeline_from_mapping.py`)

- [x] 7.1 Define a curated list of items from `openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md`: at minimum `stock_zh_a_hist` (沪深日行情), `stock_sse_summary` + `stock_szse_summary` (成交概况), `stock_szse_sector_summary` (行业估值), `stock_zh_ah_spot_em` (AH比价), `stock_dzjy_mrmx` (大宗交易), `stock_individual_info_em` (基本信息), `stock_share_change_cninfo` (股本变动), `stock_gpzy_pledge_ratio_em` (股权质押), `stock_ggcg_em` (高管持股), `stock_fhps_em` (分红), `stock_hk_hist` (港股日行情), `stock_individual_basic_info_hk_xq` (港股基本信息), `stock_hk_fhpx_detail_ths` (港股公司行为), `stock_research_report_em` (券商研报), `stock_profit_forecast_em` (盈利预测), `stock_zygc_em` (主营构成). Each entry: `name`, `source_mcp="akshare-mcp"`, `tool="call_akshare_function"`, `arguments_json` (built from the mapping's `function` + `required params` as `{"name": <function>, "params_json": <json string>}`), `storage_table`, `upsert_keys`, `cron_expr`, `timezone="Asia/Shanghai"`.
- [x] 7.2 Cadence (off-minute staggered, `Asia/Shanghai`): A-share-close datasets weekdays ~16:30–17:30; HK `0 18 * * 1-5`; research/forecast ~18:30; low-churn (质押/增发/配股) weekly Friday; event-driven (股本变动/分红) monthly/quarterly. No two items at the same `:00`/`:30`.
- [x] 7.3 Implement `--dry-run` (print planned collection + items + crons, no DB/cron writes), `--only <name>` (seed one), `--unseed` (delete the collection → cascades cron unwiring), default collection name `akshare-t-md` (override via `--collection`).
- [x] 7.4 Idempotent on collection name + item name: re-run updates existing items (via `update_pipeline_item`) and does not duplicate `cron-mcp` rows.
- [x] 7.5 Call `add_pipeline_item` per entry (so each item is validated, backfilled, and cron-wired). Print a JSON summary `{created:[...], updated:[...], failed:[...]}`.

## 8. Smoke test (`mcp/daas-mcp/selfcheck_pipeline.py` or extend `selfcheck.py`)

- [x] 8.1 `--no-network` mode: import models, assert tables create in a temp DB, assert the identifier/cron validators reject bad `storage_table`/`cron_expr`/`upsert_keys`, assert `add_pipeline_item` rejects an unknown `source_mcp`, assert CLI arg parsing for `--fetch-item` works.
- [x] 8.2 Live mode (gated behind `AKSHARE_LIVE=1`): create a temp collection, `add_pipeline_item` for `stock_individual_info_em` (one symbol) into `scraw__selfcheck`, assert rows inserted, re-run `--fetch-item` and assert row count unchanged (idempotent upsert), inject a synthetic new column and assert `ALTER TABLE` appended it.
- [x] 8.3 Assert a forced source-MCP error produces `last_status="backfill_failed"` and a non-zero exit from `--fetch-item` (mock the `fastmcp.Client` call).
- [x] 8.4 Assert `cron_failed` path: when `cron-mcp` is unreachable (mock the client), `add_pipeline_item` still stores the item + backfilled data with `last_status="cron_failed"`.

## 9. End-to-end verification

- [x] 9.1 Run `uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py --dry-run` and review the planned items + cron expressions against `design.md`'s cadence table.
- [x] 9.2 Run `uv run --directory mcp/daas-mcp python seed_pipeline_from_mapping.py` (or `--only ashare-daily` for a first pass) and confirm the `akshare-t-md` collection + items exist.
- [x] 9.3 Via `cron-mcp`, call `list_schedules` and confirm each enabled item has the correct `cron`, `task`, `timezone="Asia/Shanghai"`, and a command ending in `--fetch-item <id>`.
- [x] 9.4 Confirm each item's `scraw_<slug>` table has rows via `dashboard-mcp.query_table(database="daas", table="scraw_ashare_daily")`.
- [x] 9.5 Trigger a re-fetch via `cron-mcp.run_now` (or `python server.py --fetch-item <id>`) and confirm idempotency (row count stable, `last_status="ok"`).
- [x] 9.6 Verify unwiring: `disable_pipeline_item` on one item removes its `cron-mcp` schedule (task row kept); `enable_pipeline_item` recreates it.
- [x] 9.7 Verify cleanup: `seed_pipeline_from_mapping.py --unseed` removes the collection + all `cron-mcp` rows and leaves `scraw_*` tables intact.
- [x] 9.8 Verify recovery: drop one `cron-mcp` schedule manually, run `sync_pipeline_cron`, confirm the schedule is recreated.

## 10. Documentation

- [x] 10.1 Update `CLAUDE.md` `mcp/daas-mcp/` section: add the `pipeline_collections` / `pipeline_collection_items` tables, the ~11 new tools, the `--fetch-item` / `--register-cron` / `--unregister-cron` / `--sync-cron` CLI branches, `seed_pipeline_from_mapping.py`, and a note distinguishing managed `pipeline_collections` from curation `datasource_collections`.
- [x] 10.2 Add a short `mcp/daas-mcp/README.md` section (or extend the existing one) with one worked example: create a collection → add an item (auto backfill + cron) → inspect via `cron-mcp` / `dashboard-mcp` → disable/remove.
- [x] 10.3 Note the relationship to `akshare-cron-data-pipeline` (the managed path supersedes the standalone helper scripts for collections managed through `daas-mcp`; `datasource-mapping.md` is the seed source) and to `add-cron-mcp-data-fetch` (items migrate 1:1 to `data_job` when that lands).
