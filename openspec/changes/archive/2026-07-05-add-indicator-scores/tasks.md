## 1. Schema (shared `mcp/models`)

- [x] 1.1 Add `score = Column(Float, nullable=True, default=None)` to `IndicatorRule` in `mcp/models/models.py`; include `score` in `IndicatorRule.to_dict()`.
- [x] 1.2 Add `IndicatorCollection` model (id, unique `name`, `description`, `created_at`, `updated_at`; `items` relationship cascade all delete-orphan) — mirror `DatasourceCollection`.
- [x] 1.3 Add `IndicatorCollectionItem` model (id, `collection_id` FK→`indicator_collections.id` ON DELETE CASCADE, `indicator_id` FK→`indicator_rules.id` ON DELETE CASCADE, `sort_order` default 0, `score` Float nullable, `created_at`; UNIQUE `(collection_id, indicator_id)`) — mirror `DatasourceCollectionItem`.
- [x] 1.4 Add `IndicatorCollectionChange` audit-log model (id, `collection_id` FK→`indicator_collections.id` ON DELETE CASCADE, `indicator_name` String (denormalized), `action` ∈ {add_in, remove_out}, `source` ∈ {manual, cron}, `reason` nullable, `changed_at`) — mirror `EntityCollectionChange`.
- [x] 1.5 Export the new models from `mcp/models/__init__.py` and confirm `Base.metadata.create_all` will pick them up.

## 2. daas-mcp backend — indicator scores (`indicator-scores` capability)

- [x] 2.1 Add guarded `_migrate_indicator_rules_score` to `mcp/daas-mcp/daas_database.py` (check `PRAGMA table_info(indicator_rules)` for `score` before `ALTER TABLE`; mirror `_migrate_sources_score`). Call it on `Database.__init__`.
- [x] 2.2 Extend `create_indicator` in `mcp/daas-mcp/indicator_tools.py` (or `process_database.py` where the impl lives) to accept optional `score`; persist it; include in the returned dict.
- [x] 2.3 Extend `update_indicator` to accept optional `score` (float or null); `score=null` clears to NULL; use a `_UNSET`-style sentinel so "omitted" ≠ "cleared".
- [x] 2.4 Update `get_indicator` / `list_indicators` to return `score` (raw) and `effective_default_score` = `COALESCE(indicator_rules.score, sources.score)` via LEFT JOIN on `sources.name = indicator_rules.datasource`.
- [x] 2.5 Add `set_indicator_score(name, score)` tool: validate indicator exists (else `{"error": "indicator not found"}`); validate `score` is number-or-null (else `{"error": "score must be a number or null"}`); set/clear; return updated dict with `effective_default_score`.
- [x] 2.6 Register `set_indicator_score` in `process_api.py` (and any tool-list wiring in `server.py`).

## 3. daas-mcp backend — indicator collections (`indicator-collections` capability)

- [x] 3.1 Add `IndicatorCollectionService` to `mcp/daas-mcp/registry_service.py` (CRUD: create/list/get/delete; membership: add/remove/list-items/reorder; `set_item_score`; audit: `list_changes`). Mirror `EntityCollectionService`.
- [x] 3.2 Implement `list_indicator_collection_items` with the 3-level `COALESCE(item.score, ir.score, s.score)` resolution via LEFT JOIN on `sources.name = indicator_rules.datasource`; return `score` (resolved) + `item_score` + `indicator_default_score` + `source_default_score` per item, ordered by `sort_order`.
- [x] 3.3 Implement `add_indicator_to_collection` (optional `score`, optional `reason`): validate collection + indicator exist; insert membership row; record `add_in` audit event (`source='manual'`, `indicator_name` denormalized); no-op `already_member` when already present (no event).
- [x] 3.4 Implement `remove_indicator_from_collection` (optional `reason`): delete membership row; record `remove_out` audit event; no-op `not_member` (no event).
- [x] 3.5 Implement `reorder_indicator_collection_items(collection_name, ordered_item_ids)`: validate the list is exactly the current item ids; rewrite `sort_order`.
- [x] 3.6 Implement `set_indicator_collection_item_score(collection_name, indicator_name, score)`: set/clear override; return updated item dict with resolved score; reject unknown collection/indicator/not-in-collection.
- [x] 3.7 Implement `list_indicator_collection_changes(collection_name?, action?, source?, limit?)` newest-first, enriched with collection name.
- [x] 3.8 Create `mcp/daas-mcp/indicator_collection_tools.py` (tool-function wrappers for the 11 tools) and register them in `process_api.py` / `server.py`.

## 4. `collection_writer.py` sidecar

- [x] 4.1 Add `set-indicator-score` subcommand (args `{name, score}`) → calls `IndicatorRuleService`/equivalent to set/clear; prints one JSON line; non-zero exit + `{"error":...}` on failure.
- [x] 4.2 Add `set-indicator-collection-item-score` subcommand (args `{collection_name, indicator_name, score}`) → `IndicatorCollectionService.set_item_score`.
- [x] 4.3 Add `create-indicator-collection` (args `{name, description?}`), `delete-indicator-collection` (args `{name}`), `add-indicator-item` (args `{collection_name, indicator_name, score?, reason?}`), `remove-indicator-item` (args `{collection_name, indicator_name, reason?}`), `reorder-indicator-items` (args `{collection_name, ordered_item_ids}`).
- [x] 4.4 Update the `collection_writer.py` usage/help banner listing the new subcommands.
- [x] 4.5 Verify the writer resolves relative `DAAS_DATABASE_URL` against the repo root (already fixed repo-wide — confirm no regression).

## 5. Backend self-check

