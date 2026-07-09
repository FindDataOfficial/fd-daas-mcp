## ADDED Requirements

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
