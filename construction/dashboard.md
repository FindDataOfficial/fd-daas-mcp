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
| `src/components/` | Shared UI: nav, data-table, echarts-wrapper |
| `src/components/collections/` | Workspace, catalog/collection/chat panes, switcher |

## Collections workspace

`/collections` is a NotebookLM-style workspace for managing curated datasource collections from `daas-mcp`.

- **Catalog (left)** — every enabled datasource, grouped by category, with nested forms/sections. Each node is draggable via `@dnd-kit/core`.
- **Collection (center)** — droppable target; items can be reordered (sortable) or removed. Items show source label, form, section name, and the section's `instruction` text (expandable).
- **Chat (right)** — `useChat` from `@ai-sdk/react`, posting to `/api/collections/[name]/chat`. That route builds a system prompt naming every collection item + its instruction, then streams `streamText` with MCP tools from `daas-mcp`. Per-collection history persists in `localStorage` (`collection-chat:<name>`).

Writes go through Next.js API routes which spawn `uv run --directory mcp/daas-mcp python collection_writer.py …`. Reads bypass that and use `sql.js` directly with cache invalidation after writes.

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
