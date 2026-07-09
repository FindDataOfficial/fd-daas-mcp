## ADDED Requirements

### Requirement: Indicator collections tables

The system SHALL add two tables to the shared `mcp/models` `Base`, created in `mcp/daas.db` via `Base.metadata.create_all` (additive, no Alembic, idempotent — mirrors `datasource_collections` / `entity_collections`):

- `indicator_collections`: id, unique `name` (UNIQUE constraint), `description` (nullable), `created_at`, `updated_at`. `IndicatorCollection.to_dict()` SHALL return `{id, name, description, created_at, item_count}`.
- `indicator_collection_items`: id, `collection_id` (FK → `indicator_collections.id`, ON DELETE CASCADE, indexed, NOT NULL), `indicator_id` (FK → `indicator_rules.id`, ON DELETE CASCADE, indexed, NOT NULL), `sort_order` (int, default 0), `score` (REAL, nullable — per-collection override of `indicator_rules.score`), `created_at`. UNIQUE constraint on `(collection_id, indicator_id)`. `IndicatorCollectionItem.to_dict()` SHALL include `score`.

`PRAGMA foreign_keys=ON` is already set per-connection by daas-mcp, so deleting an indicator rule cascades to its membership rows, and deleting a collection cascades to its items.

#### Scenario: Tables are created on first run

- **WHEN** daas-mcp starts against a `daas.db` that lacks `indicator_collections` / `indicator_collection_items`
- **THEN** `Base.metadata.create_all` creates both tables without altering any other table

#### Scenario: Deleting an indicator rule removes its membership rows

- **WHEN** `delete_indicator(name="rsi_5")` is called and rsi_5 is a member of collection "momentum"
- **THEN** the `indicator_rules` row is removed AND its `indicator_collection_items` row(s) are removed by the FK cascade

#### Scenario: Existing collection items get a NULL score after creation

