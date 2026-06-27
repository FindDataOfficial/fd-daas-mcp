## 1. Schema Migration

- [x] 1.1 Add `is_datasource` (BOOLEAN, default False), `enabled` (BOOLEAN, default True), `last_fetched_at` (DATETIME, nullable) columns to `Function` model in `unified_models.py`
- [x] 1.2 Add `source_field` (VARCHAR, nullable), `unit` (VARCHAR(32), nullable), `semantic_type` (VARCHAR(64), nullable) columns to `FunctionColumn` model in `unified_models.py`
- [x] 1.3 Create `DataSnapshot` model in `unified_models.py` with columns: id (PK), function_id (FK), params_json (JSON), fetched_at (DATETIME), status (TEXT), data_json (JSON), row_count (INTEGER), plus UNIQUE(function_id, params_json)
- [x] 1.4 Add migration logic to `leader_database.py` init_db(): ALTER TABLE ADD COLUMN for new columns (check existence first), CREATE TABLE IF NOT EXISTS for data_snapshots
- [x] 1.5 Run migration against `mcp/daas.db` and verify schema with `sqlite3 .schema`

## 2. Datasource Management Tools

- [x] 2.1 Implement `list_datasources(harness: Optional[str] = None)` in `leader_tools.py` — query functions where is_datasource=true, return grouped by harness with enabled status and last_fetched_at
- [x] 2.2 Implement `toggle_datasource(harness: str, command: str, enabled: Optional[bool] = None, is_datasource: Optional[bool] = None)` — update function's datasource flags, return updated state
- [x] 2.3 Implement `save_snapshot(harness: str, command: str, params: dict)` — resolve the function, call it via the harness adapter, parse DataFrame to JSON rows, upsert into data_snapshots, update last_fetched_at, cap at 10000 rows
- [x] 2.4 Implement `list_snapshots(harness: Optional[str] = None, command: Optional[str] = None)` — list stored snapshots with function name, row count, status, fetched_at
- [x] 2.5 Implement `query_snapshots(snapshot_id: int, limit: int = 50, offset: int = 0)` — return paginated data_json rows for a snapshot

## 3. Column Provenance Tools

- [x] 3.1 Implement `get_column_provenance(harness: str, command: str)` in `leader_tools.py` — return all columns with source_field, unit, semantic_type alongside existing name/type/description
- [x] 3.2 Implement `update_column_meta(harness: str, command: str, column_name: str, source_field: Optional[str] = None, unit: Optional[str] = None, semantic_type: Optional[str] = None)` — update only the provided fields on the matching column

## 4. Server Registration

- [x] 4.1 Register all 7 new tools in `server.py` via `app.add_tool()`
- [x] 4.2 Verify leader-mcp starts without errors and `list_harnesses` still works

## 5. Dashboard Updates

- [x] 5.1 Update datasource detail page to include Source Field, Unit, and Semantic Type columns in the columns table
- [x] 5.2 Add Snapshots section to datasource detail page: list snapshots with fetch time, row count, status
- [x] 5.3 Add snapshot data viewer: click a snapshot to see paginated rows table (50 rows/page)

## 6. Tests

- [x] 6.1 Write test for schema migration: verify new columns and data_snapshots table exist after init_db()
- [x] 6.2 Write tests for datasource tools: list_datasources, toggle_datasource with edge cases (not found, toggle off, unmark)
- [x] 6.3 Write tests for column provenance tools: get_column_provenance, update_column_meta with partial update
- [x] 6.4 Write tests for snapshot tools: save_snapshot, list_snapshots, query_snapshots with upsert and error cases
- [x] 6.5 Run existing test suite to verify no regressions

## 7. Documentation

- [x] 7.1 Update CLAUDE.md with new leader-mcp tools and their descriptions
- [x] 7.2 Update dashboard quickstart if needed for new provenance/snapshot features
