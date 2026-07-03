## Why

The project runs many MCP servers (akshare, daas, cron, ckan, worldbank, scrapling, …) each exposing its own tool set. Today there is no way to build a *curated* MCP that exposes a chosen subset of tools drawn from across these servers, nor a way to compose new tools that chain calls across servers. `leader-mcp` already proves the pattern of persisting enable/disable state in `daas.db` (`toggle_datasource`); combine-mcp generalizes that idea from "toggle a datasource" to "curate a composite of tools from multiple upstreams, plus chained tools."

FastMCP 3.4.2 (already in use) provides the proxy/mount primitives (`create_proxy`, `Client`), so combine-mcp is a thin selection + orchestration layer over native composition — not a proxy engine built from scratch.

## What Changes

- New `mcp/combine-mcp/` MCP server (FastMCP, stdio). Serves **one active composite** selected by `COMPOSITE=<name>` env var.
- Management tools (always present): `list_composites`, `create_composite`, `list_upstreams`, `add_upstream`, `remove_upstream`, `list_available_tools`, `add_tool`, `remove_tool`, `list_composite_tools`, `add_chained_tool`, `remove_chained_tool`, `list_chained_tools`.
- Served tools (built from DB at startup): proxied upstream tools (verbatim forward) + chained tools (linear pipeline across upstreams).
- New tables in the shared schema package `mcp/models/`: `composites`, `upstreams`, `composite_tools`, `composite_chains`.
- Selection persisted in `mcp/daas.db`. Multiple composites served by multiple `.mcp.json` entries pointing at the same `server.py` with different `COMPOSITE`.

## Capabilities

### New Capabilities

- `combine-mcp-server`: FastMCP stdio server serving one curated composite plus management tools.
- `composite-selection`: Dynamic, DB-backed curation of which upstream tools a composite exposes.
- `composite-orchestration`: Linear chained tools that call across upstreams, resolving `$prev` references.

### Modified Capabilities

None — entirely new.

## Impact

- New directory: `mcp/combine-mcp/` (~4 files: `server.py`, `combine_database.py`, `combine_tools.py`, `pyproject.toml`).
- New tables in `mcp/models/` (schema changes go here first, per project convention).
- New `.mcp.json` entry (one per composite the user wants served).
- No changes to existing MCP servers — they are connected to as upstreams, not modified.
- New dependency: none beyond `fastmcp>=2.0` (already in use). `Client` and `create_proxy` are part of fastmcp.
