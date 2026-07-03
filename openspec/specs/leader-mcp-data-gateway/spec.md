# leader-mcp-data-gateway Specification

## Purpose
TBD - created by archiving change leader-mcp-data-gateway. Update Purpose after archive.
## Requirements
### Requirement: Upstream registry persisted in daas.db

The system SHALL store each data-fetch MCP's launch config in a `leader_upstreams` table in `mcp/daas.db` with columns: `name` (unique), `transport` (`stdio`), `command`, `args_json`, `env_json` (nullable), `cwd` (nullable), `enabled`, `description` (nullable). The table SHALL be created via `Base.metadata.create_all` (no Alembic). Management tools `add_data_mcp`, `remove_data_mcp`, `get_data_mcp`, and `list_data_mcps` SHALL provide CRUD over the registry. `list_data_mcps` SHALL return only `enabled=1` upstreams by default.

#### Scenario: Add and list an upstream
- **WHEN** `add_data_mcp(name="yfinance", transport="stdio", command="uv", args=["run","--directory",".../yfinance-mcp","python","server.py"])` is called
- **THEN** a row exists in `leader_upstreams` with those fields and `enabled=1`
- **AND** `list_data_mcps()` returns an entry for `yfinance`

#### Scenario: Disable an upstream without deleting
- **WHEN** `add_data_mcp(name="yfinance", ..., enabled=False)` is called for an existing name
- **THEN** the row's `enabled` becomes `0`
- **AND** `list_data_mcps()` (default) does NOT return `yfinance`
- **AND** `list_data_mcps(include_disabled=True)` DOES return `yfinance`

#### Scenario: Remove an upstream
- **WHEN** `remove_data_mcp(name="yfinance")` is called
- **THEN** the `yfinance` row is deleted from `leader_upstreams`
- **AND** `list_data_mcps(include_disabled=True)` does NOT return `yfinance`

### Requirement: Live upstream tool discovery

`list_data_mcp_tools(server)` SHALL connect to the named upstream via `fastmcp.Client` over a stdio transport built from that upstream's `leader_upstreams` row, list the upstream's tools, and return each tool's name and description. The client SHALL be opened per call and closed on completion (no leaked subprocess). It SHALL return a clear error if the upstream is unknown, disabled, or fails to start.

#### Scenario: List tools for a known enabled upstream
- **WHEN** `list_data_mcp_tools(server="yfinance")` is called and `yfinance` is enabled
- **THEN** the system starts the `yfinance` MCP via its stored stdio config
- **AND** returns a list including `search_functions`, `call_yfinance_function`, etc.
- **AND** the spawned subprocess is terminated after the call

#### Scenario: Unknown upstream
- **WHEN** `list_data_mcp_tools(server="nope")` is called
- **THEN** the system returns `{"error": "upstream 'nope' not found"}` without launching any subprocess

#### Scenario: Disabled upstream
- **WHEN** `list_data_mcp_tools(server="yfinance")` is called and `yfinance` has `enabled=0`
- **THEN** the system returns `{"error": "upstream 'yfinance' is disabled"}` without launching any subprocess

### Requirement: Direct cross-MCP data call

`call_data_mcp(server, tool, arguments)` SHALL connect to the named upstream via `fastmcp.Client`, invoke the named tool with the JSON-deserialized `arguments`, and return the upstream's result. The client SHALL be opened per call inside `async with client:` so the subprocess is torn down on success or error. It SHALL return a clear error for unknown/disabled upstream, unknown tool, or invalid JSON arguments.

#### Scenario: Call a known tool with valid arguments
- **WHEN** `call_data_mcp(server="edgartools", tool="get_company", arguments='{"ticker_or_cik":"AAPL"}')` is called
- **THEN** the system connects to the `edgartools` upstream, calls `get_company` with those arguments
- **AND** returns the same JSON result the `edgartools` MCP would return directly
- **AND** terminates the subprocess after the call

#### Scenario: Call a registry-based upstream's dispatch tool
- **WHEN** `call_data_mcp(server="yfinance", tool="call_yfinance_function", arguments='{"name":"ticker_history","params_json":"{\"symbol\":\"AAPL\",\"period\":\"1mo\"}"}')` is called
- **THEN** the system connects to the `yfinance` upstream, calls its `call_yfinance_function` dispatch tool with those arguments
- **AND** returns the price-history data the `yfinance` MCP would return for `ticker_history(symbol=AAPL, period=1mo)`
- **AND** terminates the subprocess after the call

#### Scenario: Invalid arguments JSON
- **WHEN** `call_data_mcp(server="yfinance", tool="ticker_history", arguments='{not json}')` is called
- **THEN** the system returns `{"error": "Invalid arguments JSON: ..."}` without launching the upstream

