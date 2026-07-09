## Context

The dashboard (`dashboard/`, Next.js 15 App Router) already has a `/chat` page from the `add-ai-chat` change. It streams AI responses via the Vercel AI SDK (`useChat` + `streamText`), calls MCP tools through `@ai-sdk/mcp`'s `experimental_createMCPClient` (singleton in `dashboard/src/lib/mcp-client.ts`, default server `leader-mcp`), and renders tool results as `tool-call-card`s plus `echarts` code blocks via `EChartsWrapper`. Chat history is `localStorage`; no DB tables.

`composite-mcp` (`mcp/composite-mcp/server.py`, FastMCP) curates a composite MCP: it proxies selected tools from upstream MCP servers (e.g. `akshare`) via `fastmcp.server.create_proxy`, plus always-present management tools, plus chained tools. The served composite is selected by `COMPOSITE` env (`.mcp.json` ships `COMPOSITE=example`). Its `FilterTools` transform keeps only selected tool names but forwards calls verbatim — `_meta` passes through untouched.

`mcp-ui` (`@mcp-ui/client` + `@modelcontextprotocol/ext-apps`) implements the MCP Apps standard: a tool returns `_meta.ui.resourceUri` (a `ui://...` URI); the host reads that resource via `resources/read` and renders it with `<AppRenderer>`, which mounts the HTML in a sandboxed iframe (`AppFrame`) and bridges host↔guest via `postMessage` (`AppBridge` + `PostMessageTransport`). `AppRenderer` takes a `client?: Client` (raw `@modelcontextprotocol/sdk` `Client`) for automatic MCP forwarding, plus `toolResourceUri`, `toolName`, `toolInput`, `toolResult`. The Python server SDK `mcp-ui-server` (`from mcp_ui_server import create_ui_resource`) builds UI resources server-side.

The existing `mcp-client.ts` uses `@ai-sdk/mcp`, whose client object does **not** expose the raw `@modelcontextprotocol/sdk` `Client` that `AppRenderer` requires.

## Goals / Non-Goals

**Goals:**
- Render MCP-Apps UI resources inline in `/chat` when a tool result carries `_meta.ui.resourceUri`.
- Make the chat's MCP server selectable; default to `composite-mcp` while keeping `leader-mcp` (and the ECharts flow) selectable.
- Ship one demo UI-returning tool on `composite-mcp` so the round-trip works out of the box.
- Keep changes additive: no DB changes, no breaking changes to existing `/chat` behavior beyond the default-server switch.

**Non-Goals:**
- Building a new chat page (we adapt the existing `/chat`).
- Multi-MCP-server tool merging inside one chat session (one server per session).
- Server-side chat-history persistence (still `localStorage`).
- Authoring UI tools on every upstream MCP — only the composite-mcp demo tool ships here.
- Remote-DOM / React-component UI resources (we use `rawHtml` for the demo; `remoteDom` support is future work).
- Mobile-responsive chat layout.

## Decisions

### Decision 1: Render UI resources via `@mcp-ui/client` `AppRenderer` in a new `ui-resource-block` component

**Chosen**: A new `dashboard/src/components/chat/ui-resource-block.tsx` renders one tool result. `message-list` detects tool-result parts whose `output` carries `_meta.ui.resourceUri` (or a `UIResource` content type) and delegates to `ui-resource-block` instead of `tool-call-card`. `ui-resource-block` mounts `<AppRenderer client={rawClient} toolName={...} toolResourceUri={uri} toolInput={...} toolResult={...} sandbox={...} />`.

**Rationale**: `AppRenderer` is the canonical MCP-Apps host renderer; it handles iframe sandboxing, `AppBridge` wiring, and host capability negotiation. Reusing it avoids re-implementing a sandbox. Non-UI tool results keep the existing card UI.

**Alternatives**:
- Render the HTML directly with `dangerouslySetInnerHTML` in a div — no sandbox, XSS risk, no `AppBridge` (guest tool calls would not round-trip). Rejected.
- Build a custom iframe + `postMessage` bridge — reimplements `AppRenderer`/`AppFrame`/`AppBridge`. Rejected.

### Decision 2: Use a raw `@modelcontextprotocol/sdk` `Client` for composite-mcp; keep `@ai-sdk/mcp` for other servers

