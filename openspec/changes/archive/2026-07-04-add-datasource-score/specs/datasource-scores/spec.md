# datasource-scores

## ADDED Requirements

### Requirement: Datasource default score column

The system SHALL add a nullable `score` column (REAL / Float) to the `sources` table. A NULL value means "no default score set". The column SHALL default to NULL on existing rows (additive migration, no data loss). `DaasSource.to_dict()` SHALL include the `score` field.

#### Scenario: Existing datasources get a NULL score after migration

- **WHEN** the `sources` table is migrated on an existing `daas.db`
- **THEN** a `score` REAL column exists on `sources` and every pre-existing row has `score = NULL`

#### Scenario: Create a datasource with a score

- **WHEN** `create_datasource(name="edgar", label="SEC EDGAR", score=0.9)` is called
- **THEN** the new `sources` row has `score = 0.9` and the returned dict includes `"score": 0.9`

#### Scenario: Create a datasource without a score

- **WHEN** `create_datasource(name="edinet", label="Japan EDINET")` is called with no `score`
- **THEN** the new row has `score = NULL` and the returned dict includes `"score": null`

### Requirement: Collection item score override column

The system SHALL add a nullable `score` column (REAL / Float) to the `datasource_collection_items` table. A NULL value means "inherit the datasource's default score". The column SHALL default to NULL on existing rows. `DatasourceCollectionItem.to_dict()` SHALL include the `score` field.

#### Scenario: Existing collection items get a NULL score after migration

- **WHEN** the `datasource_collection_items` table is migrated on an existing `daas.db`
- **THEN** a `score` REAL column exists on `datasource_collection_items` and every pre-existing item has `score = NULL`

### Requirement: Effective score resolution

When resolving a datasource's score within a collection, the system SHALL use the collection-item's `score` if it is not NULL; otherwise it SHALL fall back to the datasource's default `score`; otherwise the effective score is NULL. This resolution SHALL be surfaced by `list_collection` for every item.

#### Scenario: Item override wins over datasource default

- **WHEN** a datasource has default `score = 0.5` and its `datasource_collection_items` row in collection "us-disclosure" has `score = 0.9`
- **THEN** `list_collection("us-disclosure")` returns that item with resolved `score = 0.9` and `item_score = 0.9` and `source_default_score = 0.5`

#### Scenario: NULL item score inherits the datasource default

- **WHEN** a datasource has default `score = 0.5` and its collection item has `score = NULL`
- **THEN** `list_collection` returns that item with resolved `score = 0.5`, `item_score = null`, and `source_default_score = 0.5`

#### Scenario: Both NULL resolves to NULL

- **WHEN** a datasource has default `score = NULL` and its collection item has `score = NULL`
- **THEN** `list_collection` returns that item with resolved `score = null`, `item_score = null`, and `source_default_score = null`

### Requirement: Set collection item score tool

The system SHALL expose a `set_collection_item_score` tool that sets or clears the `score` override on an existing `datasource_collection_items` row, identified by `(collection_name, source_name, optional section_name)`. Passing `score = null` SHALL clear the override (set it back to NULL so the datasource default is inherited). The tool SHALL return the updated item dict (including the resolved effective score). The tool SHALL reject unknown collections, unknown sources, unknown sections, and items not present in the collection.

#### Scenario: Set an item score override

- **WHEN** `set_collection_item_score(collection_name="us-disclosure", source_name="edgar", score=0.8)` is called on an existing whole-datasource item
- **THEN** that `datasource_collection_items` row's `score` is set to `0.8` and the returned dict includes `"score": 0.8`

#### Scenario: Clear an item score override

- **WHEN** `set_collection_item_score(collection_name="us-disclosure", source_name="edgar", score=null)` is called on an item whose override was `0.8`
- **THEN** the item's `score` is set back to NULL and the returned dict reports `"score": null` for the override (the effective score falls back to the datasource default)

#### Scenario: Set score on a specific section item

- **WHEN** `set_collection_item_score(collection_name="us-disclosure", source_name="edgar", section_name="Item 1 Business", score=0.7)` is called
- **THEN** the override is set on the matching `(collection, source, section)` item only; other items for the same source in the same collection are unchanged

#### Scenario: Item not in collection

- **WHEN** `set_collection_item_score(collection_name="us-disclosure", source_name="edinet", score=0.5)` is called and edinet is not in the collection
- **THEN** the system returns an error indicating the item was not found in the collection

#### Scenario: Collection not found

- **WHEN** `set_collection_item_score(collection_name="nope", source_name="edgar", score=0.5)` is called and the collection does not exist
- **THEN** the system returns an error indicating the collection was not found

### Requirement: Score column migrations are idempotent

The system SHALL add the `score` column to `sources` and `datasource_collection_items` via guarded `ALTER TABLE ADD COLUMN` migrations that check `PRAGMA table_info` before altering, so they run exactly once and are safe on fresh DBs (where `create_all` already added the column) and on already-migrated DBs.

#### Scenario: Re-running init does not re-alter

- **WHEN** `daas_database.Database` init runs on a DB where `sources.score` and `datasource_collection_items.score` already exist
- **THEN** no `ALTER TABLE` is executed and startup succeeds
