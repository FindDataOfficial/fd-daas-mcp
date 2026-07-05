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

### Requirement: Seed migrates launch config idempotently

`seed_upstreams.py` SHALL read every non-`leader-mcp` entry from `.mcp.json` `mcpServers` and upsert it into `leader_upstreams` using the `.mcp.json` key as the upstream `name` (no `-mcp` suffix stripping for the non-data MCPs; the 10 data-fetch MCPs keep their existing short names for back-compat with `ask_data_crew` and the crewai-data-workflow). It SHALL support `--dry-run` (print the planned upserts, write nothing) and `--unseed` (delete the seeded rows from `leader_upstreams` and print the `.mcp.json` snippet to restore direct connection for rollback). It SHALL be safe to run from `uv run --directory mcp/leader-mcp python seed_upstreams.py`. Re-running SHALL update existing rows by name, never duplicate.

#### Scenario: Dry run
- **WHEN** `seed_upstreams.py --dry-run` is run against a `.mcp.json` with 8 entries (1 leader + 7 others)
- **THEN** the script prints the 7 non-leader upstreams it would upsert
- **AND** writes nothing to `daas.db`

#### Scenario: Idempotent seed
- **WHEN** `seed_upstreams.py` is run twice
- **THEN** `leader_upstreams` contains exactly one row per non-leader MCP key
- **AND** the second run updates existing rows rather than inserting duplicates

#### Scenario: Unseed for rollback
- **WHEN** `seed_upstreams.py --unseed` is run
- **THEN** the seeded rows are deleted from `leader_upstreams`
- **AND** the script prints the `.mcp.json` `mcpServers` snippet for all non-leader MCPs so they can be re-added for rollback

#### Scenario: Data-fetch short names preserved
- **WHEN** `seed_upstreams.py` seeds `yfinance-mcp` from `.mcp.json`
- **THEN** the `leader_upstreams` row uses `name="yfinance"` (short name) so existing `ask_data_crew` / crewai-data-workflow lookups continue to resolve
- **AND** seeding `cron-mcp` uses `name="cron-mcp"` (full key, no short-name mapping)

### Requirement: Non-leader MCPs removed from client connection

All MCPs except `leader-mcp` SHALL be removed from `.mcp.json`. This covers both the 10 data-fetch MCPs (`akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank`) AND the 7 non-data MCPs (`cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`). `leader-mcp` SHALL remain in `.mcp.json` as the sole client-facing entry point. The MCP server directories and their `server.py` files SHALL remain on disk and launchable by `leader-mcp` via their stored `leader_upstreams` configs. `process-mcp` is no longer a separate MCP — its tools have been relocated to `daas-mcp` — and SHALL NOT appear in `.mcp.json`.

#### Scenario: .mcp.json after migration
- **WHEN** the migration is complete
- **THEN** `.mcp.json` `mcpServers` contains exactly one key: `leader-mcp`
- **AND** `.mcp.json` `mcpServers` does NOT contain `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `akshare`, `ckan`, `cnstats`, `worldbank`, `cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, or `alerts-mcp`
- **AND** `.mcp.json` `mcpServers` does NOT contain `process-mcp`

#### Scenario: Data-fetch MCP still launchable by leader-mcp
- **WHEN** `call_mcp(server="yfinance", tool="list_categories", arguments='{}')` is called after the `.mcp.json` edit
- **THEN** the call succeeds because the `yfinance` launch config is stored in `leader_upstreams`
- **AND** the `yfinance` MCP directory and `server.py` still exist on disk

#### Scenario: Non-data MCP still launchable by leader-mcp
- **WHEN** `call_mcp(server="cron-mcp", tool="list_jobs", arguments='{}')` is called after the `.mcp.json` edit
- **THEN** the call succeeds because the `cron-mcp` launch config is stored in `leader_upstreams`
- **AND** the `cron-mcp` MCP directory and `server.py` still exist on disk

#### Scenario: Docker-based MCP still launchable by leader-mcp
- **WHEN** `call_mcp(server="scrapling-docker-mcp", tool="scrape", arguments='{"url":"https://example.com"}')` is called and the docker daemon is running
- **THEN** the call succeeds because the `scrapling-docker-mcp` launch config (`command="docker"`, `args=["run","-i","--rm","scrapling-mcp"]`) is stored in `leader_upstreams` and `build_client` already supports arbitrary stdio commands
- **NOTE** the live spawn is gated on the docker daemon being running on the host; the launch config itself is verified correct independent of the daemon

