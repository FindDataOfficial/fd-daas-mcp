## Why

`.mcp.json` today exposes 8 MCP servers directly to the client. `leader-mcp` already proved the gateway pattern for the 10 data-fetch MCPs (via `leader_upstreams` + `fastmcp.Client`), but 7 non-data MCPs (`cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`) still sit in `.mcp.json` as direct client entries. Consolidating to a single client-facing entry point removes duplicated launch config, centralizes upstream lifecycle, and makes `leader-mcp` the uniform access layer for every MCP in the project.

## What Changes

- Extend `leader_upstreams` seeding to cover all 7 non-leader MCPs currently in `.mcp.json` (`cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`) — not just the 10 data-fetch ones.
- Reduce `.mcp.json` `mcpServers` to a single `leader-mcp` entry. **BREAKING** for any client or script that directly addresses those 7 MCP names by their `.mcp.json` key.
- Add generic gateway tool aliases — `list_mcps`, `list_mcp_tools`, `call_mcp`, `add_mcp`, `remove_mcp`, `get_mcp` — that route to any upstream regardless of "data" vs "non-data" category. The existing `*_data_mcp` tools remain as back-compat aliases over the same implementation, so `ask_data_crew` and the crewai-data-workflow are untouched.
- Generalize `seed_upstreams.py` to seed ALL non-leader entries from `.mcp.json` (the hardcoded `DATA_FETCH_MCPS` dict becomes a derived list: every `mcpServers` key except `leader-mcp`). `--dry-run` / `--unseed` semantics preserved and now operate over the full set.
- Document the recursive-gateway note: `composite-mcp` is itself a gateway. Nesting `leader-mcp → composite-mcp → <upstream>` is supported but must stay one-hop on `composite-mcp`'s side to avoid loops; called out in design.md.

## Capabilities

### New Capabilities

None — no new capability folder. The gateway already exists; this change broadens its scope and tool surface.

### Modified Capabilities

- `leader-mcp-data-gateway`: Broadened from "data-fetch MCPs only" to "all non-leader MCPs". Specifically: (1) the "Data-fetch MCPs removed from client connection" requirement is replaced by "All non-leader MCPs removed from client connection" so the 7 non-data MCPs also leave `.mcp.json`; (2) the "Seed migrates launch config idempotently" requirement is broadened to seed every non-leader entry; (3) a new "Generic gateway tool aliases" requirement is added so the tool surface is not implicitly data-only.

## Impact

- **Code**: `mcp/leader-mcp/gateway_tools.py` (add 6 generic alias functions), `mcp/leader-mcp/seed_upstreams.py` (replace `DATA_FETCH_MCPS` dict with derived "all keys except `leader-mcp`"), `mcp/leader-mcp/server.py` (register the 6 new tools).
- **Config**: `.mcp.json` reduced from 8 entries to 1 (`leader-mcp` only).
- **Database**: no schema change — `leader_upstreams` already stores arbitrary stdio upstreams; `composite-mcp`'s `env={"COMPOSITE": "example"}` is already expressible in the existing `env_json` column.
- **Clients (breaking)**: any direct caller of the 7 removed MCP names must switch to `call_mcp(server="cron-mcp", ...)`. Known callers to audit: Trae `.mcp.json` consumers, `dashboard/` (the `add-ai-chat` change spawns `leader-mcp` only — already compatible), and any cron scripts that spawn MCPs directly.
- **Recursive gateway**: `composite-mcp` is itself a gateway; nesting is one-hop only today and must remain so.