**Chosen**: Add `getMCPClientRaw(server)` in `mcp-client.ts` using `@modelcontextprotocol/sdk`'s `Client` + `StdioClientTransport` (spawn config reused from `getServerConfig`). For `composite-mcp`, the `/api/chat` route uses the raw client: `client.listTools()` → map each to an AI-SDK tool (`{description, inputSchema, execute: (args) => client.callTool({name, arguments: args})}`), pass to `streamText`. The same raw client is held client-side (via a `/api/mcp-client` SSE/hook or, simpler, instantiated in the browser through a thin server action that returns tool-result metadata) — **see Decision 3** for where the client lives. For non-composite servers, the existing `@ai-sdk/mcp` path is unchanged.

**Rationale**: `AppRenderer` requires a raw `Client` (`client?: Client`). The `@ai-sdk/mcp` wrapper does not expose it cleanly. A single raw client for composite-mcp serves both `streamText` tool-calling and `AppRenderer` — one process, one connection. Other servers keep `@ai-sdk/mcp` (no regression).

**Alternatives**:
- Switch all servers to the raw SDK — larger blast radius, drops `@ai-sdk/mcp`'s conveniences. Rejected.
- Keep `@ai-sdk/mcp` for tool-calling and create a parallel raw client just for `AppRenderer` — two stdio processes per composite-mcp request, double the spawn cost. Rejected.

### Decision 3: `AppRenderer` runs server-side is not viable; render client-side with a server-exposed UI-resource fetch