- [x] 5.1 Create `mcp/daas-mcp/selfcheck_indicator_scores.py` (temp DB; no network; no LLM): assert `indicator_rules.score` migration is idempotent; assert `create_indicator(score=…)` / `update_indicator(score=null)`; assert `effective_default_score` inherits datasource default; assert `set_indicator_score` set/clear + not-found + bad-type errors.
- [x] 5.2 Add indicator-collection coverage to the same self-check (or a sibling): create/list/get/delete collection; add/remove membership + `already_member`/`not_member` no-ops; reorder (full list) + partial-reorder rejection; per-item `score` override set/clear + 3-level resolution (item→indicator→datasource, all four scenarios); audit log add_in/remove_out + survives indicator deletion; cascade on collection/rule delete.
- [x] 5.3 Run `uv run --directory mcp/daas-mcp python selfcheck_indicator_scores.py` and confirm a clean pass.

## 6. Dashboard — read lib + types

- [x] 6.1 Add `dashboard/src/lib/schema.ts` types: `IndicatorScoreRow` (id, name, datasource, score, datasource_default_score, effective_default_score, …), `IndicatorCollectionSummary`, `IndicatorCollectionScoreItem` (item_id, indicator_name, item_score, indicator_default_score, source_default_score, resolved score, sort_order).
- [x] 6.2 Add `dashboard/src/lib/indicator-scores.ts`: `loadIndicatorScores()` (LEFT JOIN `sources`) for the indicators page; `loadIndicatorCollections()` + `loadIndicatorCollectionScores(name)` (the 3-level COALESCE query) for the collections page — mirror `scores.ts`.

## 7. Dashboard — API routes

- [x] 7.1 Add `dashboard/src/app/api/indicators/score/route.ts` (POST `{name, score}` → spawn `collection_writer.py set-indicator-score`; parse one JSON line; `invalidateDb('daas')` on success; 404 on unknown indicator).
- [x] 7.2 Add `dashboard/src/app/api/indicators/collections/route.ts` (POST create) and `dashboard/src/app/api/indicators/collections/[name]/route.ts` (DELETE).
- [x] 7.3 Add `dashboard/src/app/api/indicators/collections/[name]/items/route.ts` (POST add) and `dashboard/src/app/api/indicators/collections/[name]/items/[indicator]/route.ts` (DELETE remove).
- [x] 7.4 Add `dashboard/src/app/api/indicators/collections/[name]/items/[indicator]/score/route.ts` (POST `{score}` → `set-indicator-collection-item-score`).
- [x] 7.5 Add `dashboard/src/app/api/indicators/collections/[name]/items/reorder/route.ts` (POST `{ordered_item_ids}`) if reorder is exposed in the UI.
- [x] 7.6 Reuse the existing spawn-writer helper used by `/api/scores/*` and `/api/entities/*`; keep routes thin (parse one JSON line, invalidate cache).

## 8. Dashboard — indicators page score column

- [x] 8.1 Update `dashboard/src/app/process/indicators/page.tsx` to LEFT JOIN `sources` and surface `score`, `datasource_default_score`, `effective_default_score` per row.
- [x] 8.2 Add an inline number-input + Save button per row (blank when `score` is NULL); on Save POST `/api/indicators/score`; show a read-only "datasource default" hint cell.
- [x] 8.3 Show the resolved `effective_default_score` next to the raw score so the operator sees what NULL inherits.
- [x] 8.4 Add a "Collections" link/action from `/process/indicators` to `/process/indicators/collections`.

## 9. Dashboard — indicator collections page

- [x] 9.1 Add `/process/indicators/collections/page.tsx` (list): enumerate collections (name, description, item_count) via `loadIndicatorCollections()`; "New collection" action; per-row Open + Delete.
- [x] 9.2 Add `/process/indicators/collections/new/page.tsx` (create form: name + optional description → POST `/api/indicators/collections`).
- [x] 9.3 Add `/process/indicators/collections/[name]/page.tsx` (detail): table of items ordered by `sort_order` with columns [indicator name | inline-editable item score | indicator default (ro) | datasource default (ro) | resolved effective (ro) | Remove]; add-indicator control; reorder control (drag or up/down).
- [x] 9.4 Wire add → `POST .../items`; remove → `DELETE .../items/[indicator]`; reorder → `POST .../items/reorder`; per-item save → `POST .../items/[indicator]/score`.
- [x] 9.5 Add a History panel (filter add_in / remove_out) on the detail page mirroring `/entities/[name]`.
- [x] 9.6 Add a nav entry / breadcrumb so the page is reachable from `/process/indicators` and the main nav.

## 10. Docs, wiring, and verification

- [x] 10.1 Update `CLAUDE.md` (daas-mcp section): document the `indicator_rules.score` column + migration, the `indicator_collections` / `indicator_collection_items` / `indicator_collection_changes` tables, the new tools (12), the `set-indicator-score` / `set-indicator-collection-item-score` + collection writer subcommands, and the self-check command.
- [x] 10.2 Run `uv run --directory mcp/daas-mcp python selfcheck.py` and the existing `selfcheck_scores.py` to confirm no regression on the datasource-score path.
- [x] 10.3 Manually smoke the dashboard: set/clear an indicator score on `/process/indicators`; create an indicator collection; add/remove/reorder items; set/clear a per-item override and confirm the resolved effective score updates (4 resolution scenarios).
- [x] 10.4 Confirm `Base.metadata.create_all` creates the 3 new tables on a fresh `daas.db` and the guarded ALTER adds `indicator_rules.score` on an existing DB without data loss.
- [ ] 10.5 `openspec archive add-indicator-scores` once all tasks complete and the change is validated.
