## Why

The dashboard's `/chat` page (from `add-ai-chat`) streams AI responses and calls MCP tools, but tool results are rendered as plain text/JSON cards — MCP tools that produce rich interactive UIs (charts, tables, forms, dashboards) have no way to surface that UI to the user. The `mcp-ui` project (MCP Apps standard) defines exactly this: tools return a UI resource (`_meta.ui.resourceUri` → `ui://...`) that a host fetches and renders inline in a sandboxed frame. Meanwhile the dashboard's chat talks to `leader-mcp`, but the curated, multi-upstream surface the user actually wants to chat with is `composite-mcp`. Bringing `@mcp-ui/client` rendering into `/chat` and pointing it at `composite-mcp` turns the chat into a real "Claude Desktop–style" host where curated tools can return live UIs.

## What Changes

- **Adapt the existing `/chat` page** to render MCP-Apps UI resources: when a tool result carries `_meta.ui.resourceUri` (or returns a `UIResource` content type), fetch the resource via the MCP client and render it inline with `@mcp-ui/client`'s `AppRenderer` inside a sandboxed `AppFrame`. Non-UI tool results keep the existing `tool-call-card` rendering.
- **Add an MCP-server selector** to `/chat` (dropdown: `composite-mcp` (default), `leader-mcp`, `daas-mcp`, …) so the existing leader-mcp + ECharts flow stays available. The selected server is passed through `/api/chat` to `getMCPTools(server)`.
- **Switch the chat's default MCP server to `composite-mcp`** — the curated multi-upstream surface. `MCP_SERVER` env still overrides; the selector wins per-session.
- **Add a demo UI tool to `composite-mcp`** using pure FastMCP: `render_stock_summary` registers a resource template at `ui://composite-mcp/stock-summary/{symbol}` (serving an HTML widget with `mimeType: text/html;profile=mcp-app`) and returns `_meta.ui.resourceUri` via FastMCP's `ToolResult(meta={...})`, so the rendering round-trip works out of the box and serves as a reference for upstream UI tools.
- **Use a raw `@modelcontextprotocol/sdk` `Client` for composite-mcp** in `mcp-client.ts` (alongside the existing `@ai-sdk/mcp` clients) so the same client instance can be passed to `AppRenderer` (which requires a raw `Client`); tool listing is mapped to AI-SDK tools for `streamText`.
- New dashboard deps: `@mcp-ui/client`, `@modelcontextprotocol/ext-apps`. (`@modelcontextprotocol/sdk` is already a dashboard dependency.) No new Python deps — composite-mcp uses FastMCP's built-in resource-template + `ToolResult.meta`.

## Capabilities

### New Capabilities
- `mcp-ui-chat`: Dashboard `/chat` renders MCP-Apps UI resources returned by MCP tools (via `@mcp-ui/client` `AppRenderer`), supports selecting the MCP server (default `composite-mcp`), and composite-mcp ships one demo UI-returning tool that exercises the rendering end-to-end.

### Modified Capabilities
<!-- None at the spec level. The existing /chat page is adapted in code, but its behavior was never specced under openspec/specs/ (the add-ai-chat change was applied to code only). composite-mcp gains one demo tool, but the composite-mcp-server / composite-selection specs describe curation/proxying and are not changed at the requirement level. -->

## Impact

- **New files**:
  - `dashboard/src/components/chat/ui-resource-block.tsx` — renders one tool result as an `AppRenderer` (sandboxed iframe) when it's a UI resource.
  - `dashboard/src/lib/mcp-ui-client.ts` — raw `@modelcontextprotocol/sdk` `Client` singleton for composite-mcp (used by both `/api/chat` tool mapping and `AppRenderer`).
  - `mcp/composite-mcp/ui_tools.py` — the `render_stock_summary` demo tool + a FastMCP resource template at `ui://composite-mcp/stock-summary/{symbol}` (pure FastMCP, no extra Python dep).
- **Modified files**:
  - `dashboard/src/app/chat/page.tsx` — MCP-server selector; render `ui-resource-block` for UI tool results.
  - `dashboard/src/components/chat/message-list.tsx` / `tool-call-card.tsx` — detect UI resources and delegate to `ui-resource-block`.
  - `dashboard/src/lib/mcp-client.ts` — `getMCPClientRaw(server)` returning a raw SDK `Client` (for composite-mcp); keep `@ai-sdk/mcp` path for other servers.
  - `dashboard/src/app/api/chat/route.ts` — accept `server` from the request; use raw client for composite-mcp, `@ai-sdk/mcp` otherwise.
  - `mcp/composite-mcp/server.py` — register the demo UI tool + resource template; no new Python deps.
  - `dashboard/package.json` — add `@mcp-ui/client`, `@modelcontextprotocol/ext-apps`, `@modelcontextprotocol/sdk`.
  - `dashboard/src/components/nav.tsx` — `/chat` label already present; no nav change expected.
- **Dependencies**: `@mcp-ui/client`, `@modelcontextprotocol/ext-apps` (dashboard). No new composite-mcp Python deps.
- **No database changes.**
- **No breaking changes** to existing `/chat` behavior beyond the default server switching to `composite-mcp` (selectable back to `leader-mcp`); the leader-mcp + ECharts flow is preserved.
