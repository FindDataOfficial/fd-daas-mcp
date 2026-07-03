## ADDED Requirements

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
The system SHALL expose an `add_to_collection` tool that adds a datasource (optionally a specific section) to a collection.

#### Scenario: Add a whole datasource
- **WHEN** `add_to_collection(collection_name="us-disclosure", source_name="edgar")` is called with no `section_name`
- **THEN** a `datasource_collection_items` row is created with the edgar `source_id` and `section_id = NULL`

#### Scenario: Add a specific section
- **WHEN** `add_to_collection(collection_name="us-disclosure", source_name="edgar", section_name="Item 1 Business")` is called
- **THEN** a collection item is created with both `source_id` and the matching `section_id`

#### Scenario: Duplicate item rejected
- **WHEN** `add_to_collection` is called for a (collection, source, section) combination that already exists
- **THEN** the system returns an error indicating the item is already in the collection

#### Scenario: Section not found under source
- **WHEN** `add_to_collection(..., source_name="edgar", section_name="Nope")` references a section name that does not exist under that source's forms
- **THEN** the system returns an error indicating the section was not found for that datasource

### Requirement: List collection contents
The system SHALL expose a `list_collection` tool that returns all items in a collection, resolving each to its datasource name, form (if any), and section name + instruction (if any).

#### Scenario: List a mixed collection
- **WHEN** `list_collection(collection_name="us-disclosure")` is called on a collection containing one whole datasource and one specific section
- **THEN** the system returns two items: one with `section = null` (whole datasource) and one with the resolved `section_name` and `instruction`

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
