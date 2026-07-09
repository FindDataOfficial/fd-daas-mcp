## Why

daas-mcp can already group **datasources** into collections (`datasource_collections`) and link individual **entities** (stocks/countries) to datasources — but there is no way to group *entities themselves* into named, curatable sets. An agent or analyst cannot say "give me everything in my A-share leaders watchlist" or "the Q3 portfolio" as a single addressable object, nor is there any record of *when* an entity entered or left such a set. This blocks watchlist/portfolio-style workflows on top of the entity registry, and it blocks scheduled re-evaluation of membership (e.g. auto-add newly-listed leaders, auto-remove delisted tickers).

## What Changes

- **New `entity_collections` concept in daas-mcp** — named collections of entities (stocks + countries), parallel to `datasource_collections` but keyed on `entities`. Full CRUD: create / list / get / update / delete / rename.
- **Membership management tools** — `add_entity_to_collection` and `remove_entity_from_collection` (by `entity_id` or `(entity_type, code)`), `list_entity_collection_items`, `reorder_entity_collection_items`. Adding/upserts idempotently; removing is by membership row.
- **Add-in / remove-out history table** — every membership transition is recorded in a new `entity_collection_changes` table as an `add_in` or `remove_out` event with `reason`, `source` (`manual` | `cron`), and `changed_at`. `list_entity_collection_changes` queries the audit log (filter by collection / entity / action).
- **Optional membership rule per collection** — a collection MAY carry a `rule_json` filter spec (`entity_type`, `exchange`, `country_code`, `codes`, `name_regex`) that defines its intended member set deterministically from the `entities` table. Manual collections have `rule_json = NULL`.
- **Sync operation + cron registration** — `sync_entity_collection(name)` re-derives the member set for a rule-based collection, diffs against current members, applies `add_in` for new matches and `remove_out` for non-matches, and records every change. `entity_collection_sync.py --register-cron` idempotently registers a cron-mcp `Task` + `Schedule` (mirrors `entity_sync.py --register-cron`) so the sync runs on a schedule. CLI branch `python server.py --sync-entity-collection <name>` runs the sync in-process for cron-mcp shell tasks.
- **Dashboard page** — new `/entities` workspace to create/browse/edit entity collections, add/remove members (with live entity search), view the add-in/remove-out history, and trigger a sync. Writes go through the `collection_writer.py` sidecar (extended with entity-collection subcommands) and `dashboard/src/app/api/entities/*` routes; reads via sql.js.
- **Docs** — `construction/daas-storage.md` and the `CLAUDE.md` daas-mcp section updated to describe the new tables, tools, CLI branch, and cron wiring.

## Capabilities

### New Capabilities
- `entity-collections`: daas-mcp — named collections of entities with membership CRUD, an add-in/remove-out audit-log table, optional rule-based membership, a sync operation, and idempotent cron-mcp registration.
- `entity-collections-dashboard-ui`: Next.js dashboard `/entities` workspace to create/manage entity collections, add/remove members, view history, and trigger syncs.

### Modified Capabilities
<!-- None: the entity-registry and entity-datasource-coverage specs are unchanged;
     entity collections are a new layer on top of the existing entities table. -->

## Impact

- **Schema** (`mcp/models/models.py`): 3 new tables — `entity_collections`, `entity_collection_items`, `entity_collection_changes` — created via `Base.metadata.create_all` (no Alembic). `entity_collection_items.entity_id` and `entity_collection_changes.entity_id` are FK→`entities.id` CASCADE; `collection_id` FK→`entity_collections.id` CASCADE. All read by `Base.metadata.create_all` on daas-mcp start (no migration needed for fresh DBs; existing `daas.db` gets the tables on next start).
- **daas-mcp code**: new `entity_collection_tools.py` (tool wrappers) + `EntityCollectionService` methods on `registry_service.py` (or a sibling service module); `collection_writer.py` extended with entity-collection subcommands; `server.py` registers ~10 new tools + a `--sync-entity-collection` CLI branch; new `entity_collection_sync.py` seeder/cron-registrar + `selfcheck_entity_collections.py`.
- **cron-mcp**: no code change — sync is scheduled via existing `create_task` + `create_schedule` tools, invoked as `uv run --directory mcp/daas-mcp python server.py --sync-entity-collection <name>`.
- **Dashboard**: new `dashboard/src/app/entities/` pages + `dashboard/src/app/api/entities/*` routes + `dashboard/src/lib/entity-collections.ts` (sql.js reads) + `dashboard/src/components/entities/*`; nav entry added; `dashboard/src/lib/schema.ts` extended with entity-collection row types.
- **Docs**: `construction/daas-storage.md`, `CLAUDE.md` (daas-mcp section).
- **No breaking changes** — purely additive. Existing `datasource_collections`, `entities`, and `entity_datasource_links` are untouched.