- **WHEN** a new `indicator_collection_items` row is inserted without a `score`
- **THEN** the row has `score = NULL` (inherit the indicator's default score)

### Requirement: Indicator collection CRUD tools

The system SHALL expose `create_indicator_collection(name, description?)`, `list_indicator_collections()`, `get_indicator_collection(name)`, and `delete_indicator_collection(name)`. `create_indicator_collection` SHALL reject a duplicate name. `delete_indicator_collection` SHALL cascade-delete the collection's items (real FK) and SHALL return `{deleted: name}`. Each tool SHALL reject unknown collection names with `{"error": "indicator collection not found"}`.

#### Scenario: Create an indicator collection

- **WHEN** `create_indicator_collection(name="momentum", description="RSI + momentum indicators")` is called
- **THEN** a new `indicator_collections` row is created and `list_indicator_collections` includes it with `item_count: 0`

#### Scenario: Duplicate name is rejected

- **WHEN** `create_indicator_collection(name="momentum")` is called and "momentum" already exists
- **THEN** the tool returns `{"error": "indicator collection already exists"}` and creates nothing

#### Scenario: Delete a collection cascades to items

- **WHEN** `delete_indicator_collection(name="momentum")` is called on a collection with 3 items
- **THEN** the `indicator_collections` row and its 3 `indicator_collection_items` rows are removed

### Requirement: Indicator collection membership tools

The system SHALL expose `add_indicator_to_collection(collection_name, indicator_name, score?, reason?)`, `remove_indicator_from_collection(collection_name, indicator_name, reason?)`, `list_indicator_collection_items(collection_name)`, and `reorder_indicator_collection_items(collection_name, ordered_item_ids)`. `add_indicator_to_collection` SHALL accept an optional `score` to set the per-item override at add time. Adding an indicator already in the collection SHALL be a no-op that returns `action: "already_member"` (no audit event). Removing an indicator not in the collection SHALL be a no-op returning `action: "not_member"` (no audit event). `reorder_indicator_collection_items` SHALL require the full ordered list of existing item ids (partial reorders rejected).

#### Scenario: Add an indicator to a collection

- **WHEN** `add_indicator_to_collection(collection_name="momentum", indicator_name="rsi_5")` is called and rsi_5 is not yet a member
- **THEN** a new `indicator_collection_items` row is created and an `add_in` audit event is recorded

#### Scenario: Add an indicator with a per-item score

- **WHEN** `add_indicator_to_collection(collection_name="momentum", indicator_name="rsi_5", score=0.9)` is called
- **THEN** the new membership row has `score = 0.9`

#### Scenario: Adding an already-member is a no-op

- **WHEN** `add_indicator_to_collection(collection_name="momentum", indicator_name="rsi_5")` is called and rsi_5 is already a member
- **THEN** no row is created, no audit event is recorded, and the tool returns `action: "already_member"`

#### Scenario: Remove an indicator from a collection

- **WHEN** `remove_indicator_from_collection(collection_name="momentum", indicator_name="rsi_5")` is called and rsi_5 is a member
- **THEN** the membership row is removed and a `remove_out` audit event is recorded

#### Scenario: Reorder requires the full item-id list

- **WHEN** `reorder_indicator_collection_items(collection_name="momentum", ordered_item_ids=[3,1,2])` is called with exactly the current item ids
- **THEN** the `sort_order` of each item is rewritten to match the given order

### Requirement: Three-level effective score resolution

When resolving an indicator's score within a collection, the system SHALL use the item's `score` if not NULL; otherwise the indicator rule's `score` if not NULL; otherwise the datasource's default `sources.score`; otherwise NULL. This 3-level resolution (`COALESCE(item.score, indicator_rules.score, sources.score)` via LEFT JOIN on `sources.name = indicator_rules.datasource`) SHALL be surfaced by `list_indicator_collection_items` for every item, alongside the raw `item_score`, `indicator_default_score`, and `source_default_score` for transparency.

#### Scenario: Item override wins over indicator and datasource defaults

- **WHEN** an indicator rule has `score = 0.5`, its datasource has `sources.score = 0.6`, and its `indicator_collection_items` row in collection "momentum" has `score = 0.9`
- **THEN** `list_indicator_collection_items("momentum")` returns that item with resolved `score = 0.9`, `item_score = 0.9`, `indicator_default_score = 0.5`, `source_default_score = 0.6`

#### Scenario: NULL item score inherits the indicator default

- **WHEN** an indicator rule has `score = 0.5`, its datasource has `sources.score = 0.6`, and its collection item has `score = NULL`
- **THEN** the resolved `score = 0.5`, `item_score = null`, `indicator_default_score = 0.5`, `source_default_score = 0.6`

#### Scenario: NULL item and NULL indicator scores inherit the datasource default

- **WHEN** an indicator rule has `score = NULL`, its datasource has `sources.score = 0.6`, and its collection item has `score = NULL`
- **THEN** the resolved `score = 0.6`, `item_score = null`, `indicator_default_score = null`, `source_default_score = 0.6`

#### Scenario: All NULL resolves to NULL

- **WHEN** an indicator rule has `score = NULL`, its datasource has `sources.score = NULL`, and its collection item has `score = NULL`
- **THEN** the resolved `score = null`, `item_score = null`, `indicator_default_score = null`, `source_default_score = null`

### Requirement: Set indicator collection item score tool

The system SHALL expose a `set_indicator_collection_item_score(collection_name, indicator_name, score)` tool that sets the per-item `score` override on an existing `indicator_collection_items` row when `score` is a float, and clears it (sets to NULL → inherits the indicator default) when `score` is `null`. The tool SHALL return the updated item dict (including the resolved effective score and the raw `item_score` / `indicator_default_score` / `source_default_score`). The tool SHALL reject unknown collections, unknown indicators, and items not present in the collection.

#### Scenario: Set a per-item override

- **WHEN** `set_indicator_collection_item_score(collection_name="momentum", indicator_name="rsi_5", score=0.8)` is called
- **THEN** the matching `indicator_collection_items.score` is set to `0.8` and the returned dict includes `item_score = 0.8` and the resolved `score = 0.8`

#### Scenario: Clear a per-item override

- **WHEN** `set_indicator_collection_item_score(collection_name="momentum", indicator_name="rsi_5", score=null)` is called
- **THEN** the item's override is set to NULL and the resolved `score` falls back to the indicator default (or datasource default)

#### Scenario: Item not in collection

- **WHEN** `set_indicator_collection_item_score(collection_name="momentum", indicator_name="sma_20", score=0.7)` is called and sma_20 is not in collection "momentum"
- **THEN** the tool returns `{"error": "indicator not in collection"}` and no row is changed

### Requirement: Indicator collection membership audit log

The system SHALL add an `indicator_collection_changes` table (append-only audit log): id, `collection_id` (FK → `indicator_collections.id` ON DELETE CASCADE), `indicator_name` (denormalized string — survives indicator-rule deletion), `action` ∈ {add_in, remove_out}, `source` ∈ {manual, cron}, `reason` (nullable), `changed_at`. A `list_indicator_collection_changes(collection_name?, action?, source?, limit?)` tool SHALL return the audit log newest-first, each row enriched with the collection name. `add_indicator_to_collection` SHALL record an `add_in` event (source='manual'); `remove_indicator_from_collection` SHALL record a `remove_out` event (source='manual'). No-op add/remove (already_member / not_member) SHALL record no event.

#### Scenario: add records an add_in event

- **WHEN** `add_indicator_to_collection(collection_name="momentum", indicator_name="rsi_5")` is called
- **THEN** an `indicator_collection_changes` row is created with `action="add_in"`, `source="manual"`, `indicator_name="rsi_5"`

#### Scenario: remove records a remove_out event

- **WHEN** `remove_indicator_from_collection(collection_name="momentum", indicator_name="rsi_5")` is called
- **THEN** an `indicator_collection_changes` row is created with `action="remove_out"`, `source="manual"`

#### Scenario: Audit log survives indicator-rule deletion

- **WHEN** an indicator rule that was previously added to collection "momentum" is deleted by `delete_indicator`
- **THEN** the `indicator_collection_changes` row referencing that indicator (by name) remains, because it is not FK-linked to `indicator_rules`
