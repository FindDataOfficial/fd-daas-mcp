# datasource-collections (delta)

## ADDED Requirements

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
