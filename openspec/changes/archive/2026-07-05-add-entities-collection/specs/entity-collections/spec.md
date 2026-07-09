## ADDED Requirements

### Requirement: Entity collection tables

The system SHALL maintain an `entity_collections` table (id, name UNIQUE, description, rule_json nullable, created_at, updated_at), an `entity_collection_items` table representing the **current** membership (id, collection_id FK→`entity_collections.id` CASCADE, entity_id FK→`entities.id` CASCADE, sort_order, added_at, added_reason, UNIQUE(collection_id, entity_id)), and an `entity_collection_changes` table as an append-only audit log (id, collection_id FK→`entity_collections.id` CASCADE, entity_id FK→`entities.id` CASCADE, action ∈ {`add_in`, `remove_out`}, source ∈ {`manual`, `cron`}, reason, changed_at). All three tables SHALL be created via `Base.metadata.create_all` on daas-mcp start (no Alembic).

#### Scenario: Fresh database gets the tables

- **WHEN** daas-mcp starts against a `daas.db` that does not yet have the tables
- **THEN** `entity_collections`, `entity_collection_items`, and `entity_collection_changes` are created by `Base.metadata.create_all`

#### Scenario: Cascade on collection delete

- **WHEN** an entity collection is deleted
- **THEN** all its `entity_collection_items` and `entity_collection_changes` rows are removed by the foreign-key cascade

#### Scenario: Cascade on entity delete

- **WHEN** an entity row is deleted
- **THEN** all its `entity_collection_items` and `entity_collection_changes` rows across every collection are removed by the foreign-key cascade

### Requirement: Create entity collection

The system SHALL expose a `create_entity_collection(name, description=None, rule=None)` daas-mcp tool that creates a named entity collection. `rule` is an optional JSON object string encoding the membership rule (`entity_type`, `exchange`, `country_code`, `codes`, `name_regex`). Collection names SHALL be unique.

#### Scenario: Create a manual collection

- **WHEN** `create_entity_collection(name="a-share-leaders", description="A股强势股")` is called with no `rule`
- **THEN** an `entity_collections` row is created with `rule_json = NULL` and returned with `id`, `name`, `description`, `item_count=0`

#### Scenario: Create a rule-based collection

- **WHEN** `create_entity_collection(name="sse-stocks", rule='{"entity_type":"stock","exchange":"SSE"}')` is called
- **THEN** the collection is created with `rule_json` storing the parsed rule object

#### Scenario: Duplicate name rejected

- **WHEN** `create_entity_collection(name="a-share-leaders")` is called and a collection with that name exists
- **THEN** the system returns `{"success": false, "error": "...already exists..."}` and creates no row

### Requirement: List and get entity collections

