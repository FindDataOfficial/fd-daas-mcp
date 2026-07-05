## REMOVED Requirements

### Requirement: Composite-mcp proxied-mode reachability (known limitation)
**Reason**: The nested-spawn failure is fixed by making composite-mcp's served-tool listing lazy — `build_served_tools` registers `FunctionTool` stubs via `app.add_tool` (tool names from the stored selections, no upstream spawn at list time); a proxied upstream is spawned only when one of its proxied tools is actually called, via a per-call `fastmcp.Client` (the same `build_client` path chained tools already use). Proxied-composite mode now routes through `leader-mcp`; the "known limitation" framing no longer applies.
**Migration**: See the new "Composite-mcp proxied-mode reachability" requirement (ADDED below). The tool surface (management + UI + proxied + chain tools) is unchanged; `call_mcp` / `list_mcp_tools` against composite-mcp with `COMPOSITE=<name>` now succeeds instead of failing with "Connection closed".

## ADDED Requirements

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