**Chosen**: `AppRenderer` is a React client component that needs an interactive `Client`. We instantiate the raw `Client` **in the browser** is also not viable (can't spawn stdio from browser). Instead: the raw `Client` lives on the **Next.js server** (singleton, per server), and the browser renders `AppRenderer` with **custom handlers** (`onReadResource`, `onCallTool`, `onListResources`) that proxy to the server via fetch (`/api/mcp-ui/*`), instead of passing a raw `client`. This uses `AppRenderer`'s "omit `client`, use custom handlers" mode.

Concretely:
- `dashboard/src/lib/mcp-ui-server.ts` — singleton raw `Client` per server (server-side only).
- `dashboard/src/app/api/mcp-ui/[op]/route.ts` — thin server route: `read-resource`, `call-tool`, `list-resources` → call the singleton client → return JSON. Auth scope: same-origin (dashboard).
- `dashboard/src/components/chat/ui-resource-block.tsx` — builds handlers that `fetch('/api/mcp-ui/read-resource', {body: {uri}})`, passes them to `<AppRenderer>` (no `client` prop).

**Rationale**: `AppRenderer`'s `onReadResource`/`onCallTool`/etc. override automatic MCP forwarding, letting the browser drive a server-side client over HTTP. This keeps the stdio process on the server and the sandboxed iframe in the browser, with no second process.

**Alternatives**:
- Run `AppRenderer` on the server (RSC) — iframes and `postMessage` don't work server-side. Rejected.
- Spawn the MCP server over SSE/HTTP transport from the browser — would require composite-mcp to expose an HTTP transport and a public endpoint; out of scope and a security hole. Rejected.

### Decision 4: `composite-mcp` demo tool `render_stock_summary` returns a `rawHtml` UI resource (pure FastMCP, no server SDK)

**Chosen**: Add `mcp/composite-mcp/ui_tools.py` with `render_stock_summary(symbol: str)`. It builds an HTML widget (a small inline stock-overview card with a couple of stat tiles; static HTML, no live data in v1 to avoid akshare latency), registers a FastMCP `@app.resource("ui://composite-mcp/stock-summary/{symbol}", mime_type="text/html;profile=mcp-app")` resource template returning the HTML string, and the tool returns `ToolResult(content=[TextContent(type="text", text=f"Stock summary for {symbol}")], meta={"ui": {"resourceUri": f"ui://composite-mcp/stock-summary/{symbol}"}})` via FastMCP's `ToolResult.meta` (maps to `CallToolResult._meta`). `server.py` imports and registers it.

**Rationale**: One end-to-end demonstrable tool. `rawHtml` is the simplest content type; no React/runtime needed. The resource-template URI per-symbol lets `AppRenderer` fetch the right widget. Keeping it static avoids coupling to akshare availability in v1; a follow-up can wire live data. **No `mcp-ui-server` Python SDK**: the PyPI release (1.0.0) is stale — it emits `mimeType: text/html` instead of the spec-required `text/html;profile=mcp-app`, and the SDK only helps build embedded `UIResource` content blocks (unused here, since we use the canonical `_meta.ui.resourceUri` + `resources/read` flow). Pure FastMCP `@app.resource(..., mime_type=...)` + `ToolResult(meta=...)` covers all spec requirements with no extra dependency and no version drift.

**Alternatives**:
- Install `mcp-ui-server` from git (the GitHub `5.2.0` has the correct `RESOURCE_MIME_TYPE`) — adds a floating git dep for no real value (the SDK is for embedded resources, which we don't use). Rejected.
- Use the PyPI `mcp-ui-server` 1.0.0 and override the mimeType manually — works but the SDK is dead weight. Rejected.
- A chained tool that calls an upstream and renders its result as UI — showcases chaining too, but chained tools currently return text; extending them to return UI resources is more work. Deferred.
- A remoteDom React widget — richer but needs a React runtime in the iframe; deferred.
- No demo tool — feature undemonstrable. Rejected (user opted in).

### Decision 5: MCP-server selector + per-session server override (chat-specific default)

**Chosen**: `chat/page.tsx` gains a `<select>` (servers: `composite-mcp` (default), `leader-mcp`, `daas-mcp`, `cron-mcp`, `dashboard-mcp`, `alerts-mcp`). The selected server is sent on each request via `experimental_prepareRequestBody` (v1.2 API; the prior `transport`/`sendMessage` code was drifted and broken against `@ai-sdk/react@1.2.12`, so the `useChat` wiring is rewritten to `api` + `append` + `experimental_prepareRequestBody`). `/api/chat` reads `server` from the request body and dispatches: composite-mcp → raw-client path; else → `@ai-sdk/mcp` path. The chat default is `composite-mcp` (`DEFAULT_SERVER` in `chat/page.tsx`, `mcpServer` in `route.ts`), overridable by `NEXT_PUBLIC_MCP_SERVER` / `MCP_SERVER` env. The global `mcp-client.ts` `defaultServer()` is left as `leader-mcp` so non-chat callers (the workflows API, the collections chat) keep their leader-mcp default — the composite-mcp default is chat-specific and does not ripple.

**Rationale**: One chat page, multiple servers, no loss of the leader-mcp + ECharts flow. Defaulting to composite-mcp matches the user's intent; the selector preserves the prior behavior. Keeping the global default at leader-mcp avoids breaking the workflows + collections APIs that depend on leader-mcp's tools.

**Alternatives**:
- Switch the global `defaultServer()` to composite-mcp — breaks `api/workflows/[name]/runs` and `api/collections/[name]/chat` (they call `getMCPTools()` with no arg and need leader-mcp). Rejected.
- Hard-switch the chat default with no selector — loses the leader-mcp flow. Rejected.
- Separate `/chat?server=` query param — less discoverable than a selector. Rejected.

### Decision 6: Sandbox config for `AppRenderer`

**Chosen**: `sandbox` = `{ url: new URL('/mcp-ui-sandbox-proxy.html', window.location.origin) }` — a dashboard-served proxy HTML page (copied into `dashboard/public/`) that implements the v7.1.1 protocol: on load it posts `{method: "ui/notifications/sandbox-proxy-ready"}`; it consumes `{method: "ui/notifications/sandbox-resource-ready", params: {html}}` to write the guest HTML into an inner `about:blank` iframe via `document.write`; and it relays all other `postMessage`s parent↔inner (so the AppBridge JSON-RPC channel works). The proxy iframe ends up with AppFrame's default `allow-scripts allow-same-origin allow-forms` — `allow-same-origin` is required for the proxy to reach the inner iframe's `contentDocument` to write the HTML (AppFrame hardcodes this; the v7.1.1 repo proxy has the same property). `onOpenLink` opens links in a new tab (`window.open(url, '_blank', 'noopener')`).

**Rationale**: The v7.1.1 `@mcp-ui/client` AppFrame posts `{method: "ui/notifications/sandbox-resource-ready", params: {html}}` and waits for `{method: "ui/notifications/sandbox-proxy-ready"}` — but the proxy HTML committed on `mcp-ui`'s `main` branch uses the OLDER protocol (`ui-html-content` / `ui-proxy-iframe-ready`), so it does NOT work with v7.1.1. The dashboard therefore ships its own v7.1.1-compatible proxy. `allow-same-origin` is unavoidable here because `document.write` into the inner iframe requires parent access to `contentDocument`; a future hardening can use a dedicated sandbox origin or `srcdoc` to drop it.

**Alternatives**:
- Use the repo `main`-branch proxy — incompatible with v7.1.1 (protocol mismatch). Rejected.
- `allow-scripts`-only (no `allow-same-origin`) — `document.write` into the inner iframe fails (parent can't reach `contentDocument` of a uniquely-origined iframe). Rejected for v1; noted as future hardening.
- A plain `<iframe srcdoc={html} sandbox="allow-scripts" />` (no AppRenderer) — simpler and safer, but loses the AppBridge (guest can't call host tools) and isn't "using mcp-ui". Rejected (user wants mcp-ui).

## Risks / Trade-offs

- **`AppRenderer` API churn** (`@mcp-ui/client` is at v5.x, MCP Apps spec still evolving) → Pin an exact `@mcp-ui/client` / `@modelcontextprotocol/ext-apps` version in `dashboard/package.json`; wrap usage in `ui-resource-block.tsx` so a future API change is one-file.
- **`_meta` passthrough in `composite-mcp` proxy** — `FilterTools` forwards calls but if FastMCP's `create_proxy` strips `_meta` from `CallToolResult`, UI resources from proxied upstream tools won't render → Mitigation: the demo tool is on composite-mcp directly (not proxied), so it works regardless; add a self-check asserting `_meta.ui.resourceUri` survives a proxied round-trip once an upstream UI tool exists.
- **Two connection paths in `mcp-client.ts`** (raw SDK + `@ai-sdk/mcp`) → Mitigation: clear code split — `getMCPClientRaw()` for composite-mcp, `getMCPClient()` (existing) for others; a self-check asserts both connect to `mcp/daas.db`-less stdio servers.
- **iframe sandbox blocks `postMessage` to parent** → `AppRenderer`/`AppBridge` is designed for this; if `allow-scripts`-only blocks it, fall back to `allow-scripts allow-same-origin` and document. Verified at implementation time.
- **`mcp-ui-server` Python dep on `mcp>=1.0.0`** — composite-mcp already uses FastMCP; version compatibility → Mitigation: `uv sync` in `mcp/composite-mcp/` and run `selfcheck.py`; pin `mcp-ui-server` to a tested version.
- **Default-server switch is a behavior change** — existing `/chat` users expecting leader-mcp → Mitigation: selector defaults to composite-mcp but leader-mcp is one click away; documented in the change.

## Migration Plan

1. Add deps (`dashboard/package.json`; `mcp/composite-mcp/pyproject.toml`). `uv sync` composite-mcp; `npm install` dashboard.
2. Implement composite-mcp demo UI tool (`ui_tools.py` + `server.py` registration) and verify `selfcheck` + a manual `fastmcp run` exposes `render_stock_summary` and serves `ui://composite-mcp/stock-summary/{symbol}`.
3. Implement `mcp-ui-server.ts` (raw client singleton) + `/api/mcp-ui/[op]` routes; verify `read-resource` returns the demo widget HTML.
4. Implement `ui-resource-block.tsx` + wire `message-list`; implement `/api/chat` `server` dispatch + selector.
5. Manual E2E: open `/chat`, pick composite-mcp, ask "show me a stock summary for AAPL" → `render_stock_summary` fires → widget renders inline.
6. Rollback: revert the PR; `/chat` returns to leader-mcp default (selector + raw-client code is additive and inert when composite-mcp is not selected). composite-mcp demo tool is additive (always-present tool; existing composites unaffected).

## Open Questions

- Should the demo `render_stock_summary` fetch live data (akshare) in v1, or stay static? **Default: static**; a follow-up change wires live data once the rendering is stable.
- Do we want the MCP-server selector to also list composite-mcp's *named composites* (e.g. pick `example` vs another composite)? **Default: no** — `COMPOSITE` env selects the composite; the selector picks the MCP server. Could add later.

## Follow-ups (deferred)

- Wire live akshare data into `render_stock_summary` (currently static demo data) once the mcp-ui rendering is confirmed stable in the browser.
- Add a self-check asserting `_meta.ui.resourceUri` survives a **proxied upstream** round-trip (via `create_proxy` + `FilterTools`) once an upstream MCP ships a UI-returning tool. The demo tool is on composite-mcp directly so it doesn't exercise the proxy path.
- Replace the `allow-same-origin` sandbox proxy with a dedicated sandbox origin / `srcdoc` approach to drop `allow-same-origin` (AppFrame's `document.write` requires it today).
- Run the full `chat` → LLM → tool-call → `AppRenderer`-iframe browser E2E with an LLM API key (no key was available during implementation; verified up to the API layer via `next build` + `/api/mcp-ui/*` curl + `mcp-ui.cy.ts`).
