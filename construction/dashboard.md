# Dashboard Construction

## Architecture

Next.js 15 + sql.js (WASM) — reads `daas.db` directly. No API server, no `CREATE TABLE` statements.

## Env

```bash
# dashboard/.env.local
DAAS_DATABASE_URL=sqlite:///../mcp/daas.db
```

All env flows from root `.env`. Dashboard resolves the DB path from `DAAS_DATABASE_URL` by stripping the `sqlite:///` prefix.

## Schema

**Schema is managed by `mcp/models/models.py`.** The dashboard does NOT define tables.

`dashboard/src/lib/schema.ts` holds TypeScript interfaces as mirrors. When a schema changes, update `mcp/models/models.py` first, then reflect here.

## Key Files

| File | Role |
|------|------|
| `src/lib/db.ts` | sql.js connection, query helpers. No `CREATE TABLE`. |
| `src/lib/schema.ts` | TS type mirrors of `mcp/models/models.py` |
| `src/lib/seed.ts` | Populates `datasources` + `datasource_columns` in `daas.db` |
| `src/lib/collections.ts` | sql.js loaders for catalog/collection (NotebookLM-style workspace) |
| `src/lib/py-cli.ts` | Spawns `uv run … python <cli>` for write operations |
| `src/app/datasources/page.tsx` | Datasource list page |
| `src/app/datasources/[id]/columns/page.tsx` | Column metadata editor |
| `src/app/databases/[dbName]/[tableName]/page.tsx` | Table browser |
| `src/app/cron/page.tsx` | Cron management |
| `src/app/collections/page.tsx` | Collections home (picker + create) |
| `src/app/collections/[name]/page.tsx` | Three-pane workspace (catalog · collection · chat) |
| `src/app/api/collections/*` | Write routes: create / rename / delete / add / remove / reorder |
| `src/app/api/collections/[name]/chat/route.ts` | Collection-scoped chat (overlays `/api/chat` with collection system prompt) |
| `src/app/api/chat/route.ts` | Streaming AI chat — reads `server` from the body; `composite-mcp` → raw SDK client path, else `@ai-sdk/mcp` |
| `src/app/api/mcp-ui/[op]/route.ts` | Same-origin proxy from the browser to the server-side raw MCP `Client` (`read-resource` / `call-tool` / `list-resources`) backing `AppRenderer` |
| `src/lib/mcp-client.ts` | `@ai-sdk/mcp` client per server (default `leader-mcp`); re-exports `getMCPClientRaw`/`getMCPClientRawTools` from `mcp-ui-server.ts` |
| `src/lib/mcp-ui-server.ts` | Server-side raw `@modelcontextprotocol/sdk` `Client` singleton (for `composite-mcp`); `getMCPClientRawTools` maps tools for `streamText` preserving `_meta.ui.resourceUri` |
| `src/components/chat/ui-resource-block.tsx` | Renders one tool result via `@mcp-ui/client` `AppRenderer` (sandboxed iframe + `AppBridge`) when the result carries `_meta.ui.resourceUri` |
| `src/components/` | Shared UI: nav, data-table, echarts-wrapper |
| `src/components/collections/` | Workspace, catalog/collection/chat panes, switcher |
| `public/mcp-ui-sandbox-proxy.html` | v7.1.1-compatible sandbox proxy page for `AppRenderer`'s iframe (writes guest HTML via `document.write` + relays `postMessage`) |

## Collections workspace

`/collections` is a NotebookLM-style workspace for managing curated datasource collections from `daas-mcp`.

- **Catalog (left)** — every enabled datasource, grouped by category, with nested forms/sections. Each node is draggable via `@dnd-kit/core`.
- **Collection (center)** — droppable target; items can be reordered (sortable) or removed. Items show source label, form, section name, and the section's `instruction` text (expandable).
- **Chat (right)** — `useChat` from `@ai-sdk/react`, posting to `/api/collections/[name]/chat`. That route builds a system prompt naming every collection item + its instruction, then streams `streamText` with MCP tools from `daas-mcp`. Per-collection history persists in `localStorage` (`collection-chat:<name>`).

Writes go through Next.js API routes which spawn `uv run --directory mcp/daas-mcp python collection_writer.py …`. Reads bypass that and use `sql.js` directly with cache invalidation after writes.

## MCP-UI chat (`/chat`)

The `/chat` page (from `add-ai-chat`) streams AI responses and calls MCP tools. The `add-mcp-ui-chat` change adapts it to also render **MCP-Apps UI resources** (the `mcp-ui` standard) and to default to **`composite-mcp`** as the chat's MCP server.

