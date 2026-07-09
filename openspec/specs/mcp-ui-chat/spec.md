# mcp-ui-chat Specification

## Purpose
Dashboard `/chat` page renders MCP-Apps UI resources (the `mcp-ui` standard) returned by MCP tools inline via `@mcp-ui/client`'s `AppRenderer`, supports selecting the MCP server (default `composite-mcp`), and `composite-mcp` ships a demo UI-returning tool that exercises the rendering end-to-end.

## Requirements

### Requirement: Chat renders MCP-Apps UI resources inline

The `/chat` page SHALL detect tool-result parts whose `output` carries `_meta.ui.resourceUri` (a `ui://...` URI) or a `UIResource` content type, and render them inline using `@mcp-ui/client`'s `AppRenderer` inside a sandboxed iframe, instead of the default text/JSON `tool-call-card`. Tool results without a UI resource SHALL continue to render via `tool-call-card` unchanged.

#### Scenario: Tool returns a UI resource
- **WHEN** the selected MCP server's tool returns a result with `_meta.ui.resourceUri` equal to `ui://composite-mcp/stock-summary/AAPL`
- **THEN** the chat renders that tool result as an `AppRenderer` mounting the fetched HTML in a sandboxed iframe, and does not render the plain `tool-call-card` for that result

#### Scenario: Tool returns plain text (no UI resource)
- **WHEN** a tool result has no `_meta.ui.resourceUri` and no `UIResource` content
- **THEN** the chat renders the result via the existing `tool-call-card` unchanged

#### Scenario: UI resource fetch fails
- **WHEN** the host cannot read the resource at `ui://...` (server unreachable, resource not found)
- **THEN** the chat SHALL show a non-blocking error placeholder in place of the widget and SHALL NOT crash the chat session

### Requirement: Chat MCP server is selectable, defaulting to composite-mcp

The `/chat` page SHALL provide a server selector listing MCP servers from `.mcp.json` `mcpServers`, with `composite-mcp` as the default selection. The selected server SHALL be sent to `/api/chat` on every request. The `MCP_SERVER` env var, when set, SHALL override the default. The previously-defaulted `leader-mcp` server SHALL remain selectable and SHALL continue to support the existing ECharts rendering flow.

#### Scenario: Default server is composite-mcp
- **WHEN** the user opens `/chat` with no prior selection and `MCP_SERVER` is unset
- **THEN** the server selector shows `composite-mcp` selected, and chat messages are dispatched against `composite-mcp` tools

#### Scenario: User switches to leader-mcp
- **WHEN** the user selects `leader-mcp` in the selector and sends a message
- **THEN** `/api/chat` uses the `leader-mcp` MCP client and the existing `@ai-sdk/mcp` tool path, and ECharts code blocks continue to render via `EChartsWrapper`

#### Scenario: Env override
- **WHEN** `MCP_SERVER=daas-mcp` is set in the dashboard environment
- **THEN** the selector defaults to `daas-mcp` on first load

### Requirement: composite-mcp ships a demo UI-returning tool

`composite-mcp` SHALL register a tool `render_stock_summary(symbol: str)` that returns a `ToolResult` whose `meta` is `{"ui": {"resourceUri": f"ui://composite-mcp/stock-summary/{symbol}"}}` (mapped to `CallToolResult._meta`) and whose content is a text part. `composite-mcp` SHALL also serve a resource template at `ui://composite-mcp/stock-summary/{symbol}` returning the resource body with `mimeType: text/html;profile=mcp-app` and a non-empty `rawHtml` body. The tool SHALL be available on every composite (always-present), independent of which composite `COMPOSITE` selects. No third-party Python SDK SHALL be required (pure FastMCP).

#### Scenario: Tool returns a UI resource link
- **WHEN** `render_stock_summary` is called with `symbol="AAPL"`
- **THEN** the returned `CallToolResult` contains `_meta.ui.resourceUri` equal to `ui://composite-mcp/stock-summary/AAPL`