#### Scenario: Unknown tool on a running upstream
- **WHEN** `call_data_mcp(server="yfinance", tool="no_such_tool", arguments='{}')` is called
- **THEN** the system returns an error indicating the tool was not found on the upstream
- **AND** terminates the subprocess after the call

### Requirement: CrewAI agent manages data access

`ask_data_crew(question)` SHALL route a natural-language data request to the right upstream tool and return the fetched data. It SHALL use a CrewAI crew (Manager + DataFetcher agents) that uses the existing registry tools (`search_functions`, `get_function_detail`, `list_harnesses`, `list_data_mcps`) to map the question to a `(server, tool, arguments)` triple, then calls `call_data_mcp`. When CrewAI is unavailable (import error or runtime error), it MUST fall back to a deterministic direct router that performs the same mapping via keyword/registry lookup and terminates in `call_data_mcp`. Both paths SHALL return the upstream's raw result.

#### Scenario: CrewAI available — natural-language fetch
- **WHEN** `ask_data_crew(question="get AAPL 1-month price history")` is called and `crewai` imports successfully
- **THEN** the CrewAI crew resolves the request to the `yfinance` upstream (routing through its `call_yfinance_function` dispatch tool, function `ticker_history`)
- **AND** returns the AAPL 1-month price-history data (the same payload `call_data_mcp("yfinance","call_yfinance_function",'{"name":"ticker_history","params_json":"{\"symbol\":\"AAPL\",\"period\":\"1mo\"}"}')` would return)

#### Scenario: CrewAI unavailable — fallback router
- **WHEN** `ask_data_crew(question="get AAPL 1-month price history")` is called and `crewai` raises `ImportError`
- **THEN** the system logs the fallback and uses the deterministic direct router
- **AND** still returns the fetched data via `call_data_mcp`
- **AND** does NOT raise

#### Scenario: Router cannot resolve a target
- **WHEN** `ask_data_crew(question="something no upstream can serve")` is called and no upstream+tool matches
- **THEN** the system returns a clear error listing the available upstreams
- **AND** does NOT call any upstream

### Requirement: Data-fetch MCPs removed from client connection

The 10 data-fetch MCPs — `akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank` — SHALL be removed from `.mcp.json`. `leader-mcp` SHALL remain in `.mcp.json` as the sole client-facing entry point for live data from those MCPs. The MCP server directories and their `server.py` files SHALL remain on disk and launchable by `leader-mcp` via their stored `leader_upstreams` configs. Non-data-fetch MCPs (`leader-mcp`, `cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `combine-mcp`, `process-mcp`) SHALL remain in `.mcp.json`.

#### Scenario: .mcp.json after migration
- **WHEN** the migration is complete
- **THEN** `.mcp.json` `mcpServers` does NOT contain `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `akshare`, `ckan`, `cnstats`, or `worldbank`
- **AND** `.mcp.json` `mcpServers` still contains `leader-mcp`, `cron-mcp`, `daas-mcp`, `dashboard-mcp`, `combine-mcp`, `process-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`

#### Scenario: Data-fetch MCP still launchable by leader-mcp
- **WHEN** `call_data_mcp(server="yfinance", tool="list_categories", arguments='{}')` is called after the `.mcp.json` edit
- **THEN** the call succeeds because the `yfinance` launch config is stored in `leader_upstreams`
- **AND** the `yfinance` MCP directory and `server.py` still exist on disk

### Requirement: Seed migrates launch config idempotently

`seed_upstreams.py` SHALL read the 10 data-fetch MCP entries from `.mcp.json` and upsert them into `leader_upstreams` (re-running updates existing rows, never duplicates by name). It SHALL support `--dry-run` (print the planned upserts, write nothing) and `--unseed` (delete the seeded rows from `leader_upstreams` and print the `.mcp.json` snippet to restore direct connection for rollback). It SHALL be safe to run from `uv run --directory mcp/leader-mcp python seed_upstreams.py`.

#### Scenario: Dry run
- **WHEN** `seed_upstreams.py --dry-run` is run
- **THEN** the script prints the 10 upstreams it would upsert
- **AND** writes nothing to `daas.db`

#### Scenario: Idempotent seed
- **WHEN** `seed_upstreams.py` is run twice
- **THEN** `leader_upstreams` contains exactly one row per data-fetch MCP (10 rows total)
- **AND** the second run updates existing rows rather than inserting duplicates

#### Scenario: Unseed for rollback
- **WHEN** `seed_upstreams.py --unseed` is run
- **THEN** the 10 seeded rows are deleted from `leader_upstreams`
- **AND** the script prints the `.mcp.json` `mcpServers` snippet for the 10 data-fetch MCPs so they can be re-added for rollback

