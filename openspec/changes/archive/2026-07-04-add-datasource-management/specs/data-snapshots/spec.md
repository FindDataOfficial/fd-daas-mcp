## ADDED Requirements

### Requirement: Data snapshot storage
The system SHALL maintain a `data_snapshots` table in `daas.db` that stores structured row data from function calls, keyed by function and parameters.

#### Scenario: Snapshot table schema
- **WHEN** the database is initialized
- **THEN** the `data_snapshots` table exists with columns: id (INTEGER PK), function_id (FK→functions), params_json (JSON), fetched_at (DATETIME), status (TEXT), data_json (JSON), row_count (INTEGER)
- **AND** a UNIQUE constraint on (function_id, params_json)

#### Scenario: Snapshot status values
- **WHEN** a snapshot is stored
- **THEN** status is one of: "success" (data fetched and stored), "partial" (some rows truncated), "error" (function call failed)

### Requirement: Dashboard shows snapshot data
The dashboard datasource detail page SHALL display stored snapshots for a datasource, with the ability to view the data rows in a table.

#### Scenario: View snapshots for a datasource
- **WHEN** a user navigates to a datasource's detail page
- **THEN** a "Snapshots" section lists all snapshots with fetch time, row count, and status

#### Scenario: View snapshot data rows
- **WHEN** a user clicks on a snapshot
- **THEN** the data rows are displayed in a paginated table (50 rows per page)

#### Scenario: No snapshots for datasource
- **WHEN** a datasource has no snapshots
- **THEN** the Snapshots section shows "No snapshots saved yet"
