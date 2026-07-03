## ADDED Requirements

### Requirement: Pipeline collection storage

The system SHALL maintain a `pipeline_collections` table (id, name UNIQUE, description, created_at) and a `pipeline_collection_items` table where each item references a `collection_id` (FK, ON DELETE CASCADE) and carries `name`, `source_mcp`, `tool`, `arguments_json`, `storage_table`, `upsert_keys_json`, `cron_expr`, `timezone`, `enabled`, `task_name`, `last_run_at`, `last_status`, `last_row_count`, `error_message`, and `created_at`. This storage SHALL be distinct from the curation-only `datasource_collections` / `datasource_collection_items` tables and SHALL carry no fetch/storage/cron semantics in the curation tables.

#### Scenario: Tables are created on startup

- **WHEN** `daas-mcp` starts against an existing `mcp/daas.db`
- **THEN** `pipeline_collections` and `pipeline_collection_items` are created via `Base.metadata.create_all` without affecting existing tables

#### Scenario: Deleting a collection cascades to items

- **WHEN** a `pipeline_collections` row is deleted
- **THEN** all `pipeline_collection_items` rows with its `collection_id` are deleted by FK CASCADE

### Requirement: Create pipeline collection

The system SHALL expose a `create_pipeline_collection` tool that creates a named collection.

#### Scenario: Create a collection

- **WHEN** `create_pipeline_collection(name="akshare-t-md", description="A-share/HK daily pipeline")` is called
- **THEN** a `pipeline_collections` row is created and returned

#### Scenario: Duplicate name rejected

- **WHEN** `create_pipeline_collection(name="akshare-t-md")` is called and a collection with that name exists
- **THEN** the system returns an error and does not create a duplicate

### Requirement: List and get pipeline collection

The system SHALL expose `list_pipeline_collections` (returns every collection with its item count) and `get_pipeline_collection` (returns one collection with its items).

#### Scenario: List collections

- **WHEN** `list_pipeline_collections()` is called
- **THEN** every `pipeline_collections` row is returned with a count of its items

#### Scenario: Get one collection with items

- **WHEN** `get_pipeline_collection(name="akshare-t-md")` is called
- **THEN** the collection row and all its `pipeline_collection_items` are returned

### Requirement: Delete pipeline collection unwires cron

The system SHALL expose a `delete_pipeline_collection` tool that, before deleting the collection, unwires the `cron-mcp` task + schedule for every enabled item (via `cron-mcp` `delete_schedule` + `delete_task`), then deletes the collection row (FK CASCADE removes items). Fetched `scraw_<slug>` tables SHALL be left intact.

#### Scenario: Delete unwires all items

- **WHEN** `delete_pipeline_collection(name="akshare-t-md")` is called on a collection with 3 enabled items
- **THEN** the 3 corresponding `cron-mcp` tasks + schedules are deleted and the `pipeline_collections` row (and its items) are deleted

#### Scenario: Fetched data is preserved

- **WHEN** a collection whose items wrote `scraw_ashare_daily` is deleted
- **THEN** the `scraw_ashare_daily` table and its rows remain in `mcp/daas.db`

### Requirement: Add pipeline item validates and stores

The system SHALL expose an `add_pipeline_item` tool that, before storing the item, validates that `source_mcp` resolves to a launch config — either an entry in `.mcp.json`'s `mcpServers` or a `mcp/<source_mcp>/server.py` convention directory — validates `tool` is a non-empty string, validates `storage_table` matches `^scraw_[a-z0-9_]+$`, validates `cron_expr` is a 5-field cron expression, and validates `upsert_keys` is a non-empty list of valid identifiers. The item's `task_name` SHALL be derived as `pipeline_<collection_name>_<item_name>`.

#### Scenario: Valid item is stored

- **WHEN** `add_pipeline_item(collection_name="akshare-t-md", name="ashare-daily", source_mcp="akshare-mcp", tool="call_akshare_function", arguments_json='{"name":"stock_zh_a_hist","params_json":"{\"symbol\":\"000001\",\"period\":\"daily\"}"}', storage_table="scraw_ashare_daily", upsert_keys=["date","symbol"], cron_expr="30 16 * * 1-5", timezone="Asia/Shanghai")` is called
- **THEN** a `pipeline_collection_items` row is created with `task_name="pipeline_akshare-t-md_ashare-daily"` and `enabled=1`

#### Scenario: Unknown source MCP rejected

- **WHEN** `add_pipeline_item(..., source_mcp="not-in-mcp-json")` is called
- **THEN** the system returns an error naming the unknown source MCP and creates no row

