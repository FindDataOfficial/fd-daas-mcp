# datasource-management

## Purpose

Tools to create, update, and delete datasources (rows in `sources`), including optional category assignment and cascade deletion of dependent forms, sections, and collection-item references.

## Requirements

### Requirement: Create datasource

The system SHALL expose a `create_datasource` tool that inserts a new row into `sources` with a unique name, label, optional description/url/config, an optional `category_id`, and an optional `score` (numeric, default NULL — no default score set). The created row (including `id` and `score`) SHALL be returned.

#### Scenario: Create a datasource with a category

- **WHEN** `create_datasource(name="edgar", label="SEC EDGAR", category_id=3)` is called
- **THEN** a new `DaasSource` row is created with `name="edgar"`, `label="SEC EDGAR"`, `category_id=3`, `enabled=true`, `score=NULL`, and the created row (including `id`) is returned

#### Scenario: Create a datasource without a category

- **WHEN** `create_datasource(name="edinet", label="Japan EDINET")` is called with no `category_id`
- **THEN** the datasource is created with `category_id = NULL`

#### Scenario: Create a datasource with a score

- **WHEN** `create_datasource(name="edgar", label="SEC EDGAR", score=0.9)` is called
- **THEN** the new row has `score = 0.9` and the returned dict includes `"score": 0.9`

#### Scenario: Duplicate name rejected

- **WHEN** `create_datasource(name="edgar", ...)` is called and a source named "edgar" already exists
- **THEN** the system returns an error and does not create a duplicate

#### Scenario: Nonexistent category rejected

- **WHEN** `create_datasource(..., category_id=999)` references a `category_id` that does not exist
- **THEN** the system returns an error indicating the category was not found

### Requirement: Update datasource

The system SHALL expose an `update_datasource` tool that modifies mutable fields (`label`, `description`, `url`, `config`, `enabled`, `category_id`, `score`) of an existing datasource, identified by `name` or `id`. Passing `clear_score=true` SHALL set `score` back to NULL. Only supplied fields are changed; omitted fields are left unchanged.

#### Scenario: Update label and category

- **WHEN** `update_datasource(name="edgar", label="SEC EDGAR Filings", category_id=5)` is called
- **THEN** the datasource's `label` and `category_id` are updated and the updated row is returned

#### Scenario: Move datasource to a different category

- **WHEN** `update_datasource(name="edgar", category_id=7)` is called
- **THEN** only `category_id` changes; other fields are unchanged

#### Scenario: Clear category

- **WHEN** `update_datasource(name="edgar", category_id=null)` is called
- **THEN** the datasource's `category_id` is set to NULL

#### Scenario: Update the default score

- **WHEN** `update_datasource(name="edgar", score=0.85)` is called
- **THEN** the datasource's `score` is set to `0.85` and the updated row (including `"score": 0.85`) is returned

#### Scenario: Clear the default score

- **WHEN** `update_datasource(name="edgar", clear_score=true)` is called
- **THEN** the datasource's `score` is set to NULL and the updated row reports `"score": null`

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

### Requirement: List datasources

The system SHALL expose a `list_datasources` tool that returns all functions where `is_datasource = true`, grouped by harness, with enabled status and last_fetched_at timestamp.

#### Scenario: List all datasources

- **WHEN** `list_datasources` is called with no arguments
- **THEN** the system returns a list of all functions marked as datasources, showing harness, command, category, enabled status, and last_fetched_at (or "never" if null)

#### Scenario: List datasources for a specific harness

- **WHEN** `list_datasources(harness="akshare")` is called
- **THEN** the system returns only datasources belonging to the akshare harness

#### Scenario: No datasources configured

- **WHEN** `list_datasources` is called but no functions have `is_datasource = true`
- **THEN** the system returns a message indicating no datasources are configured

### Requirement: Toggle datasource

The system SHALL expose a `toggle_datasource` tool that marks a function as a datasource and sets its enabled state.

#### Scenario: Enable a function as datasource

- **WHEN** `toggle_datasource(harness="akshare", command="stock_zh_a_hist", enabled=true)` is called
- **THEN** the function's `is_datasource` is set to true and `enabled` is set to true

#### Scenario: Disable a datasource

- **WHEN** `toggle_datasource(harness="akshare", command="stock_zh_a_hist", enabled=false)` is called
- **THEN** the function's `is_datasource` remains true but `enabled` is set to false

#### Scenario: Unmark a datasource

- **WHEN** `toggle_datasource(harness="akshare", command="stock_zh_a_hist", is_datasource=false)` is called
- **THEN** the function's `is_datasource` is set to false

#### Scenario: Function not found

- **WHEN** `toggle_datasource` references a harness/command that does not exist
- **THEN** the system returns an error message indicating the function was not found

### Requirement: Save data snapshot

The system SHALL expose a `save_snapshot` tool that calls a data function, parses the result into structured rows, and stores them in the `data_snapshots` table.

#### Scenario: Save a snapshot successfully

- **WHEN** `save_snapshot(harness="akshare", command="stock_zh_a_hist", params={"symbol":"000001","start_date":"20250101"})` is called
- **THEN** the system calls the function, converts the result to JSON rows, stores them in `data_snapshots` with status "success", and updates `last_fetched_at` on the function

#### Scenario: Upsert existing snapshot

- **WHEN** `save_snapshot` is called with the same function and params as an existing snapshot
- **THEN** the existing snapshot is updated with new data (not duplicated)

#### Scenario: Function call fails

- **WHEN** `save_snapshot` is called but the underlying function raises an error
- **THEN** a snapshot is stored with status "error" and the error message in `data_json`

#### Scenario: Too many rows

- **WHEN** `save_snapshot` would produce more than 10000 rows
- **THEN** the system returns an error and does not store the snapshot

### Requirement: List snapshots

The system SHALL expose a `list_snapshots` tool that lists all stored snapshots with metadata (function, row count, status, fetch time).

#### Scenario: List all snapshots

- **WHEN** `list_snapshots` is called
- **THEN** the system returns all snapshots with function name, row count, status, and fetched_at

#### Scenario: List snapshots for a specific function

- **WHEN** `list_snapshots(harness="akshare", command="stock_zh_a_hist")` is called
- **THEN** the system returns only snapshots for that function

#### Scenario: No snapshots exist

- **WHEN** `list_snapshots` is called but no snapshots have been saved
- **THEN** the system returns a message indicating no snapshots exist

### Requirement: Query snapshot data

The system SHALL expose a `query_snapshots` tool that returns the stored row data for a specific snapshot.

#### Scenario: Query snapshot rows

- **WHEN** `query_snapshots(snapshot_id=1, limit=50, offset=0)` is called
- **THEN** the system returns the `data_json` rows for that snapshot, paginated

#### Scenario: Snapshot not found

- **WHEN** `query_snapshots` references a snapshot_id that does not exist
- **THEN** the system returns an error message
