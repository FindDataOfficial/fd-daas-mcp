## ADDED Requirements

### Requirement: Fetcher calls `akshare-mcp` and persists records to a `scraw_<slug>` table

`mcp/akshare-mcp/fetch_to_store.py` SHALL connect to `akshare-mcp` via `fastmcp.Client` (using the launch command resolved from `.mcp.json`), call its `call_akshare_function` tool with `name` and `params_json`, and write the returned records into the target `scraw_<slug>` table in `mcp/daas.db`.

#### Scenario: Successful fetch creates the table and upserts rows

- **WHEN** `fetch_to_store.py --name stock_zh_a_hist --params '{"symbol":"000001","period":"daily","start_date":"20250101","end_date":"20250131"}' --table scraw_ashare_daily --keys date,symbol` is run
- **THEN** the script connects to `akshare-mcp`, calls `call_akshare_function`, and receives a list of records
- **AND** if `scraw_ashare_daily` does not exist, it is created with columns derived from the records (column names from the akshare field names, types inferred from the first non-null value)
- **AND** a `UNIQUE INDEX` is created on `(date, symbol)` if not already present
- **AND** each record is upserted via `INSERT ... ON CONFLICT(date, symbol) DO UPDATE`
- **AND** the script prints a JSON summary to stdout and exits 0

#### Scenario: Re-run is idempotent

- **WHEN** the same fetch is run a second time with overlapping data
- **THEN** rows matching the upsert keys are updated in place
- **AND** no duplicate rows are inserted
- **AND** the summary reports `rows_upserted` equal to the record count (not doubled)

### Requirement: Fetcher handles schema drift across runs

If `akshare-mcp` returns columns not present in the existing `scraw_<slug>` table, the fetcher SHALL add them; it SHALL NOT drop columns that disappear.

#### Scenario: New column appended on later run

- **WHEN** a later fetch returns a record with a field not in the existing table schema
- **THEN** the fetcher issues `ALTER TABLE scraw_<slug> ADD COLUMN <field> <type>` (type inferred, default NULL) before upserting
- **AND** the upsert succeeds
- **WHEN** a later fetch omits a previously-seen column
- **THEN** that column is left as NULL for new rows and is not dropped

### Requirement: Fetcher reports failures as data, not exceptions

A failed fetch (akshare error, MCP transport error, timeout) SHALL be reported as a JSON summary on stdout with `status="failed"` and a non-zero exit code; the script SHALL NOT raise an unhandled exception.

#### Scenario: akshare-mcp returns an error

- **WHEN** `call_akshare_function` returns an `{"error": ...}` payload or the connection fails
- **THEN** the script prints `{"status":"failed","dataset":...,"table":...,"error":<msg>}` to stdout
- **AND** exits with a non-zero status code
- **AND** no partial upsert is committed

### Requirement: Fetcher CLI and configuration

The fetcher SHALL accept `--name`, `--params`, `--table`, `--keys` (comma-separated) arguments, SHALL resolve the `akshare-mcp` launch command from `.mcp.json` (overridable via `AKSHARE_MCP_COMMAND` env), and SHALL use `DAAS_DATABASE_URL` for the target database.

#### Scenario: Arguments drive the fetch

- **WHEN** the fetcher is invoked with `--name`, `--params`, `--table`, `--keys`
- **THEN** those values override any catalog defaults (the fetcher is usable standalone, without importing the catalog)
- **AND** the `akshare-mcp` subprocess is launched using the command found in `.mcp.json` for the `akshare-mcp` server

#### Scenario: Database target is configurable

- **WHEN** `DAAS_DATABASE_URL` is set in the environment
- **THEN** the fetcher writes to that database
- **WHEN** it is unset
- **THEN** the script exits with a clear error message before any fetch