#### Scenario: Invalid storage table rejected

- **WHEN** `add_pipeline_item(..., storage_table="not_scraw")` is called
- **THEN** the system returns an error and creates no row

### Requirement: Add pipeline item automatically backfills history

When `add_pipeline_item` adds an enabled item, the system SHALL immediately run a history backfill by spawning the item's `source_mcp` via `fastmcp.Client` (launch config read from `.mcp.json`), calling the item's `tool` with `arguments_json` (spread as kwargs), extracting the `data` records from the returned result, converting them to a DataFrame, and upserting them into the item's `storage_table` (`CREATE TABLE IF NOT EXISTS` with inferred columns, `CREATE UNIQUE INDEX IF NOT EXISTS` on `upsert_keys`, `ALTER TABLE ADD COLUMN` for new columns, `INSERT ... ON CONFLICT(keys) DO UPDATE`). The item's `last_run_at`, `last_status`, and `last_row_count` SHALL be updated.

#### Scenario: Backfill populates the storage table

- **WHEN** an enabled item for `stock_zh_a_hist` is added
- **THEN** `akshare-mcp` is spawned, `call_akshare_function` is called, `scraw_ashare_daily` is created with inferred columns, rows are upserted, and `last_status="ok"` with `last_row_count` set

#### Scenario: Backfill is idempotent on re-fetch

- **WHEN** `--fetch-item` is run again for the same item
- **THEN** the row count is unchanged (upsert on keys) and `last_status="ok"`

#### Scenario: Backfill failure records status

- **WHEN** the source MCP call raises an error during backfill
- **THEN** `last_status="backfill_failed"`, `error_message` is set, and no partial commit occurs

### Requirement: Add pipeline item automatically registers cron schedule

When `add_pipeline_item` adds an enabled item, after the backfill the system SHALL connect to `cron-mcp` via `fastmcp.Client` and idempotently register a `cron-mcp` task + schedule: `create_task(name=task_name, command="uv run --directory <abs_repo>/mcp/daas-mcp python server.py --fetch-item <item_id>")` (or `update_task` on name conflict), then `create_schedule(name=task_name, cron=cron_expr, task=task_name, timezone=timezone)`. The cron step's outcome SHALL be recorded on the item independently of the backfill outcome.

#### Scenario: Cron task and schedule are created

- **WHEN** an enabled item is added and `cron-mcp` is reachable
- **THEN** a `cron-mcp` task and schedule exist with the item's `cron_expr` and `timezone`, and the schedule's command runs `--fetch-item <item_id>`

#### Scenario: Cron failure does not roll back backfill

- **WHEN** the backfill succeeds but `cron-mcp` is unreachable
- **THEN** the item row remains, `last_status="cron_failed"` with `error_message` set, and the backfilled data is preserved

#### Scenario: Re-add is idempotent

- **WHEN** `add_pipeline_item` is called again with the same item name (after a remove, or via `sync_pipeline_cron`)
- **THEN** the existing `cron-mcp` task is updated (not duplicated) and the schedule is recreated only if `cron`/`timezone` changed

### Requirement: Remove pipeline item unwires cron

The system SHALL expose a `remove_pipeline_item` tool that deletes the item's `cron-mcp` task + schedule (via `delete_schedule` + `delete_task`) before deleting the item row. The `scraw_<slug>` table SHALL be left intact.

#### Scenario: Remove unwires and deletes

- **WHEN** `remove_pipeline_item(collection_name="akshare-t-md", name="ashare-daily")` is called
- **THEN** the corresponding `cron-mcp` task + schedule are deleted and the `pipeline_collection_items` row is deleted

### Requirement: Enable and disable pipeline item

The system SHALL expose `enable_pipeline_item` and `disable_pipeline_item` tools. Disabling an enabled item SHALL delete its `cron-mcp` schedule (keep the task row) and set `enabled=0`. Enabling a disabled item SHALL run the backfill and recreate the `cron-mcp` schedule, then set `enabled=1`.

#### Scenario: Disable stops scheduling

- **WHEN** `disable_pipeline_item(collection_name="akshare-t-md", name="ashare-daily")` is called
- **THEN** the `cron-mcp` schedule is deleted, the task row remains, and `enabled=0`

#### Scenario: Enable backfills and reschedules

- **WHEN** `enable_pipeline_item(collection_name="akshare-t-md", name="ashare-daily")` is called on a disabled item
- **THEN** a backfill runs, the `cron-mcp` schedule is recreated, and `enabled=1`