#### Scenario: Resource is fetchable
- **WHEN** a host calls `resources/read` with `uri="ui://composite-mcp/stock-summary/AAPL"`
- **THEN** composite-mcp returns a `UIResource` whose `resource.mimeType` is `text/html;profile=mcp-app` and whose `resource.text` is non-empty HTML

#### Scenario: Tool is present regardless of composite
- **WHEN** `COMPOSITE` is set to any composite (including one with no upstreams)
- **THEN** `render_stock_summary` is still listed in `tools/list`

### Requirement: Raw MCP client backs the composite-mcp chat path

When the chat server is `composite-mcp`, `/api/chat` SHALL obtain tools via a server-side raw `@modelcontextprotocol/sdk` `Client` singleton (`getMCPClientRaw`), mapping `client.listTools()` to AI-SDK tools whose `execute` calls `client.callTool`. For all other servers, `/api/chat` SHALL use the existing `@ai-sdk/mcp` `experimental_createMCPClient` path unchanged. Only one stdio process per selected server SHALL be spawned per dashboard process (singleton, reused across requests).

#### Scenario: composite-mcp uses the raw client
- **WHEN** `/api/chat` handles a request with `server="composite-mcp"`
- **THEN** it calls `getMCPClientRaw('composite-mcp')` and maps the returned tools for `streamText`, and does NOT call `experimental_createMCPClient`

#### Scenario: Other servers use the AI-SDK MCP client
- **WHEN** `/api/chat` handles a request with `server="leader-mcp"`
- **THEN** it uses the existing `getMCPClient('leader-mcp')` `@ai-sdk/mcp` path unchanged

#### Scenario: Singleton reuse
- **WHEN** two concurrent `/api/chat` requests target `composite-mcp`
- **THEN** both requests share the same stdio `Client` instance (no second process spawned)

### Requirement: Browser drives the server-side MCP client via HTTP handlers

Because `AppRenderer` runs in the browser and cannot spawn a stdio MCP process, `ui-resource-block` SHALL render `AppRenderer` WITHOUT a `client` prop, supplying custom `onReadResource`/`onCallTool`/`onListResources` handlers that fetch a same-origin server route (`/api/mcp-ui/[op]`). The `/api/mcp-ui/[op]` routes SHALL proxy to the server-side raw `Client` for the currently selected server.

#### Scenario: AppRenderer fetches the UI resource through the server
- **WHEN** `AppRenderer` requests resource `ui://composite-mcp/stock-summary/AAPL`
- **THEN** the browser handler calls `/api/mcp-ui/read-resource` with that URI, the server route reads it via the raw `Client`, and the `UIResource` is returned to `AppRenderer`

#### Scenario: Guest UI calls a tool
- **WHEN** the rendered widget issues a `tools/call` via `AppBridge`
- **THEN** the browser handler calls `/api/mcp-ui/call-tool`, the server route calls `client.callTool`, and the result is returned to the guest

### Requirement: UI resources render in a sandboxed iframe

The `ui-resource-block` SHALL render `AppRenderer` with a sandbox proxy URL (`SandboxConfig.url`) pointing at a dashboard-served proxy HTML page. The proxy iframe SHALL carry `allow-scripts` (so guest widget JS runs). Links opened from within a widget SHALL open in a new browser tab via an `onOpenLink` handler, not navigate the dashboard.

Note: AppFrame's architecture writes guest HTML into an inner `about:blank` iframe via `document.write`, which requires `allow-same-origin` on the proxy iframe (the parent must reach the inner iframe's `contentDocument`). The dashboard-served proxy therefore uses `allow-scripts allow-same-origin allow-forms` (AppFrame's default). A future hardening can use a dedicated sandbox origin / `srcdoc` to drop `allow-same-origin`.

#### Scenario: Sandbox runs guest scripts
- **WHEN** `ui-resource-block` mounts `AppRenderer` against the dashboard proxy
- **THEN** the proxy iframe `sandbox` attribute includes `allow-scripts`

#### Scenario: Widget link opens in a new tab
- **WHEN** the guest UI requests opening an external link
- **THEN** the `onOpenLink` handler calls `window.open(url, '_blank', 'noopener')` and the dashboard route is unchanged
