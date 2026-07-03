## Why

Claude Code and the dashboard connect **directly** to ~10 data-fetch MCPs (yfinance, edgartools, edinet, dartlab, cnreport, hkreport, akshare, ckan, cnstats, worldbank) via `.mcp.json`. This flattens ~60+ live-data tools into the client's tool surface, forces the client (or user) to know which server + tool serves each request, and spawns a separate stdio process per server at client startup. `leader-mcp` already orchestrates registry **metadata** across harnesses but stops short of live data. Consolidating live data access behind `leader-mcp` — with a CrewAI agent that routes data requests to the right upstream via `fastmcp.Client` — shrinks the client-facing tool surface to a handful of gateway tools, centralizes data access in one place, and lets the data-fetch MCPs be removed from `.mcp.json`. The cross-MCP call primitive (`fastmcp.Client` over a stdio transport built from a server config) is already proven by `combine-mcp` and the in-flight `add-cron-mcp-data-fetch` change, so this is a new gateway over an existing primitive, not new infrastructure.

## What Changes

- **New**: `leader-mcp` becomes the single gateway for live data fetching from the project's data-fetch MCPs, using `fastmcp.Client` over stdio (same pattern as `combine-mcp.combine_database.build_client`).
- **New**: a CrewAI `DataCrew` agent in `leader-mcp` that manages access — it takes a natural-language data request, uses the existing registry tools (`search_functions`, `get_function_detail`, `list_harnesses`) to discover which upstream serves it, then calls the upstream tool and returns the result.
- **New**: an upstream registry stored in `mcp/daas.db` (new `leader_upstreams` table) holding the stdio launch config (command/args/env/cwd) for each data-fetch MCP, seeded from the current `.mcp.json` entries — so removing them from `.mcp.json` does not lose their launch config.
- **New gateway tools** exposed by `leader-mcp`: `list_data_mcps`, `list_data_mcp_tools(server)`, `call_data_mcp(server, tool, arguments)`, `ask_data_crew(question)`.
- **New management tools**: `add_data_mcp`, `remove_data_mcp`, `get_data_mcp` (curate the upstream registry).
- **BREAKING**: remove the 10 data-fetch MCPs (akshare, yfinance, edgartools, edinet, dartlab, cnreport, hkreport, ckan, cnstats, worldbank) from `.mcp.json`. Clients that previously called them directly must route through `leader-mcp`. The MCP servers themselves are **not** deleted — they are launched on demand by `leader-mcp` as stdio subprocesses.
- **New optional dependency**: `crewai` added to `mcp/leader-mcp/pyproject.toml`. The gateway falls back to a deterministic direct router when CrewAI is unavailable (mirroring the existing `LeaderCrew` fallback in `leader_crew.py`). CrewAI requires Python <3.14; `leader-mcp` is on 3.11+ (compatible).

## Capabilities

### New Capabilities

- `leader-mcp-data-gateway`: `leader-mcp` routes live data requests to the project's data-fetch MCPs via `fastmcp.Client` stdio clients, with a CrewAI agent managing access and a daas.db-backed upstream registry; the data-fetch MCPs are removed from `.mcp.json`.

### Modified Capabilities

None — the data-fetch MCPs' own specs (`yfinance-mcp-server`, `edgar-mcp-server`, `edinet-mcp-server`, `dartlab-mcp-server`, `hkreport-mcp-server`, `cnreport-company-api`, …) are unchanged. They are called as clients, not modified, and still run identically when launched directly.

## Impact

- `mcp/leader-mcp/`: new `gateway_tools.py` (FastMCP client calls + gateway/management tools), new `data_crew.py` (CrewAI `DataCrew` + direct-router fallback), new `gateway_database.py` (`leader_upstreams` table + CRUD), extend `server.py` (register new tools), update `pyproject.toml` (`+crewai` optional dep, `+gateway_tools`/`data_crew`/`gateway_database` py-modules), new `seed_upstreams.py` (migrate `.mcp.json` data-fetch entries → `leader_upstreams`, idempotent, `--dry-run`/`--unseed`).
- `mcp/models/models.py`: +1 table (`LeaderUpstream`: name, transport, command, args_json, env_json, cwd, enabled, description).
- `.mcp.json`: remove the 10 data-fetch MCP entries (akshare, yfinance, edgartools, edinet, dartlab, cnreport, hkreport, ckan, cnstats, worldbank). Keep `leader-mcp`, `cron-mcp`, `scrapling-*-mcp`, `daas-mcp`, `dashboard-mcp`, `combine-mcp`, `process-mcp`.
- `mcp/daas.db`: new `leader_upstreams` table auto-created via `Base.metadata.create_all` (no Alembic).
- New dependency: `crewai` in the `leader-mcp` venv (`uv pip install -e ".[crew]"` or default). Note `leader_crew.py` already imports `crewai` lazily and falls back — the new `data_crew.py` reuses the same pattern.
- No changes to the data-fetch MCP servers, the dashboard, or other MCPs. No new DB tables touched by data-fetch MCPs (they remain live-execution-only / registry-only as before).