### Requirement: Update pipeline item

The system SHALL expose an `update_pipeline_item` tool that updates an item's mutable fields (`arguments_json`, `cron_expr`, `timezone`, `upsert_keys`, `description`, `enabled`). Changing `cron_expr` or `timezone` SHALL re-sync the `cron-mcp` schedule. Changing `arguments_json` SHALL NOT auto-backfill (the next cron tick fetches with the new arguments); the user can trigger a re-fetch via `--fetch-item`.

#### Scenario: Cron change resyncs schedule

- **WHEN** `update_pipeline_item(..., cron_expr="0 17 * * 1-5")` changes the cadence
- **THEN** the `cron-mcp` schedule is recreated with the new cron and the item row is updated

### Requirement: Fetch-to-store CLI branch

The system SHALL support a `python server.py --fetch-item <item_id>` CLI branch (and `--register-cron <item_id>` / `--unregister-cron <item_id>` / `--sync-cron`) that runs the in-process fetch-to-store path (or cron wiring) for one item / all items, prints a JSON summary, and exits — no stdio server — so `cron-mcp` shell tasks can invoke it.

#### Scenario: CLI fetch runs the bridge

- **WHEN** `uv run --directory mcp/daas-mcp python server.py --fetch-item 7` is run
- **THEN** item 7 is resolved, its `source_mcp` is spawned, `tool` is called, the `scraw_<slug>` table is upserted, and a JSON summary `{"status":"ok","item":...,"rows":N}` is printed on stdout with exit 0

#### Scenario: CLI fetch failure exits non-zero

- **WHEN** the fetch fails
- **THEN** a JSON summary `{"status":"failed","error":...}` is printed and the process exits non-zero

### Requirement: Sync pipeline cron

The system SHALL expose a `sync_pipeline_cron` tool (and `--sync-cron` CLI branch) that, for every enabled item, idempotently re-applies the `cron-mcp` task + schedule wiring, and for every disabled item, ensures its schedule is removed. This is the recovery path after restarts or `cron_failed` statuses.

#### Scenario: Sync recovers missing schedules

- **WHEN** `sync_pipeline_cron()` is called after a `cron-mcp` DB reset
- **THEN** every enabled item has a `cron-mcp` task + schedule, and `last_status` is updated to reflect the sync

### Requirement: List pipeline items

The system SHALL expose a `list_pipeline_items` tool that returns all items for a collection (or all items across collections when no collection is named), including each item's `enabled`, `last_run_at`, `last_status`, `last_row_count`, and `task_name`.

#### Scenario: List items in a collection

- **WHEN** `list_pipeline_items(collection_name="akshare-t-md")` is called
- **THEN** every item in that collection is returned with its status fields

### Requirement: Seed from the akshare datasource mapping

The system SHALL ship a `seed_pipeline_from_mapping.py` script that creates a `pipeline_collection` (default name `akshare-t-md`) and adds one item per `t.md` data need mapped in `openspec/changes/akshare-cron-data-pipeline/datasource-mapping.md` (e.g. `stock_zh_a_hist`, `stock_sse_summary`, `stock_szse_summary`, `stock_zh_ah_spot_em`, `stock_dzjy_mrmx`, `stock_hk_hist`, `stock_research_report_em`, `stock_profit_forecast_em`, `stock_zygc_em`), each with its `scraw_<slug>` storage table, upsert keys, and `Asia/Shanghai` off-minute cron cadence. The script SHALL support `--dry-run`, `--only <name>`, and `--unseed`, and SHALL be idempotent on collection name + item name.

#### Scenario: Dry run plans without side effects

- **WHEN** `seed_pipeline_from_mapping.py --dry-run` is run
- **THEN** the planned collection + items + cron expressions are printed and no DB/cron rows are created

#### Scenario: Seed creates collection and wires cron

- **WHEN** `seed_pipeline_from_mapping.py` is run
- **THEN** a `pipeline_collection` row exists, one `pipeline_collection_items` row per mapped need exists (each enabled, backfilled, with a `cron-mcp` task + schedule)

#### Scenario: Unseed removes collection and unwires cron

- **WHEN** `seed_pipeline_from_mapping.py --unseed` is run
- **THEN** the `akshare-t-md` collection is deleted, all its items' `cron-mcp` tasks + schedules are deleted, and `scraw_*` tables are left intact

#### Scenario: Re-seed is idempotent

- **WHEN** `seed_pipeline_from_mapping.py` is run again
- **THEN** existing items are updated (not duplicated) and `cron-mcp` rows are not duplicated
