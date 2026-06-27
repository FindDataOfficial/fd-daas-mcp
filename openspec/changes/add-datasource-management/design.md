## Context

`leader-mcp` manages a unified registry of 673+ functions across multiple harnesses (akshare, ckan, cnstats, worldbank). The database is `mcp/daas.db` (set via `LEADER_MCP_DATABASE_URL` in `leader_database.py`). Currently:

- `functions` table has: id, harness, command, category, source, description, parameters (JSON)
- `function_columns` table has: id, function_id FK, column_name, column_type, column_description
- No concept of "this function is a datasource" or "when was data last fetched"
- No way to document column provenance (where the field comes from, what unit it uses)
- No storage for fetched data results

The dashboard at `dashboard/` has its own `dashboard.db` with `datasources` and `datasource_columns` tables, but these are disconnected from the function registry.

## Goals / Non-Goals

**Goals:**
- Extend `daas.db` schema to support datasource management, column provenance, and data snapshots
- Add MCP tools to leader-mcp for CRUD on these new capabilities
- Update dashboard datasource detail page to show provenance fields and snapshot data
- Zero impact on existing tools and queries (all new columns default to NULL/False)

**Non-Goals:**
- Unifying leader_mcp.db and daas.db (they stay separate)
- Auto-fetching/scheduling snapshots (manual save_snapshot only for v1)
- Modifying the dashboard.db `datasources` table schema
- Adding auth or multi-user support to the dashboard

## Decisions

### Decision 1: Extend existing tables vs new tables

**Chosen**: Extend `functions` and `function_columns` with nullable columns.

**Rationale**: Adding nullable columns to existing tables is backward-compatible — all existing queries continue to work. New columns default to NULL/False. Creating separate `datasource_metadata` and `column_provenance` tables would require JOINs for every read and complicate the existing `to_dict()` methods. The new fields are simple attributes of the existing entities.

**Alternative considered**: Separate `datasources` join table. Rejected because a function IS a datasource in this model — no need for an extra mapping table.

### Decision 2: Structured rows (JSON array of objects) for snapshots

**Chosen**: `data_json` column stores `[{col: val, ...}, ...]` — an array of row objects.

**Rationale**: Dashboard can render tables directly from JSON without parsing. ECharts can plot directly. Each row is a dict so column names are explicit (not positional arrays). SQLite JSON functions (`json_extract`, `json_array_length`) can query into the data if needed.

**Alternative considered**: Normalized `snapshot_rows` table (one row per cell). Rejected because it explodes row count (100 rows × 10 columns = 1000 SQL rows per snapshot) with no benefit for this use case.

### Decision 3: Dedup by `(function_id, params_json)` UNIQUE constraint

**Chosen**: `data_snapshots` has `UNIQUE(function_id, params_json)`.

**Rationale**: Calling the same function with the same params should upsert, not duplicate. If you call `stock_zh_a_hist(symbol=000001, start_date=20250101)` twice, you get one snapshot with updated data.

### Decision 4: semantic_type is an open string, not an enum

**Chosen**: `semantic_type` is VARCHAR(64), not a constrained enum.

**Rationale**: New harnesses bring new column types. Enum would require schema migration each time. Documentation in the tool description guides users to common values (price, volume, date, name, code, ratio, rate, amount, count, text).

## Risks / Trade-offs

- **Schema migration on live DB**: Adding columns to existing tables is safe in SQLite (ALTER TABLE ADD COLUMN). New table is a CREATE. No data loss risk. → Mitigation: migration script checks column existence before ALTER.
- **data_json size**: A 1000-row snapshot with 10 columns is ~200KB JSON. SQLite handles this fine, but we should cap at some reasonable limit. → Mitigation: `save_snapshot` tool limits to 10000 rows; returns error if exceeded.
- **UNIQUE on params_json**: JSON equality is byte-for-byte. `{"a":1}` and `{"a": 1}` (with space) are different strings. → Mitigation: normalize params (sort keys, compact JSON) before hashing.
