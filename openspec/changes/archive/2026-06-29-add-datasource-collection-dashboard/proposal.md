## Why

The `daas-mcp` already stores `datasource_collections` and `datasource_collection_items`, but they can only be manipulated through MCP tool calls. There is no human-facing surface to browse the catalog, assemble curated collections, or actually use a collection as a research context. Users need a NotebookLM-style workspace where they can drag-and-drop datasources into a collection and then chat against that collection's data.

## What Changes

- Add a `/collections` section to the existing Next.js dashboard with:
  - A **left panel** listing all datasources (grouped by category, searchable) — items are draggable.
  - A **center panel** showing the active collection's items (whole datasources or specific sections), accepting drops, supporting reorder and remove.
  - A **right panel** chat surface that converses with an LLM scoped to the current collection (the collection's items + their `instruction` text become the chat context / tool-routing grammar).
- Add a collection picker / "new collection" / rename / delete affordance so users can keep many collections side-by-side.
- Add a thin dashboard API route (`/api/collections/...` and `/api/chat`) so chat and write operations don't go through the WASM read path. Reads continue via `sql.js` (current dashboard pattern); writes and chat go through Next.js API routes that call `daas-mcp` (or write directly via SQLAlchemy in-process — see design).
- Extend the existing `datasource-collections` capability with two new requirements: **rename collection** and **reorder items** (needed for the UI, not currently in spec).
- No schema changes — `datasource_collections` and `datasource_collection_items` already cover the data model.

## Capabilities

### New Capabilities
- `collection-dashboard-ui`: NotebookLM-style three-pane dashboard page (catalog · collection · chat) for managing and using datasource collections.
- `collection-chat`: Chat surface that uses a selected collection as the data/context scope, dispatching to `daas-mcp`'s `fetch_data` (and the section `instruction` routing grammar) when the model decides to pull data.

### Modified Capabilities
- `datasource-collections`: add **rename collection** and **reorder items** requirements (small additions; existing create/add/list/remove untouched).

## Impact

- **Code**: new files under `dashboard/src/app/collections/`, `dashboard/src/app/api/collections/`, `dashboard/src/app/api/chat/`, and `dashboard/src/components/` (drag-and-drop pieces, chat panel). New helpers in `dashboard/src/lib/` for collection writes.
- **Schema**: none. `mcp/models/models.py` already has `DatasourceCollection` and `DatasourceCollectionItem`; reorder needs a `sort_order` column on `DatasourceCollectionItem` if it doesn't exist (verify in design).
- **MCP**: `daas-mcp` gains a `rename_collection` tool and (if `sort_order` is added) a `reorder_collection_items` tool, so dashboard writes and MCP-driven writes stay consistent.
- **Dependencies**: add a DnD library to `dashboard/package.json` (e.g. `@dnd-kit/core`) and an LLM client (Anthropic SDK already available via env). No new runtime infra.
- **Env**: dashboard needs an LLM API key for chat (read from root `.env`, e.g. `ANTHROPIC_API_KEY`).
