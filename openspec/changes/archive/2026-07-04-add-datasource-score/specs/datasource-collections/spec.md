# datasource-collections

## MODIFIED Requirements

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
