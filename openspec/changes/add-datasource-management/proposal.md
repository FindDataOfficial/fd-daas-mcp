## Why

leader-mcp has 673+ functions cataloged but no way to treat them as managed datasources — you can't toggle them on/off, track when data was last fetched, or understand column provenance (where each column comes from and what it means). The dashboard has a `datasources` table but it's disconnected from the actual function registry. This bridges that gap.

## What Changes

- **Extend `functions` table** in `daas.db`: add `is_datasource`, `enabled`, `last_fetched_at` columns
- **Extend `function_columns` table**: add `source_field`, `unit`, `semantic_type` columns for provenance
- **New `data_snapshots` table**: store structured rows (JSON) from function calls, keyed by `(function_id, params_json)`
- **7 new MCP tools** on leader-mcp: `list_datasources`, `toggle_datasource`, `get_column_provenance`, `update_column_meta`, `save_snapshot`, `query_snapshots`, `list_snapshots`
- **Dashboard update**: datasource detail page shows column provenance fields and snapshot data tables

## Capabilities

### New Capabilities

- `datasource-management`: Mark functions as datasources, toggle enabled/disabled, track last fetch time. Exposed via `list_datasources` and `toggle_datasource` MCP tools.
- `column-provenance`: Document where each output column originates (`source_field`), its unit (`CNY`, `%`), and semantic role (`price`, `volume`, `date`). Editable via `update_column_meta`.
- `data-snapshots`: Save structured row data from function calls into a `data_snapshots` table. Query and list snapshots. Deduplicates by `(function_id, params_json)`.

### Modified Capabilities

None — no existing OpenSpec specs to modify.

## Impact

- **`mcp/leader-mcp/unified_models.py`**: add columns to `Function`, `FunctionColumn`; add `DataSnapshot` model
- **`mcp/leader-mcp/leader_tools.py`**: add 7 new tool functions
- **`mcp/leader-mcp/server.py`**: register new tools
- **`mcp/daas.db`**: schema migration (new columns + new table)
- **Dashboard** (`dashboard/`): update datasource detail page to render provenance and snapshots
- **Existing tools unaffected** — new columns default to NULL/False, all existing queries continue working
