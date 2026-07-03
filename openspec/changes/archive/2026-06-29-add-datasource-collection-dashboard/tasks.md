## 1. Schema & migration

- [x] 1.1 Add `sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)` to `DatasourceCollectionItem` in `mcp/models/models.py`
- [x] 1.2 Mirror `sort_order: number` on the `DatasourceCollectionItem` type in `dashboard/src/lib/schema.ts`
- [x] 1.3 Add `_migrate_collection_items_sort_order` to `mcp/daas-mcp/daas_database.py` (idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0`) and call it next to the existing `_migrate_sources_category_id`
- [x] 1.4 Run the migration once against `mcp/daas.db` by starting `daas-mcp` and confirm the column exists via sqlite

## 2. daas-mcp tool changes

- [x] 2.1 Update `add_to_collection` in `registry_service.py` to compute `sort_order = max(existing in collection) + 1`
- [x] 2.2 Update `list_collection` in `registry_service.py` to ORDER BY `sort_order, id`
- [x] 2.3 Add `rename_collection(old_name, new_name)` to `registry_service.py` with unique-name and "collection not found" errors
- [x] 2.4 Add `reorder_collection_items(collection_name, ordered_item_ids)` to `registry_service.py` with "unknown item rejects whole reorder" semantics
- [x] 2.5 Register `rename_collection` and `reorder_collection_items` as MCP tools in `daas_tools.py` and `server.py`
- [x] 2.6 Add a quick check (run `uv run python selfcheck.py` or equivalent ad-hoc) confirming the two new tools and the order behavior

## 3. Python sidecar CLIs (called by Next.js routes)

- [x] 3.1 Add `mcp/daas-mcp/collection_writer.py` with a tiny argparse / click CLI that dispatches `create | rename | delete | add-item | remove-item | reorder` against `registry_service`, taking JSON args on stdin or as `--json` flag
- [x] 3.2 Add `mcp/daas-mcp/fetch_data_cli.py` that takes `{ source, function, params }` JSON and calls the same code path as the `fetch_data` MCP tool, printing JSON to stdout
- [x] 3.3 Make both CLIs exit non-zero on error and emit a JSON `{ "error": "..." }` line on stderr for easy parsing

## 4. Dashboard reads (sql.js)

- [x] 4.1 Add `loadCatalog()` to `dashboard/src/lib/db.ts` returning datasources grouped by category, each with nested forms/sections
- [x] 4.2 Add `loadCollections()` returning all collections with `{ id, name, description }`
- [x] 4.3 Add `loadCollection(name)` returning the active collection's items joined to source / form / section / instruction, ordered by `sort_order`
- [x] 4.4 Type the returns against `dashboard/src/lib/schema.ts`

## 5. Dashboard API routes

- [x] 5.1 Create `dashboard/src/app/api/collections/route.ts` (`POST` create, `GET` list-as-fallback) calling `collection_writer.py create`
- [x] 5.2 Create `dashboard/src/app/api/collections/[name]/route.ts` with `PATCH` rename and `DELETE` delete
- [x] 5.3 Create `dashboard/src/app/api/collections/[name]/items/route.ts` with `POST` add-item, `DELETE` remove-item, `PATCH` reorder
- [x] 5.4 Implement a `runPythonCli(cli: string, args: any): Promise<any>` helper that `child_process.spawn`s `uv run --directory <abs path to mcp/daas-mcp> python <cli> --json <…>` and parses JSON
- [x] 5.5 Surface clear 4xx/5xx errors with the underlying Python error message in the body

## 6. Chat backend

- [x] 6.1 Add `@anthropic-ai/sdk` to `dashboard/package.json`
- [x] 6.2 Create `dashboard/src/app/api/chat/route.ts` accepting `{ collection: string, messages: ChatMessage[], model?: string }`
- [x] 6.3 Build the system prompt server-side from `loadCollection(name)` items (name, label, form, section, instruction)
- [x] 6.4 Declare a single tool `daas_fetch_data({ source, function, params })`; in the tool-use loop, validate `source` is in the collection's items, then call `runPythonCli('fetch_data_cli.py', …)`
- [x] 6.5 Stream the response via SSE / Next.js streaming; surface tool errors back to the model as tool results
- [x] 6.6 Return a clear 400 if `ANTHROPIC_API_KEY` env is missing; never include the key in any response

## 7. Dashboard UI

- [x] 7.1 Install `@dnd-kit/core` (and `@dnd-kit/sortable` for in-pane reorder) into `dashboard/package.json`
- [x] 7.2 Create `dashboard/src/app/collections/page.tsx` (no collection selected) with a "pick or create a collection" prompt + picker
- [x] 7.3 Create `dashboard/src/app/collections/[name]/page.tsx` with a Server Component that loads catalog + collection, passing data to a Client Component layout
- [x] 7.4 Build `<CatalogPane>` (left) with search input, category grouping, collapsible source/section tree, each draggable via `@dnd-kit`
- [x] 7.5 Build `<CollectionPane>` (center) with droppable area, sortable list, remove control per item, instruction expander
- [x] 7.6 Build `<ChatPane>` (right) — message list, input box, streaming render, per-collection `localStorage` history keyed by name
- [x] 7.7 Build `<CollectionSwitcher>` (header) — picker + "New collection" + rename + delete (confirm)
- [x] 7.8 Wire all drag/drop/remove/reorder/create/rename/delete actions to the API routes from §5; show toasts for duplicate-item / name-collision errors
- [x] 7.9 Wire chat send to `/api/chat`, render tool-call results inline so the user can see what data the model pulled

## 8. Docs & wiring

- [x] 8.1 Update `construction/dashboard.md` with the new `/collections` routes, the API surface, and the `ANTHROPIC_API_KEY` requirement (in root `.env`)
- [x] 8.2 Update root `CLAUDE.md` `mcp/dashboard-mcp/` and dashboard sections to mention the collections workspace
- [x] 8.3 Add a `.env.example` line for `ANTHROPIC_API_KEY` if not already present
- [x] 8.4 Add a top-nav link to `/collections` in the dashboard nav component

## 9. Validation

- [ ] 9.1 Manual: drag two datasources + one section into a fresh collection; verify items + order persist across page reload
- [ ] 9.2 Manual: rename and delete a collection; verify URL + items behavior
- [ ] 9.3 Manual: chat with a collection containing `edgar` (or whatever sources are seeded) and confirm the model issues a `daas_fetch_data` call that comes back with data
- [ ] 9.4 Manual: chat tries to call a source NOT in the collection; verify the route refuses and the model recovers
- [ ] 9.5 Confirm no `ANTHROPIC_API_KEY` value appears in any client-side bundle / network response
- [ ] 9.6 Run the existing dashboard's Cypress smoke suite to ensure no regression on existing pages
