# datasource-management

## Purpose

Tools to create, update, and delete datasources (rows in `sources`), including optional category assignment and cascade deletion of dependent forms, sections, and collection-item references.

## Requirements

### Requirement: Create datasource

The system SHALL expose a `create_datasource` tool that inserts a new row into `sources` with a unique name, label, optional description/url/config, and an optional `category_id`.

#### Scenario: Create a datasource with a category

- **WHEN** `create_datasource(name="edgar", label="SEC EDGAR", category_id=3)` is called
- **THEN** a new `DaasSource` row is created with `name="edgar"`, `label="SEC EDGAR"`, `category_id=3`, `enabled=true`, and the created row (including `id`) is returned

#### Scenario: Create a datasource without a category

- **WHEN** `create_datasource(name="edinet", label="Japan EDINET")` is called with no `category_id`
- **THEN** the datasource is created with `category_id = NULL`

#### Scenario: Duplicate name rejected

- **WHEN** `create_datasource(name="edgar", ...)` is called and a source named "edgar" already exists
- **THEN** the system returns an error and does not create a duplicate

#### Scenario: Nonexistent category rejected

- **WHEN** `create_datasource(..., category_id=999)` references a `category_id` that does not exist
- **THEN** the system returns an error indicating the category was not found

### Requirement: Update datasource

The system SHALL expose an `update_datasource` tool that modifies mutable fields (`label`, `description`, `url`, `config`, `enabled`, `category_id`) of an existing datasource, identified by `name` or `id`.

#### Scenario: Update label and category

- **WHEN** `update_datasource(name="edgar", label="SEC EDGAR Filings", category_id=5)` is called
- **THEN** the datasource's `label` and `category_id` are updated and the updated row is returned

#### Scenario: Move datasource to a different category

- **WHEN** `update_datasource(name="edgar", category_id=7)` is called
- **THEN** only `category_id` changes; other fields are unchanged

#### Scenario: Clear category

- **WHEN** `update_datasource(name="edgar", category_id=null)` is called
- **THEN** the datasource's `category_id` is set to NULL

#### Scenario: Datasource not found

- **WHEN** `update_datasource(name="nope")` references a nonexistent datasource
- **THEN** the system returns an error indicating the datasource was not found

### Requirement: Delete datasource

The system SHALL expose a `delete_datasource` tool that removes a datasource and cascades deletion to its forms, sections, and collection-item references.

#### Scenario: Delete a datasource with dependent rows

- **WHEN** `delete_datasource(name="edgar")` is called on a source that has forms, sections, and collection items
- **THEN** the source row, its `datasource_forms`, their `datasource_sections`, and any `datasource_collection_items` referencing it are all removed

#### Scenario: Delete a datasource not in any collection

- **WHEN** `delete_datasource(name="edinet")` is called on a source with no collection references
- **THEN** only the source and its forms/sections are removed; no error

#### Scenario: Datasource not found

- **WHEN** `delete_datasource(name="nope")` references a nonexistent datasource
- **THEN** the system returns an error indicating the datasource was not found
