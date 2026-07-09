## Why

`daas-mcp` already has a scored-datasource concept (`sources.score` default + per-collection `datasource_collection_items.score` override, with effective-score resolution) and a `/scores` dashboard page to manage it. Indicators (`indicator_rules`) have **no score at all** and no collection concept — so an operator cannot express "this RSI indicator matters more than that SMA indicator", cannot group indicators into reusable bundles, and cannot say "indicator X is high-priority in the `us-leaders` collection but low-priority in the `cn-macro` collection". We need the same score+collection ergonomics for indicators that already exist for datasources, with the inheritance chain the operator asked for: **datasource score → indicator score (inherits) → indicator-collection-item score (inherits/overrides)**.

## What Changes

- Add a nullable `score` column (Float) to `indicator_rules`. NULL = "inherit the datasource's default `sources.score`". Additive `ALTER TABLE` migration (mirrors `_migrate_sources_score`).
- Extend `create_indicator` / `update_indicator` to accept an optional `score`; `get_indicator` / `list_indicators` return it.
- Add a `set_indicator_score(name, score)` tool that sets/clears the indicator default score (`score=null` clears → falls back to datasource).
- Add a new **indicator collections** concept: two tables `indicator_collections` (name UNIQUE, description) and `indicator_collection_items` (collection_id FK CASCADE, indicator_id FK→`indicator_rules.id` ON DELETE CASCADE, sort_order, `score` nullable override). Created via `Base.metadata.create_all` (additive, no Alembic) — mirrors `datasource_collections` / `datasource_collection_items`.
- Add a 3-level **effective score resolution** for an indicator in a collection: item `score` override if set → else `indicator_rules.score` if set → else `sources.score` (the datasource default). Surfaced by `list_indicator_collection` for every item.
- Add CRUD + membership tools for indicator collections: `create_indicator_collection`, `list_indicator_collections`, `get_indicator_collection`, `delete_indicator_collection`, `add_indicator_to_collection` (accepts optional `score`), `remove_indicator_from_collection`, `list_indicator_collection_items`, `reorder_indicator_collection_items`, `set_indicator_collection_item_score` (sets/clears the per-item override), `list_indicator_collection_changes` (membership audit log, mirrors `entity_collection_changes`).
- Add `collection_writer.py` subcommands: `set-indicator-score`, `set-indicator-collection-item-score`, plus the indicator-collection CRUD/membership subcommands used by the dashboard.
- Dashboard: add an inline-editable **score** column (with resolved inherited value + datasource default for reference) to the existing `/process/indicators` page; add a new **indicators collection** page (list + detail) where an operator can group indicators and set per-item scores, with the resolved effective score shown per row. Reads via sql.js; writes via the new `collection_writer.py` subcommands through `/api/...` routes.
- Self-check: `selfcheck_indicator_scores.py` (temp DB, no network) guarding the score column migration, the 3-level resolution rule, the per-item override set/clear, and the writer subcommands — mirroring `selfcheck_scores.py`.

## Capabilities

### New Capabilities
- `indicator-scores`: A nullable `score` on `indicator_rules` (default indicator priority/quality weight) with effective-score resolution that inherits the datasource's default `sources.score` when NULL; `set_indicator_score` tool; `score` param on `create_indicator`/`update_indicator`. Mirrors `datasource-scores`.
- `indicator-collections`: Named, ordered groups of indicators (`indicator_collections` + `indicator_collection_items` tables) with membership CRUD, sort ordering, an add-in/remove-out audit log, and a per-item `score` override whose effective resolution chains item-override → indicator-default → datasource-default (3-level). Mirrors `datasource-collections` + the collection-item-score parts of `datasource-scores`.
- `indicator-scores-dashboard-ui`: Dashboard management for indicator scores — an inline-editable score column on the `/process/indicators` page, a new indicators-collection page (list + detail with add/remove/reorder + per-item score override + resolved effective score), the `/api/...` routes, and the `collection_writer.py` score subcommands. Reads via sql.js; writes via the Python sidecar.

### Modified Capabilities
<!-- None — following the datasource-scores precedent, the score param on
     create_indicator/update_indicator is owned by `indicator-scores` and the
     indicator_rules.score column is additive (no existing requirement changes). -->

## Impact

- **`mcp/models/models.py`**: add `score` to `IndicatorRule`; add `IndicatorCollection` + `IndicatorCollectionItem` (+ `IndicatorCollectionChange` audit table if membership audit is included). Update `to_dict()` outputs.
- **`mcp/daas-mcp/`**: `process_database.py` (migration + score on IndicatorRule CRUD), `indicator_tools.py` (`create_indicator`/`update_indicator`/`set_indicator_score`), new `indicator_collection_tools.py` + `IndicatorCollectionService` in `registry_service.py` + `indicator_collection_database.py` (or reuse `daas_database.py`), `process_api.py` (wire new tools), `collection_writer.py` (new subcommands), `server.py` (register tools + any `--sync-indicator-collection` CLI branch), `selfcheck_indicator_scores.py` (new).
- **`dashboard/`**: extend `/process/indicators/page.tsx` (score column), new `/process/indicators/collections/` route tree (list + `[name]` detail), new `dashboard/src/lib/indicator-collections.ts` + extend `indicator-scores` read helpers, new `/api/indicators/score` + `/api/indicators/collections/*` routes, `dashboard/src/lib/schema.ts` types, nav entry.
- **Databases**: additive only — `mcp/daas.db` gains `indicator_rules.score` (guarded ALTER) + 2–3 new tables via `create_all`. No breaking schema change; no data loss.
- **No breaking API changes** — all new tools/columns are additive and optional.