- **Server selector** — a `<select>` in the header lists MCP servers (`composite-mcp` default, `leader-mcp`, `daas-mcp`, …). The selection is sent to `/api/chat` via `useChat`'s `experimental_prepareRequestBody` (`{ messages, server }`) and persisted in `localStorage` (`chat-mcp-server`). `NEXT_PUBLIC_MCP_SERVER` / `MCP_SERVER` env overrides the default. The global `defaultServer()` stays `leader-mcp` so non-chat callers (workflows, collections chat) are unaffected.
- **Two client paths** — `composite-mcp` uses a raw `@modelcontextprotocol/sdk` `Client` (`mcp-ui-server.ts`) so the same client backs both `streamText` tool-calling and the `/api/mcp-ui/*` handlers; other servers use `@ai-sdk/mcp` unchanged. The raw `Client` is a singleton per server (one stdio spawn).
- **UI resource rendering** — when a tool result carries `_meta.ui.resourceUri` (a `ui://…` URI), `message-bubble` renders `<UiResourceBlock>` instead of `ToolCallCard`. `UiResourceBlock` mounts `@mcp-ui/client`'s `AppRenderer` with NO `client` prop, supplying `onReadResource`/`onCallTool`/`onListResources` handlers that `fetch('/api/mcp-ui/<op>', { body: { server, … } })`. `AppRenderer` loads the dashboard-served `public/mcp-ui-sandbox-proxy.html` in a sandboxed iframe, which writes the guest HTML via `document.write` and relays `AppBridge` `postMessage`s both ways. Non-UI tool results keep the `ToolCallCard` rendering; ECharts code blocks still render via `EchartsBlock` for `leader-mcp`.
- **composite-mcp demo tool** — `composite-mcp` ships `render_stock_summary(symbol)` (always-present, pure FastMCP) returning `_meta.ui.resourceUri` via `ToolResult.meta` + a resource template at `ui://composite-mcp/stock-summary/{symbol}` (`mimeType: text/html;profile=mcp-app`). Self-check: `uv run --directory mcp/composite-mcp python selfcheck_ui_tool.py`.
- **Note on `useChat` API** — `@ai-sdk/react@1.2.x` dropped `transport`/`sendMessage`; `/chat` uses `api` + `append` + `experimental_prepareRequestBody` + `stopWhen(stepCountIs(n))` (the `add-ai-chat` code was written against an older preview and is rewritten here to the v1.2 API).

## Env additions

Add to root `.env`:

```bash
# Chat provider (anthropic|openai|google|openrouter|ollama|volcengine)
CHAT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Use daas-mcp tools (fetch_data, list_sources, list_collection, ...) for chat
MCP_SERVER=daas-mcp
```

## Key Decisions

- **Direct sql.js access** — not through dashboard-mcp MCP tools. Faster, simpler, no network hop. Schema truth stays in `mcp/models/models.py`.
- **No `dashboard.db`** — `datasources` and `datasource_columns` live in `daas.db`.
- **No `initDashboardDb()`** — tables created by `Base.metadata.create_all()` via any MCP that imports `mcp.models`.
- **Writes via Python sidecar CLI** — `collection_writer.py` is the same code path as the MCP tools, so the dashboard and Claude Code see consistent state. One subprocess per write; slow under load but writes are user-driven and infrequent.
- **Collection chat is a system-prompt overlay**, not a custom tool-use loop. The model's tool list is whatever MCP server is configured (`MCP_SERVER=daas-mcp`); the prompt restricts it to sources in the active collection.

## Standalone HTML dashboards (the `dashboards` registry)

Distinct from the Next.js `dashboard/` app above. The `fd-daas-dashboard-creator` skill builds self-contained HTML dashboards at `dashboard/my-charts-dashboard/<slug>.html` (ECharts, vendored locally at `vendor/echarts.min.js`; interactive entity + time filters; data baked as JSON). Each dashboard's metadata is registered in the `dashboards` table in `mcp/daas.db` (the single source of truth) via `dashboard-mcp.register_dashboard`, which also regenerates `dashboard/my-charts-dashboard/index.html` + `daas.md` from the DB. The `dashboards` row holds: `slug` (unique kebab), `name` (human-readable), `intro` (one-paragraph description), `source_tables` (JSON), `entity_coverage` (JSON), `time_range` (JSON), `refresh_cadence`, `chart_config` (JSON structural description — NOT a full ECharts option blob), `file_path`, `file_url`, timestamps.

- **`dashboard-mcp` registry tools** (6): `register_dashboard`, `list_dashboards`, `get_dashboard`, `search_dashboards`, `update_dashboard`, `delete_dashboard`. All resolve `DAAS_DATABASE_URL` against the repo root.
- **Skills** (in `.claude/skills/`):
  - `fd-daas-dashboard-creator` — build a new standalone HTML dashboard (propose name + intro + entity/time scope → validate source data → build with ECharts + filters → register in DB).
  - `fd-daas-dashboard` — find/open/inspect an existing dashboard (list, search by keyword over name+intro+source, show metadata, open in browser, query backing data via `dashboard-mcp.query_table`). Read-only over the registry.
- **Key decision**: DB is the single source of truth; `index.html` + `daas.md` are derived (regenerated on every write), never hand-appended — no three-way drift. ECharts is vendored locally (not CDN) so dashboards render via `file://` with zero network; CSS-only bars are not used (no interactivity, can't do candlesticks/linked charts).
