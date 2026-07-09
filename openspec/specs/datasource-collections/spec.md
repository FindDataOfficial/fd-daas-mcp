# datasource-collections

## Purpose

Named collections (`datasource_collections`) that group whole datasources or specific datasource-sections via a `datasource_collection_items` join table, with create/add/list/remove tools and automatic cleanup of references on datasource deletion.
## Requirements
### Requirement: Collections group datasources or sections

The system SHALL maintain a `datasource_collections` table (id, name, description) and a `datasource_collection_items` join table where each item references a `source_id` (required) and an optional `section_id` (nullable). A null `section_id` means the whole datasource is in the collection; a non-null `section_id` means a specific section is in the collection.

#### Scenario: Collection holds a whole datasource

- **WHEN** an item is added with `source_id` set and `section_id = NULL`
- **THEN** the collection includes the entire datasource

#### Scenario: Collection holds a specific section

- **WHEN** an item is added with both `source_id` and `section_id` set
- **THEN** the collection includes only that specific datasource-section

### Requirement: Create collection

The system SHALL expose a `create_collection` tool that creates a named collection.

#### Scenario: Create a collection

- **WHEN** `create_collection(name="us-disclosure", description="US securities disclosure sources")` is called
- **THEN** a `datasource_collections` row is created and returned

#### Scenario: Duplicate name rejected

- **WHEN** `create_collection(name="us-disclosure")` is called and a collection with that name exists
- **THEN** the system returns an error and does not create a duplicate

### Requirement: Add item to collection

The system SHALL expose an `add_to_collection` tool that adds a datasource (optionally a specific section) to a collection. An optional `score` (numeric) MAY be supplied to set a per-collection score override on the new item at add time; when omitted the item's `score` is NULL (inherits the datasource default per the resolution rule).

#### Scenario: Add a whole datasource

- **WHEN** `add_to_collection(collection_name="us-disclosure", source_name="edgar")` is called with no `section_name`
- **THEN** a `datasource_collection_items` row is created with the edgar `source_id`, `section_id = NULL`, and `score = NULL`

#### Scenario: Add a specific section

- **WHEN** `add_to_collection(collection_name="us-disclosure", source_name="edgar", section_name="Item 1 Business")` is called
- **THEN** a collection item is created with both `source_id` and the matching `section_id`

#### Scenario: Add with a per-collection score override

- **WHEN** `add_to_collection(collection_name="us-disclosure", source_name="edgar", score=0.8)` is called
- **THEN** the new `datasource_collection_items` row is created with `score = 0.8`

#### Scenario: Duplicate item rejected

- **WHEN** `add_to_collection` is called for a (collection, source, section) combination that already exists
- **THEN** the system returns an error indicating the item is already in the collection

#### Scenario: Section not found under source

- **WHEN** `add_to_collection(..., source_name="edgar", section_name="Nope")` references a section name that does not exist under that source's forms
- **THEN** the system returns an error indicating the section was not found for that datasource

### Requirement: List collection contents