The system SHALL expose `list_entity_collections()` returning every collection (`id`, `name`, `description`, `rule`, `item_count`, `created_at`) and `get_entity_collection(name)` returning one collection with its current member entities (each member's `entity_id`, `entity_type`, `code`, `name`, `ticker`, `exchange`, `sort_order`, `added_at`).

#### Scenario: List collections

- **WHEN** `list_entity_collections()` is called against a DB with two collections
- **THEN** the system returns both collections each with a correct `item_count`

#### Scenario: Get a collection with members

- **WHEN** `get_entity_collection(name="a-share-leaders")` is called on a collection with 3 members
- **THEN** the system returns the collection metadata plus a `members` array of 3 entities ordered by `sort_order`

#### Scenario: Get a missing collection

- **WHEN** `get_entity_collection(name="nope")` is called and no such collection exists
- **THEN** the system returns `{"success": false, "error": "collection 'nope' not found"}`

### Requirement: Update and delete entity collection

The system SHALL expose `update_entity_collection(name, new_name=None, description=None, rule=None)` that partially updates an existing collection's `name` and/or `description` and/or `rule`. At least one field SHALL be provided. `new_name` SHALL be rejected if it collides with another collection. The system SHALL expose `delete_entity_collection(name)` that deletes the collection and cascades to its items and changes.

#### Scenario: Update description only

- **WHEN** `update_entity_collection(name="a-share-leaders", description="Updated")` is called
- **THEN** the description is updated, name and rule are unchanged, and members remain intact

#### Scenario: Rename to a free name

- **WHEN** `update_entity_collection(name="a-share-leaders", new_name="cn-leaders")` is called and `cn-leaders` is free
- **THEN** the name is updated and members remain intact

#### Scenario: Rename collision

- **WHEN** `update_entity_collection(name="a-share-leaders", new_name="existing")` is called and `existing` already exists
- **THEN** the system returns an error and does not change either field

#### Scenario: Delete a collection

- **WHEN** `delete_entity_collection(name="a-share-leaders")` is called
- **THEN** the collection row, its `entity_collection_items`, and its `entity_collection_changes` are all removed

### Requirement: Add entity to collection records add-in event

The system SHALL expose `add_entity_to_collection(collection_name, entity_id=None, entity_type=None, code=None, reason=None)` that resolves the entity (by `entity_id`, or by `(entity_type, code)`), adds an `entity_collection_items` row if the entity is not already a member (appended at `sort_order = max(existing)+1`), and appends an `entity_collection_changes` row with `action='add_in'`, `source='manual'`, the given `reason`, and `changed_at=now`. If the entity is already a member, the call SHALL be a no-op that returns the existing membership WITHOUT recording a duplicate `add_in` event.

#### Scenario: Add a member by id

- **WHEN** `add_entity_to_collection(collection_name="a-share-leaders", entity_id=42, reason="manual pick")` is called for a non-member
- **THEN** an `entity_collection_items` row is created, an `entity_collection_changes` row with `action='add_in'`, `source='manual'`, `reason='manual pick'` is appended, and the system returns `{"success": true, "action": "added", ...}`

#### Scenario: Add a member by (entity_type, code)

- **WHEN** `add_entity_to_collection(collection_name="a-share-leaders", entity_type="stock", code="600519")` is called for a non-member
- **THEN** the entity is resolved to its `entity_id` and added as a member with an `add_in` change recorded

#### Scenario: Re-adding an existing member is a no-op

- **WHEN** `add_entity_to_collection(...)` is called for an entity that is already a member
- **THEN** no new membership row is created, no `add_in` change is recorded, and the system returns `{"success": true, "action": "already_member"}`

#### Scenario: Entity not found

- **WHEN** `add_entity_to_collection(entity_type="stock", code="ZZZZZZ")` references an entity that does not exist
- **THEN** the system returns `{"success": false, "error": "entity not found"}`

### Requirement: Remove entity from collection records remove-out event

The system SHALL expose `remove_entity_from_collection(collection_name, entity_id=None, entity_type=None, code=None, reason=None)` that resolves the entity, deletes the `entity_collection_items` row if present, and appends an `entity_collection_changes` row with `action='remove_out'`, `source='manual'`, the given `reason`, and `changed_at=now`. Removing a non-member SHALL be a no-op that returns `{"action": "not_member"}` WITHOUT recording a `remove_out` event.

#### Scenario: Remove a member

- **WHEN** `remove_entity_from_collection(collection_name="a-share-leaders", entity_id=42, reason="delisted")` is called for a current member
- **THEN** the `entity_collection_items` row is deleted, a `remove_out` change is recorded, and the system returns `{"success": true, "action": "removed"}`

#### Scenario: Remove a non-member is a no-op

- **WHEN** `remove_entity_from_collection(...)` is called for an entity that is not a member
- **THEN** no `remove_out` change is recorded and the system returns `{"success": true, "action": "not_member"}`

### Requirement: List and reorder collection members

The system SHALL expose `list_entity_collection_items(collection_name)` returning the current members ordered by `sort_order` (each with full entity detail), and `reorder_entity_collection_items(collection_name, ordered_item_ids)` that rewrites `sort_order` to match the given ordered list of `entity_collection_items.id`. `ordered_item_ids` SHALL contain exactly the item ids currently in the collection.

#### Scenario: List members ordered

- **WHEN** `list_entity_collection_items(collection_name="a-share-leaders")` is called
- **THEN** members are returned in ascending `sort_order`

#### Scenario: Reorder members

- **WHEN** `reorder_entity_collection_items(collection_name="c", ordered_item_ids=[3, 1, 2])` is called on a 3-member collection
- **THEN** subsequent `list_entity_collection_items("c")` returns the members in the order 3, 1, 2

#### Scenario: Reorder rejects unknown ids

- **WHEN** `reorder_entity_collection_items` is called with an item id that does not belong to the named collection
- **THEN** the system returns an error and modifies no rows

### Requirement: Query add-in / remove-out history

The system SHALL expose `list_entity_collection_changes(collection_name=None, entity_id=None, action=None, source=None, limit=100, offset=0)` returning audit-log rows ordered by `changed_at` DESC (newest first), each with `collection_name`, `entity_id`, `entity_code`, `entity_name`, `action`, `source`, `reason`, `changed_at`. Filters SHALL be combinable.

#### Scenario: List all changes for a collection

- **WHEN** `list_entity_collection_changes(collection_name="a-share-leaders")` is called
- **THEN** the system returns every `add_in` and `remove_out` event for that collection, newest first, each enriched with the entity's current code/name

#### Scenario: Filter by action

- **WHEN** `list_entity_collection_changes(collection_name="c", action="add_in")` is called
- **THEN** only `add_in` events are returned

#### Scenario: Filter by entity

- **WHEN** `list_entity_collection_changes(entity_id=42)` is called
- **THEN** only changes involving entity 42 are returned, across all collections

### Requirement: Sync rule-based collection membership

The system SHALL expose a `sync_entity_collection(name)` daas-mcp tool that, for a collection with a non-NULL `rule_json`, re-derives the intended member set by applying the rule filter to the `entities` table, diffs it against the current `entity_collection_items`, performs `add_in` for intended members not currently present, performs `remove_out` for current members not in the intended set, and records every transition as an `entity_collection_changes` row with `source='cron'`. The call SHALL return a summary `{"added": [...], "removed": [...], "unchanged": N}`. For a collection with `rule_json = NULL`, the sync SHALL be a no-op returning `{"action": "manual_collection", "added": [], "removed": [], "unchanged": N}`.

#### Scenario: Sync adds new matches

- **WHEN** `sync_entity_collection(name="sse-stocks")` is called on a rule-based collection `{"entity_type":"stock","exchange":"SSE"}` whose current members are missing two SSE stocks
- **THEN** the two missing stocks are added as members and `add_in` changes with `source='cron'` are recorded, and the summary reports `added` with those two entities

#### Scenario: Sync removes non-matches

- **WHEN** a current member of a rule-based collection no longer matches the rule (e.g. its `exchange` changed)
- **THEN** `sync_entity_collection` removes that member and records a `remove_out` change with `source='cron'`

#### Scenario: Sync a manual collection is a no-op

- **WHEN** `sync_entity_collection(name="a-share-leaders")` is called on a collection with `rule_json = NULL`
- **THEN** no members are added or removed, no changes are recorded, and the summary reports `action: "manual_collection"`

#### Scenario: Sync is idempotent

- **WHEN** `sync_entity_collection(name="sse-stocks")` is called twice in a row with no entity changes between
- **THEN** the second call reports `added: []`, `removed: []`, and records no new changes

### Requirement: Sync CLI branch for cron-mcp

The system SHALL support a `--sync-entity-collection <name>` CLI branch on `mcp/daas-mcp/server.py` that runs `sync_entity_collection(name)` in-process, prints a JSON summary to stdout, and exits without starting the stdio server. This is the entry point invoked by cron-mcp shell tasks.

#### Scenario: CLI branch runs the sync

- **WHEN** `uv run --directory mcp/daas-mcp python server.py --sync-entity-collection sse-stocks` is run
- **THEN** the sync runs against the connected `daas.db`, a JSON summary `{"name":"sse-stocks","added":[...],"removed":[...],"unchanged":N}` is printed, and the process exits 0

#### Scenario: CLI branch on a missing collection

- **WHEN** the CLI branch is invoked for a collection name that does not exist
- **THEN** the process prints `{"error":"collection '<name>' not found"}` and exits non-zero

### Requirement: Idempotent cron registration

The system SHALL provide an `entity_collection_sync.py` script under `mcp/daas-mcp/` with a `--register-cron` flag that idempotently inserts a cron-mcp `Task` (name `entity-collection-sync-<name>`, command `uv run --directory mcp/daas-mcp python server.py --sync-entity-collection <name>`) and a `Schedule` (name `entity-collection-sync-<name>-daily`, daily cron expression, timezone from env) into the shared `tasks`/`schedules` tables, deduplicating on the task/schedule name. The flag SHALL print a reminder that the schedule takes effect on the next cron-mcp start. The script SHALL also support `--sync <name>` (run the sync once, in-process), `--dry-run`, and `--unregister-cron <name>`.

#### Scenario: Register cron for a collection

- **WHEN** `entity_collection_sync.py --register-cron sse-stocks` is run for the first time
- **THEN** a `tasks` row named `entity-collection-sync-sse-stocks` and a `schedules` row named `entity-collection-sync-sse-stocks-daily` are created, and the script prints a reminder to restart cron-mcp

#### Scenario: Idempotent re-registration

- **WHEN** `entity_collection_sync.py --register-cron sse-stocks` is run again
- **THEN** no duplicate rows are created and the script reports the schedule already exists

#### Scenario: Unregister cron

- **WHEN** `entity_collection_sync.py --unregister-cron sse-stocks` is run
- **THEN** the matching `tasks` and `schedules` rows are deleted and the script reports success

#### Scenario: Sync once via the script

- **WHEN** `entity_collection_sync.py --sync sse-stocks` is run
- **THEN** the sync runs in-process and a JSON summary is printed (same shape as the CLI branch)
