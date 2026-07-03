## Context

The existing Next.js dashboard at `dashboard/` reads `mcp/daas.db` directly via `sql.js` (WASM) and renders datasource lists, table browsers, and a cron page. Schema lives in `mcp/models/models.py` — the dashboard never issues `CREATE TABLE`. The `daas-mcp` MCP server already manages datasources, categories, forms, sections, and collections (`DatasourceCollection`, `DatasourceCollectionItem`), with `instruction` text on each section used as a `mcp=… tool=… param=k=v` routing grammar.

What's missing: a human-facing way to assemble curated **collections** of datasources/sections and then *use* them as the working context for a chat-driven research session, the way Google NotebookLM lets users pin sources and converse over them.

Two design pressures shape this work:

1. **Reads stay direct, writes get an API surface.** sql.js is read-only against an opened DB. The dashboard already uses sql.js for reads; mutating collections requires a server route.
2. **Chat needs server-side LLM access.** API keys can't ship to the browser, and tool dispatch (sending the model's routing calls to `daas-mcp.fetch_data`) is a server concern.

Stakeholders: this dashboard's primary user is the project owner doing financial / disclosure research across the `daas-mcp` sources (edgar, edinet, dartlab, yfinance, akshare, ckan, cnstats, worldbank, ...).

## Goals / Non-Goals

**Goals:**
- A `/collections` workspace with three panes (catalog · collection · chat) that loads existing datasources, supports drag-and-drop into a collection, and chats with the collection as scope.
- Reuse the existing `dashboard/` Next.js app and `mcp/daas.db` directly — no separate frontend, no new database.
- Keep schema truth in `mcp/models/models.py`; add a `sort_order` column to `DatasourceCollectionItem` if (and only if) it isn't there.
- Mutating endpoints (`/api/collections/*`, `/api/chat`) live in the dashboard's Next.js API routes; they hit `mcp/daas.db` via SQLAlchemy using the shared `mcp/models` package.
- Chat dispatches data calls to the `daas-mcp` source adapters that match the active collection.

**Non-Goals:**
- A new MCP server for the dashboard (the existing `dashboard-mcp` and `daas-mcp` are sufficient).
- A persistent chat history store. Chat history is held in client state (and optionally per-collection in browser storage) — not in `daas.db`. If we later want shared history, that's a follow-up.
- Multi-user auth or sharing. This is single-user, local.
- Building a generic chat-with-anything; this chat is explicitly **scoped to one collection**.
- Replacing existing dashboard pages. The new workspace is additive.

## Decisions

### D1. Drag-and-drop library: `@dnd-kit/core`

We need both the cross-pane drag (catalog → collection) and intra-pane reorder (within the collection). `@dnd-kit` covers both, is the de-facto React DnD library in 2026, and is accessibility-friendly out of the box.

Alternatives considered:
- `react-dnd` — older, larger API surface, fewer recent updates.
- Hand-rolled HTML5 DnD — possible but loses keyboard support and gets noisy.

### D2. Writes go through Next.js API routes, not through `daas-mcp` tool calls

The Next.js API routes (`/api/collections/*`) open `mcp/daas.db` via SQLAlchemy + `from models import …`, perform the write, and return JSON. The dashboard does NOT spawn the `daas-mcp` process to make a collection edit.

Why:
- The dashboard already runs as a Node process; spawning a Python MCP server per request would be slow and racy against the same SQLite file.
- The schema package `mcp/models` is the canonical contract — the dashboard can import it from a sibling Python sidecar OR use a thin TypeScript translation. We choose the **Python sidecar** path: a tiny `dashboard-writer` Python process (FastAPI or even a sub-script invoked per request) is simpler than re-implementing SQLAlchemy in TS.

Refined: Next.js API route → `child_process.spawn` of `uv run --directory mcp/daas-mcp python -m collection_writer <command> <json-args>` (a new tiny CLI we add to `daas-mcp` that wraps the same `registry_service` functions used by the MCP tools). That keeps the write path consistent with the MCP tools and avoids duplicating SQL.

Alternative considered: have the dashboard talk to a long-running HTTP server inside `daas-mcp`. Rejected because `daas-mcp` is stdio-only by design; adding HTTP just for the dashboard doubles the surface.

### D3. `sort_order` column on `DatasourceCollectionItem`

The existing `DatasourceCollectionItem` table has no ordering. Reorder requires one. We add `sort_order: int NOT NULL DEFAULT 0` to `mcp/models/models.py`, then run a guarded `ALTER TABLE` in `daas_database.Database` (idempotent, no Alembic — matches how the project handles the `sources.category_id` migration today).

`add_to_collection` is changed to compute `sort_order = (max in collection) + 1`. `list_collection` orders by `sort_order, id`.

### D4. Chat backend: Anthropic SDK, tool-use loop, streaming via SSE

The `/api/chat` route uses `@anthropic-ai/sdk` (already part of the broader environment, `ANTHROPIC_API_KEY` from root `.env`). Default model: `claude-haiku-4-5-20251001` for cost, switchable per-request to `claude-sonnet-4-6` or `claude-opus-4-8` from a settings dropdown.