The system SHALL expose a `list_collection` tool that returns all items in a collection, resolving each to its datasource name, form (if any), and section name + instruction (if any). Each item SHALL also include `score` (the resolved effective score — item override if not NULL, else the datasource default, else NULL), `item_score` (the raw per-item override, nullable), and `source_default_score` (the datasource's default score, nullable).

#### Scenario: List a mixed collection

- **WHEN** `list_collection(collection_name="us-disclosure")` is called on a collection containing one whole datasource and one specific section
- **THEN** the system returns two items: one with `section = null` (whole datasource) and one with the resolved `section_name` and `instruction`; each item carries its `score`, `item_score`, and `source_default_score`

#### Scenario: Item with override surfaces the resolved score

- **WHEN** `list_collection` is called on a collection whose edgar item has `score = 0.8` (override) and the edgar datasource default is `0.5`
- **THEN** the edgar item in the result has `score = 0.8`, `item_score = 0.8`, and `source_default_score = 0.5`

#### Scenario: Item without override inherits the default

- **WHEN** `list_collection` is called on a collection whose edgar item has `score = NULL` and the edgar datasource default is `0.5`
- **THEN** the edgar item in the result has `score = 0.5`, `item_score = null`, and `source_default_score = 0.5`

#### Scenario: Empty collection

- **WHEN** `list_collection(collection_name="empty")` is called on a collection with no items
- **THEN** the system returns an empty items list (not an error)

### Requirement: Remove item from collection

The system SHALL expose a `remove_from_collection` tool that removes a single item from a collection by (collection, source, optional section).

#### Scenario: Remove a whole-datasource item

- **WHEN** `remove_from_collection(collection_name="us-disclosure", source_name="edgar")` is called with no section
- **THEN** the collection item with `section_id = NULL` for edgar is removed

#### Scenario: Item not in collection

- **WHEN** `remove_from_collection` references an item not present in the collection
- **THEN** the system returns an error indicating the item was not found in the collection

### Requirement: Deleting a datasource removes its collection items

When a datasource is deleted, any `datasource_collection_items` referencing it SHALL be removed automatically.

#### Scenario: Delete source referenced by a collection

- **WHEN** a datasource that appears in one or more collections is deleted
- **THEN** all collection items referencing that source (and its sections) are removed; no dangling references remain

### Requirement: Rename collection

The system SHALL expose a `rename_collection` tool (and corresponding dashboard API route) that renames an existing collection to a new unique name. The rename SHALL preserve all `datasource_collection_items` rows (they reference by `collection_id`).

#### Scenario: Rename to a free name

- **WHEN** `rename_collection(old_name="us-disclosure", new_name="us-securities")` is called and no other collection uses `us-securities`
- **THEN** the collection's `name` is updated and its items remain intact

#### Scenario: Rename collides

- **WHEN** `rename_collection(old_name="us-disclosure", new_name="japan-disclosure")` is called and a `japan-disclosure` collection already exists
- **THEN** the system returns an error and does not change the existing collection

#### Scenario: Rename a missing collection

- **WHEN** `rename_collection(old_name="nope", new_name="x")` is called and `nope` does not exist
- **THEN** the system returns a "collection not found" error

### Requirement: Reorder collection items

The `datasource_collection_items` table SHALL carry a `sort_order` integer column, and the system SHALL expose a `reorder_collection_items` tool (and dashboard API route) that accepts an ordered list of item identifiers (or `(source, section)` pairs) for a given collection and rewrites their `sort_order` accordingly. `list_collection` SHALL return items in ascending `sort_order`.

#### Scenario: Reorder existing items

- **WHEN** `reorder_collection_items(collection_name="us-disclosure", order=[item_b_id, item_a_id, item_c_id])` is called on a 3-item collection
- **THEN** subsequent `list_collection("us-disclosure")` returns the items in the order B, A, C

#### Scenario: New items get appended sort_order

- **WHEN** `add_to_collection` adds a new item to a collection that already has N items
- **THEN** the new item is assigned `sort_order = max(existing) + 1` so it appears at the end of `list_collection`

#### Scenario: Reorder rejects unknown items

- **WHEN** `reorder_collection_items` is called with an item id that does not belong to the named collection
- **THEN** the system returns an error and does not modify any rows

### Requirement: Edit collection metadata

The system SHALL expose an `update_collection` tool that partially updates an existing collection's `name` and/or `description` in a single call. The caller SHALL provide at least one of `new_name` or `description`; any field that is omitted SHALL be left unchanged. When `new_name` is provided and differs from the collection's current name, the system SHALL enforce that the new name is not already used by another collection. The update SHALL preserve all `datasource_collection_items` rows for the collection (they reference by `collection_id`, not by name). The system SHALL raise a "collection not found" error when the target collection does not exist.

#### Scenario: Update description only
- **WHEN** `update_collection(name="us-disclosure", description="Updated description")` is called and `us-disclosure` exists
- **THEN** the collection's `description` is updated, its `name` is unchanged, and its items remain intact

#### Scenario: Update name only
- **WHEN** `update_collection(name="us-disclosure", new_name="us-securities")` is called and no other collection uses `us-securities`
- **THEN** the collection's `name` is updated, `description` is unchanged, and its items remain intact

#### Scenario: Update both name and description in one call
- **WHEN** `update_collection(name="us-disclosure", new_name="us-securities", description="US securities sources")` is called and `us-securities` is free
- **THEN** both fields are updated in a single call and the collection's items remain intact

#### Scenario: Name collision on update
- **WHEN** `update_collection(name="us-disclosure", new_name="japan-disclosure")` is called and a `japan-disclosure` collection already exists
- **THEN** the system returns an error and does not change either field

#### Scenario: Collection not found
- **WHEN** `update_collection(name="nope", description="x")` is called and `nope` does not exist
- **THEN** the system returns a "collection not found" error

#### Scenario: No fields provided
- **WHEN** `update_collection(name="us-disclosure")` is called with neither `new_name` nor `description`
- **THEN** the system returns an error indicating at least one field to update is required

#### Scenario: Rename to the same name is a no-op for the name field
- **WHEN** `update_collection(name="us-disclosure", new_name="us-disclosure", description="new")` is called
- **THEN** the uniqueness check is skipped (name unchanged), the description is updated, and the call succeeds

