## ADDED Requirements

### Requirement: Discover target MCP servers and their tools

cron-mcp SHALL let a caller enumerate the MCP servers it can fetch from (read from the project `.mcp.json`) and list the tools a given server exposes, so a fetch can be targeted without leaving cron-mcp.

#### Scenario: List available MCP servers

- **WHEN** `list_mcp_servers()` is called
- **THEN** the tool returns the set of stdio MCP server names registered in `.mcp.json` (e.g. `daas-mcp`, `yfinance-mcp`, `edgartools-mcp`) with their launch command
- **AND** cron-mcp itself SHALL be excluded from the list

#### Scenario: List a server's tools live

- **WHEN** `list_mcp_tools(source_mcp="daas-mcp")` is called
- **THEN** cron-mcp spawns/connects to that server via `fastmcp.Client` and returns its current tool names
- **AND** returns an error if `source_mcp` is not in `.mcp.json`

### Requirement: Define a reusable data fetch (data job)

The system SHALL persist a named, reusable data fetch definition — `source_mcp`, `tool`, `arguments` — that can be run manually or bound to a schedule.

#### Scenario: Create a data job

- **WHEN** `create_data_job(name="daily_fund_nav", source_mcp="daas-mcp", tool="fetch_data", arguments={"function_name": "worldbank_gdp", "params_json": "{}"})` is called
- **THEN** a `cron_data_jobs` row is persisted with those fields and `enabled=1`
- **AND** the tool returns `{success, job_id, name}`
- **AND** a second create with the same `name` SHALL fail with an error

#### Scenario: List, get, update, delete data jobs

- **WHEN** `list_data_jobs()` is called
- **THEN** all data jobs are returned (id, name, source_mcp, tool, arguments, enabled, timestamps)
- **WHEN** `update_data_job(name, arguments=...)` is called
- **THEN** only the supplied fields are changed and the row is persisted (this prevents a bound schedule from silently breaking when arguments change)
- **WHEN** `delete_data_job(name)` is called
- **THEN** the row is removed and any `schedules.data_job_id` referencing it is set to NULL

### Requirement: Run a one-shot fetch manually

The system SHALL fetch data from another MCP on demand with no prior setup, via `fetch_data_now(source_mcp, tool, arguments)`.

#### Scenario: Ad-hoc fetch stores a result

- **WHEN** `fetch_data_now(source_mcp="yfinance-mcp", tool="call_yfinance_function", arguments={"name": "ticker_history", "params_json": "{\"symbol\":\"AAPL\",\"period\":\"1mo\"}"})` is called
- **THEN** cron-mcp connects to `yfinance-mcp`, calls `call_yfinance_function`, and stores a `cron_fetch_results` row with `job_id=NULL`, the returned data in `data_json`, a `row_count`, and `status="completed"`
- **AND** returns `{status, result_id, row_count, preview}` where `preview` is a truncated view of the data

#### Scenario: Fetch error is recorded, not raised

- **WHEN** a fetch fails (tool not found, target error, or timeout)
- **THEN** a `cron_fetch_results` row is stored with `status="failed"` and `error` set to the message
- **AND** the tool returns `{status: "failed", error}` rather than raising

### Requirement: Run a saved data job manually

The system SHALL run a saved data job on demand via `run_data_job(name)`.

#### Scenario: Run a saved job

- **WHEN** `run_data_job(name="daily_fund_nav")` is called
- **THEN** cron-mcp loads the job, fetches via its `source_mcp`/`tool`/`arguments`, and stores a `cron_fetch_results` row with `job_id` set to the job's id
- **AND** returns `{status, result_id, row_count, preview}`
- **WHEN** `run_data_job(name="missing")` is called for a non-existent job
- **THEN** it returns `{success: false, error}`

### Requirement: Persist and retrieve fetch results

The system SHALL persist every fetch (manual or scheduled) and let results be queried.

#### Scenario: List results

- **WHEN** `list_fetch_results(job_id=None, source_mcp=None, limit=50)` is called
- **THEN** the most recent results are returned (id, job_id, source_mcp, tool, status, row_count, started_at), filtered by `job_id`/`source_mcp` when supplied

#### Scenario: Get a full result

- **WHEN** `get_fetch_result(result_id)` is called
- **THEN** the full row is returned including `data_json`, `arguments`, and `error`

#### Scenario: Result honors a timeout

- **WHEN** a fetch runs longer than the job's `timeout` (default 60s)
- **THEN** the fetch is aborted, the result is stored with `status="failed"` and `error="timeout after Ns"`, and `row_count=0`
