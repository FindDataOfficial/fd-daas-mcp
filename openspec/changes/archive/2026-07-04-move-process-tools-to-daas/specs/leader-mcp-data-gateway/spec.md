## MODIFIED Requirements

### Requirement: Data-fetch MCPs removed from client connection

The 10 data-fetch MCPs — `akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank` — SHALL be removed from `.mcp.json`. `leader-mcp` SHALL remain in `.mcp.json` as the sole client-facing entry point for live data from those MCPs. The MCP server directories and their `server.py` files SHALL remain on disk and launchable by `leader-mcp` via their stored `leader_upstreams` configs. Non-data-fetch MCPs (`leader-mcp`, `cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`) SHALL remain in `.mcp.json`. `process-mcp` is no longer a separate MCP — its tools have been relocated to `daas-mcp` — and SHALL NOT appear in `.mcp.json`.

#### Scenario: .mcp.json after migration
- **WHEN** the migration is complete
- **THEN** `.mcp.json` `mcpServers` does NOT contain `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `akshare`, `ckan`, `cnstats`, or `worldbank`
- **AND** `.mcp.json` `mcpServers` does NOT contain `process-mcp`
- **AND** `.mcp.json` `mcpServers` still contains `leader-mcp`, `cron-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`

#### Scenario: Data-fetch MCP still launchable by leader-mcp
- **WHEN** `call_data_mcp(server="yfinance", tool="list_categories", arguments='{}')` is called after the `.mcp.json` edit
- **THEN** the call succeeds because the `yfinance` launch config is stored in `leader_upstreams`
- **AND** the `yfinance` MCP directory and `server.py` still exist on disk