### Requirement: Generic gateway tool aliases

The gateway SHALL expose generic tool names — `list_mcps`, `list_mcp_tools`, `call_mcp`, `add_mcp`, `remove_mcp`, `get_mcp` — that route to any upstream in `leader_upstreams` regardless of "data" vs "non-data" category. Each generic tool SHALL delegate to the same implementation as its `*_data_mcp` counterpart (identical behavior and return shape). The existing `*_data_mcp` tools SHALL remain registered as back-compat aliases so existing callers (`ask_data_crew`, the crewai-data-workflow, the `add-ai-chat` dashboard route) require no changes.

#### Scenario: list_mcps returns all upstreams
- **WHEN** `list_mcps()` is called
- **THEN** it returns the same set of upstreams as `list_data_mcps()` (same rows, same shape)

#### Scenario: call_mcp routes to a non-data upstream
- **WHEN** `call_mcp(server="cron-mcp", tool="list_jobs", arguments='{}')` is called
- **THEN** the result is identical to `call_data_mcp(server="cron-mcp", tool="list_jobs", arguments='{}')` (same delegation path, same return shape)

#### Scenario: add_mcp upserts a non-data upstream
- **WHEN** `add_mcp(name="alerts-mcp", transport="stdio", command="uv", args=["run","--directory",".../alerts-mcp","python","server.py"])` is called
- **THEN** the row is upserted into `leader_upstreams` identically to `add_data_mcp(...)` with the same arguments

#### Scenario: Back-compat alias unchanged
- **WHEN** `call_data_mcp(server="yfinance", tool="list_categories", arguments='{}')` is called after the generic aliases are added
- **THEN** the call behaves exactly as before (no behavior change, no deprecation warning)
- **AND** `ask_data_crew(question="get AAPL 1-month price history")` still resolves to the `yfinance` upstream via the same code path

### Requirement: Composite-mcp proxied-mode reachability

`composite-mcp` SHALL be reachable via `call_mcp(server="composite-mcp", ...)` and `list_mcp_tools(server="composite-mcp")` whether started with or without a `COMPOSITE` env var. When a `COMPOSITE` env var selects a composite that mounts proxied upstreams (e.g. `COMPOSITE=example` → `akshare`), listing composite-mcp's served tools SHALL NOT spawn any proxied upstream at list time — the tool list SHALL be derived from the composite's stored tool selections (DB rows). A proxied upstream SHALL be spawned only when one of its proxied tools is actually called, via a per-call `fastmcp.Client` over the same `build_client` path used by chained tools. Management tools and the `render_stock_summary` UI tool SHALL remain available regardless of the `COMPOSITE` env var.

#### Scenario: composite-mcp management tools route through leader-mcp
- **WHEN** `composite-mcp` is started without a `COMPOSITE` env var
- **AND** `call_mcp(server="composite-mcp", tool="list_composites", arguments='{}')` is called
- **THEN** the call succeeds and returns the composite catalog
- **AND** `list_mcp_tools(server="composite-mcp")` returns the management tools (including `render_stock_summary`)

#### Scenario: composite-mcp proxied mode lists tools through leader-mcp without spawning upstreams
- **WHEN** `composite-mcp` is started with `COMPOSITE=example`
- **AND** `list_mcp_tools(server="composite-mcp")` is called through `leader-mcp`
- **THEN** the call succeeds and returns the composite's management + UI + proxied + chain tool names
- **AND** no proxied upstream subprocess is started during the list call (listing is DB-driven)

#### Scenario: composite-mcp proxied tool call spawns the upstream on demand
- **WHEN** `composite-mcp` is started with `COMPOSITE=example`
- **AND** `call_mcp(server="composite-mcp", tool="akshare_<tool_name>", arguments='{}')` is called through `leader-mcp`
- **THEN** the call spawns the `akshare` upstream via a per-call `fastmcp.Client`
- **AND** returns the same result `call_mcp(server="akshare", tool="<tool_name>", arguments='{}')` would return

