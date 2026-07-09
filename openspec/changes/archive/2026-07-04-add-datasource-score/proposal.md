## Why

Datasources have no notion of priority or quality weight today. When an agent (or the dashboard's collection chat) resolves a request against multiple datasources in a collection, there is no signal for which one to prefer. This change introduces a **score** concept — a per-datasource numeric weight — at two levels: a **default score** on each datasource, and an optional **per-collection override** so the same datasource can be weighted differently inside different collections. A dedicated dashboard page lets the user manage both.

## What Changes

- **New `score` column on `sources`** (`DaasSource`) — the datasource's default score (Float, nullable; NULL = unset).
- **New `score` column on `datasource_collection_items`** (`DatasourceCollectionItem`) — a per-collection override (Float, nullable; NULL = inherit the datasource default).
- **Resolution rule**: a datasource's effective score within a collection is the collection-item score if set, else the datasource default score, else NULL.
- **`create_datasource` / `update_datasource`** gain an optional `score` param; `update_datasource` gains `clear_score` to reset it. Returned datasource dicts include `score`.
- **`add_to_collection`** gains an optional `score` param (set the override at add time).
- **New tool `set_collection_item_score`** — set or clear (`score=null`) the per-item override on an existing collection item.
- **`list_collection`** returns each item's resolved `score`, raw `item_score`, and `source_default_score`.
- **New `/scores` dashboard page** with two sections: (1) a default-score table for all datasources (inline-editable), (2) a collection picker + that collection's items with inline-editable per-item scores (default score shown for reference).
- **New API routes** `/api/scores/source` and `/api/scores/item`, plus `collection_writer.py` subcommands `set-source-score` / `set-item-score` (the existing write sidecar pattern).

## Capabilities

### New Capabilities

- `datasource-scores`: The score concept — `score` columns on `sources` and `datasource_collection_items`, the item-overrides-default resolution rule, and the `set_collection_item_score` MCP tool.
- `score-dashboard-ui`: The `/scores` dashboard page and its API routes for managing default scores and per-collection score overrides.

### Modified Capabilities

- `datasource-management`: `create_datasource` / `update_datasource` accept an optional `score` (and `clear_score` on update); datasource payloads include `score`.
- `datasource-collections`: `add_to_collection` accepts an optional `score`; `list_collection` returns resolved `score` + `item_score` + `source_default_score` per item.

## Impact

- **`mcp/models/models.py`**: add `score` (Float, nullable) to `DaasSource` and `DatasourceCollectionItem`; update `to_dict()` on both.
- **`mcp/daas-mcp/daas_database.py`**: two guarded `ALTER TABLE … ADD COLUMN score REAL` migrations (same idempotent pattern as `category_id` / `sort_order`).
- **`mcp/daas-mcp/registry_service.py`**: thread `score` through `create_datasource` / `update_datasource` / `add_to_collection` / `_source_detail`; add `set_collection_item_score`; resolve effective score in `list_collection`.
- **`mcp/daas-mcp/daas_tools.py`**: expose `score` / `clear_score` params and the new `set_collection_item_score` tool.
- **`mcp/daas-mcp/server.py`**: register `set_collection_item_score`.
- **`mcp/daas-mcp/collection_writer.py`**: add `set-source-score` and `set-item-score` subcommands.
- **Dashboard** (`dashboard/`): new `/scores` page + components, two API routes, `loadScores` read helpers in `lib/`, nav entry; `lib/collections.ts` / `lib/schema.ts` extended to carry score fields.
- **Existing tools unaffected** — new columns default to NULL; all existing queries and the catalog/chat workspace continue working unchanged.
