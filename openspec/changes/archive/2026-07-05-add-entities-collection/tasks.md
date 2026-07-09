# Implementation Tasks

## 1. Schema (mcp/models)

- [x] 1.1 Add `EntityCollection` model to `mcp/models/models.py` (`entity_collections`: id, name UNIQUE, description, rule_json nullable, created_at, updated_at; `to_dict()` returns id/name/description/rule/item_count/created_at).
- [x] 1.2 Add `EntityCollectionItem` model (`entity_collection_items`: id, collection_id FK→entity_collections CASCADE, entity_id FK→entities CASCADE, sort_order default 0, added_at, added_reason nullable; UNIQUE(collection_id, entity_id); `to_dict()`).
- [x] 1.3 Add `EntityCollectionChange` model (`entity_collection_changes`: id, collection_id FK→entity_collections CASCADE, entity_id FK→entities CASCADE, action ∈ {add_in, remove_out}, source ∈ {manual, cron}, reason nullable, changed_at; `to_dict()`).
- [x] 1.4 Verify `Base.metadata.create_all` creates the three tables on a fresh temp DB (no Alembic); confirm `PRAGMA foreign_keys=ON` cascade behavior.

## 2. Service layer (daas-mcp)

- [x] 2.1 Add `EntityCollectionService` methods to `registry_service.py` (or a new `entity_collection_service.py` imported by it): `create_entity_collection`, `list_entity_collections`, `get_entity_collection` (with members), `update_entity_collection`, `delete_entity_collection`.
- [x] 2.2 Implement `add_entity_to_collection` (resolve by entity_id OR (entity_type, code); insert membership row if absent + append `add_in`/`source='manual'` change; no-op + `action='already_member'` if present; `entity not found` error if unresolved).
- [x] 2.3 Implement `remove_entity_from_collection` (delete membership row if present + append `remove_out`/`source='manual'` change; no-op + `action='not_member'` if absent).
- [x] 2.4 Implement `list_entity_collection_items` (ordered by sort_order, joined with `entities` for full detail) and `reorder_entity_collection_items` (rewrite sort_order; reject unknown ids; require exactly the current item set).
- [x] 2.5 Implement `list_entity_collection_changes` (filter by collection_name / entity_id / action / source; newest-first; limit+offset; enrich each row with entity code/name).
- [x] 2.6 Implement `sync_entity_collection(name)` — load rule_json (NULL → no-op summary), compute intended set via AND-combined rule filter, diff vs current, apply add_in/remove_out with `source='cron'`, return `{added, removed, unchanged}`. Register a Python-side SQLite `REGEXP` function on the daas engine for `name_regex` (fallback to LIKE if unavailable).

## 3. MCP tools + CLI branch (daas-mcp)

- [x] 3.1 Create `entity_collection_tools.py` with thin wrappers (mirror `entity_tools.py`) for: `create_entity_collection`, `list_entity_collections`, `get_entity_collection`, `update_entity_collection`, `delete_entity_collection`, `add_entity_to_collection`, `remove_entity_from_collection`, `list_entity_collection_items`, `reorder_entity_collection_items`, `list_entity_collection_changes`, `sync_entity_collection`.
- [x] 3.2 Register all 11 tools in `mcp/daas-mcp/server.py` (`app.tool(...)`).
- [x] 3.3 Add `--sync-entity-collection <name>` CLI branch to `server.py` (in-process sync, JSON summary, exit; mirror `--run-rule`).
- [x] 3.4 Extend `mcp/daas-mcp/collection_writer.py` with subcommands: `create-entity-collection`, `update-entity-collection`, `delete-entity-collection`, `add-entity-item`, `remove-entity-item`, `reorder-entity-items`, `sync-entity-collection` (dispatch to the same service methods).

## 4. Cron registration script

- [x] 4.1 Create `mcp/daas-mcp/entity_collection_sync.py` with flags: `--sync <name>` (run sync in-process, print JSON), `--register-cron <name>` (idempotently insert cron-mcp `Task` `entity-collection-sync-<name>` + `Schedule` `entity-collection-sync-<name>-daily`, daily off-minute cron, timezone from env; print restart reminder), `--unregister-cron <name>` (delete the task/schedule rows), `--dry-run`.
- [x] 4.2 Reuse the cron-mcp `tasks`/`schedules` table-insert pattern from `entity_sync.py --register-cron` (deduplicate on names; print "already exists" on re-register).