Tool exposure: we declare exactly one tool — `daas_fetch_data` — that takes `{ source: string, function: string, params: object }`. The route validates `source` is in the active collection's items, then dispatches to `daas-mcp` via the same Python sidecar pattern (`uv run --directory mcp/daas-mcp python -m fetch_data ...`).

Streaming: Anthropic SDK's `stream` API → Server-Sent Events to the browser.

System prompt is built per-turn from the collection's items: for each item we include `source.name`, `source.label`, optional `form_type`, `section_name`, and the section's `instruction` text. The model sees the routing grammar in the instructions and uses `daas_fetch_data` calls that conform to it.

### D5. URL shape

- `/collections` — workspace, no collection selected (picker prompts).
- `/collections/[name]` — workspace bound to that collection.
- Rename updates the URL via `router.replace`.

Slug = collection name (already unique). If a name contains URL-unsafe characters, encode in URL; the source of truth is still the `name` column.

### D6. Catalog uses `sql.js`, not the new API routes

For consistency with the rest of the dashboard, the catalog listing (`/api/datasources`-style endpoints) is NOT used for reads. Instead `dashboard/src/lib/db.ts` is extended with a `loadCatalog()` helper that runs a single sql.js query joining `sources`, `categories`, `datasource_forms`, `datasource_sections`. Same for `loadCollection(name)`.

### D7. Chat history persistence

Client-side, per-collection, in `localStorage`. Keyed by collection name. Cleared on rename (history follows the old name; a later enhancement can migrate). Non-goal: server-side persistence.

## Risks / Trade-offs

- **[Spawning Python per write request is slow]** → Mitigation: writes are infrequent (drag-drop operations). If we measure >150 ms latency users notice, we can switch to a long-running Python sidecar over a local Unix socket. The CLI wrapper signature is stable, so the swap is internal.

- **[sort_order migration on a populated `daas.db`]** → Mitigation: idempotent `ALTER TABLE … ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0` in `daas_database.Database._migrate_collection_items_sort_order`. Existing items keep `0`; the dashboard backfills order on first reorder. Matches the `category_id` migration pattern already in the codebase.

- **[Chat can call a source the user didn't intend (e.g. the model fabricates a `source`)]** → Mitigation: the `daas_fetch_data` dispatch validates `source` against the active collection items before invoking; unknown source returns an error to the model, which surfaces it to the user.

- **[LLM API key leak via SSR]** → Mitigation: key is read only inside `/api/chat` route handler (server-only); never returned in any response and never inlined into client bundles. Next.js naturally separates these.

- **[Schema drift between `mcp/models` and `dashboard/src/lib/schema.ts`]** → Mitigation: existing convention says schema.ts is a *mirror*; add `sort_order` to both in the same commit. A repo-level check could be added later; out of scope for this change.

- **[DnD on touch devices is fiddly]** → Mitigation: `@dnd-kit` ships pointer + keyboard + touch sensors. We enable all three. Accessibility tests are part of the tasks.

## Migration Plan

1. **Schema**: add `sort_order` to `DatasourceCollectionItem` in `mcp/models/models.py`. Run the guarded `ALTER TABLE` from `daas_database.Database` so existing `mcp/daas.db` upgrades on next MCP startup.
2. **MCP tools**: extend `daas-mcp`'s `registry_service` + `daas_tools` with `rename_collection` and `reorder_collection_items`, and change `add_to_collection` / `list_collection` to honor `sort_order`.
3. **Python CLIs**: add `collection_writer.py` and `fetch_data.py` thin entry points inside `daas-mcp` that the dashboard can `uv run` per request.
4. **Dashboard wiring**: extend `dashboard/src/lib/db.ts` with `loadCatalog()` / `loadCollection()`; mirror `sort_order` in `dashboard/src/lib/schema.ts`.
5. **Dashboard API routes**: implement `/api/collections/create|rename|delete|add-item|remove-item|reorder` and `/api/chat`.
6. **UI**: implement `/collections` and `/collections/[name]` pages with the three-pane layout, drag-and-drop, and the chat panel; wire chat to `/api/chat` with streaming.
7. **Docs**: update `construction/dashboard.md` with the new routes and the LLM API key requirement; update `CLAUDE.md` if conventions changed.
8. **Rollback**: every step is additive. To roll back, remove the `/collections` routes; the `sort_order` column is harmless if unused and no other code depends on rename/reorder tools.

## Open Questions

- Should renaming a collection also migrate its localStorage chat history? Decision deferred to UI polish; default = clear history, with a "you'll lose chat history" warning at rename time.
- Do we want a **read-only "explore" mode** that lets the user chat over a collection without modifying it? Defer until needed; today, every workspace allows edits.
- Should we cache the per-collection system prompt across turns for cost? Anthropic prompt caching (5-minute TTL) is a near-free win once the chat path is stable — pencilled in as a follow-up, not in scope here.
