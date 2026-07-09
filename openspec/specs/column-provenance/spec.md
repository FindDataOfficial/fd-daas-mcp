# column-provenance

## Purpose

Track provenance metadata (source_field, unit, semantic_type) for each column of a registered function, so users can understand where a column comes from, what unit it uses, and what kind of value it represents. Exposes tools to read and update this metadata and a dashboard view to display it.

## Requirements

### Requirement: Get column provenance

The system SHALL expose a `get_column_provenance` tool that returns all columns for a function with their provenance fields (source_field, unit, semantic_type).

#### Scenario: Get provenance for a function with metadata

- **WHEN** `get_column_provenance(harness="akshare", command="stock_zh_a_hist")` is called
- **THEN** the system returns each column with name, type, description, source_field, unit, and semantic_type

#### Scenario: Get provenance for a function without metadata

- **WHEN** `get_column_provenance` is called but no provenance fields have been set
- **THEN** the system returns columns with source_field, unit, and semantic_type as null/empty

#### Scenario: Function not found

- **WHEN** `get_column_provenance` references a harness/command that does not exist
- **THEN** the system returns an error message

### Requirement: Update column metadata

The system SHALL expose an `update_column_meta` tool that updates provenance fields on a specific column.

#### Scenario: Update all provenance fields

- **WHEN** `update_column_meta(harness="akshare", command="stock_zh_a_hist", column_name="收盘", source_field="close", unit="CNY", semantic_type="price")` is called
- **THEN** the column's source_field, unit, and semantic_type are updated

#### Scenario: Update a single field

- **WHEN** `update_column_meta(harness="akshare", command="stock_zh_a_hist", column_name="收盘", unit="CNY")` is called
- **THEN** only the unit field is updated; other provenance fields are unchanged

#### Scenario: Column not found

- **WHEN** `update_column_meta` references a column_name that does not exist for the function
- **THEN** the system returns an error message

### Requirement: Dashboard shows column provenance

The dashboard datasource detail page SHALL display source_field, unit, and semantic_type for each column when viewing a datasource's columns.

#### Scenario: View datasource with provenance data

- **WHEN** a user navigates to a datasource's column detail page
- **THEN** the columns table includes Source Field, Unit, and Semantic Type columns alongside the existing Column Name and Type columns

#### Scenario: View datasource without provenance data

- **WHEN** a user navigates to a datasource's column detail page and no provenance fields are set
- **THEN** the provenance columns show as empty, and the page renders normally