## 5. Self-check

- [x] 5.1 Create `mcp/daas-mcp/selfcheck_entity_collections.py` (temp DB; no network; no LLM) covering: fresh-DB table creation, cascade on collection delete, cascade on entity delete, create/list/get/update/delete, add/remove with change recording, re-add no-op, remove non-member no-op, reorder + unknown-id rejection, history query + filters, rule-based sync (add/remove/idempotent), manual-collection sync no-op, CLI branch happy path + missing-collection error.
- [x] 5.2 Run `uv run --directory mcp/daas-mcp python selfcheck_entity_collections.py` green.

## 6. Dashboard — API routes

- [x] 6.1 Add `dashboard/src/app/api/entities/route.ts` (GET list via sql.js; POST create via `collection_writer.py create-entity-collection`).
- [x] 6.2 Add `dashboard/src/app/api/entities/[name]/route.ts` (GET detail; PATCH update; DELETE collection).
- [x] 6.3 Add `dashboard/src/app/api/entities/[name]/items/route.ts` (POST add member; DELETE remove member; PATCH reorder).
- [x] 6.4 Add `dashboard/src/app/api/entities/[name]/sync/route.ts` (POST → `collection_writer.py sync-entity-collection`; return added/removed summary).
- [x] 6.5 Add `dashboard/src/app/api/entities/[name]/history/route.ts` (GET → sql.js read of `entity_collection_changes` with action filter).

## 7. Dashboard — pages + components

- [x] 7.1 Add `dashboard/src/lib/entity-collections.ts` (sql.js reads: `loadEntityCollections`, `loadEntityCollectionDetail`, `loadEntityCollectionHistory`; `searchEntitiesForPicker` reusing the existing entity search via daas-mcp tool or sql.js).
- [x] 7.2 Add row types to `dashboard/src/lib/schema.ts` (`EntityCollectionRow`, `EntityCollectionItemRow`, `EntityCollectionChangeRow`).
- [x] 7.3 Add `dashboard/src/app/entities/page.tsx` (list + "New collection" dialog: name, description, optional rule JSON).
- [x] 7.4 Add `dashboard/src/app/entities/[name]/page.tsx` (metadata editor, member table with add/remove, reorder, "Sync now" for rule-based collections, "Delete collection", History panel).
- [x] 7.5 Add `dashboard/src/components/entities/*` (collection-manager, member-picker with live search, history-panel).
- [x] 7.6 Add "Entities" entry to `dashboard/src/components/nav.tsx` linking to `/entities`.

## 8. Docs

- [x] 8.1 Update `construction/daas-storage.md` — add a section on entity collections (3 tables, add-in/remove-out audit log, rule_json, sync, cron registration) cross-linking the `entity-registry` / `entity-datasource-coverage` notes.
- [x] 8.2 Update `CLAUDE.md` `mcp/daas-mcp/` section — list the 11 new entity-collection tools, the `--sync-entity-collection` CLI branch, `entity_collection_sync.py` flags, the self-check command, and the new dashboard `/entities` route + nav entry.
- [x] 8.3 Note in both docs that the feature is additive (no migration, no breaking changes; tables created by `Base.metadata.create_all`).

## 9. Verify end-to-end

- [x] 9.1 Start daas-mcp; confirm the 11 entity-collection tools are listed (`list_data_mcp_tools` via leader-mcp or a direct tool call).
- [x] 9.2 Run the dashboard, create a collection at `/entities`, add members via search, remove one, view history, trigger a sync on a rule-based collection — confirm the audit log records every transition with the right `action`/`source`.
- [x] 9.3 Run `entity_collection_sync.py --register-cron <name>`, confirm the cron-mcp task/schedule rows exist, restart cron-mcp, confirm the schedule loads, and confirm a tick applies add-in/remove-out changes recorded with `source='cron'`.
