## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Data-fetch MCPs removed from client connection
**Reason**: Broadened from "data-fetch MCPs only" to "all non-leader MCPs" by the `leader-mcp-single-entry` change, and renamed to "Non-leader MCPs removed from client connection" (ADDED below). The 7 non-data MCPs (`cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`) now also leave `.mcp.json`.
**Migration**: See the "Non-leader MCPs removed from client connection" requirement (ADDED in the same change). Rollback: `seed_upstreams.py --unseed` prints the `.mcp.json` snippet to restore direct connection for all non-leader MCPs.

## ADDED Requirements

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

### Requirement: Composite-mcp proxied-mode reachability (known limitation)

`composite-mcp` management tools — registered unconditionally in `server.py` — SHALL be reachable via `call_mcp(server="composite-mcp", ...)` when `composite-mcp` is started WITHOUT a `COMPOSITE` env var (management-only mode). When `composite-mcp` is started WITH a `COMPOSITE` env var that selects a composite mounting proxied upstreams (e.g. `COMPOSITE=example`, which proxies `akshare`), `call_mcp` / `list_mcp_tools` against `composite-mcp` SHALL fail with "Connection closed", because listing the composite's served tools spawns the proxied upstream as a nested stdio sub-subprocess (leader-mcp server → composite-mcp subprocess → proxied upstream) that does not complete inside the running leader-mcp server context. This is a known limitation of the single-entry-point gateway for composite-mcp's proxied mode; management-only mode is unaffected. The proxied upstream remains directly reachable via `call_mcp(server="akshare", ...)` as the supported workaround.

#### Scenario: composite-mcp management tools route through leader-mcp
- **WHEN** `composite-mcp` is started without a `COMPOSITE` env var
- **AND** `call_mcp(server="composite-mcp", tool="list_composites", arguments='{}')` is called
- **THEN** the call succeeds and returns the composite catalog
- **AND** `list_mcp_tools(server="composite-mcp")` returns the management tools (including `render_stock_summary`)

#### Scenario: composite-mcp proxied mode fails through leader-mcp (known limitation)
- **WHEN** `composite-mcp` is started with `COMPOSITE=example`
- **AND** `list_mcp_tools(server="composite-mcp")` is called through `leader-mcp`
- **THEN** the call fails with "Connection closed" due to nested stdio spawn in the server context
- **AND** the proxied upstream (`akshare`) remains directly reachable via `call_mcp(server="akshare", tool="list_categories", arguments='{}')`
