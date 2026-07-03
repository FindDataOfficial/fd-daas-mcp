## Context

The dashboard already ships a NotebookLM-style three-pane collection workspace at `/collections/[name]` (catalog → items → chat) and a thin picker landing at `/collections`. The daas-mcp registry exposes `create_collection`, `rename_collection`, `delete_collection`, `add_to_collection`, `remove_from_collection`, `reorder_collection_items`, and `list_collections` — all wired through `collection_writer.py` (one-process-per-write sidecar) and `/api/collections/*` Next.js routes. Reads go through `sql.js` (WASM, read-only) via `dashboard/src/lib/collections.ts`.

Two gaps motivate this change:

1. **No management surface.** There is no grid/home page listing every collection with its description and item count — only a `<select>` picker and inline rename/delete on the switcher.
2. **Description is immutable after create.** `create_collection(name, description)` accepts a description, but there is no `update_collection` / `set_description` tool. `rename_collection` changes `name` only. Once a collection exists, its description cannot be changed through any API.

Constraints (must respect):

- **Read pattern**: catalog/collection reads use `sql.js` direct-read (`getDb('daas.db')`). Writes MUST go through `collection_writer.py` → `registry_service` (never write via `sql.js`). This is an existing invariant in `collection-dashboard-ui`.
- **No DB schema change**: `datasource_collections.description` already exists (`mcp/models`). No migration.
- **Backward compatibility**: the workspace's `CollectionSwitcher` rename control sends `PATCH { new_name }` — this contract must keep working.
- **Single `.env` / single `mcp/daas.db`**: per CLAUDE.md, all MCPs and the dashboard read/write `mcp/daas.db`.

## Goals / Non-Goals

**Goals:**

- A NotebookLM-style "notebooks home" at `/collections/manage` listing every collection (name, description, item count, last-updated) with create / rename / edit-description / delete / open-workspace actions.
- Create a collection with `name + description` in a single dialog.
- Edit a collection's `description` (and optionally `name`) after creation — close the immutability gap.
- Reuse the existing read-through-`sql.js` / write-through-`collection_writer.py` pattern; no new infra.

**Non-Goals:**

- Reordering collections (the `datasource_collections` table has no `sort_order`; NotebookLM does not reorder notebooks either — out of scope).
- Bulk operations (multi-select add/remove).
- Permissions / multi-user (single-user dashboard).
- Touching the three-pane workspace (`/collections/[name]`) or the chat pane — unchanged.
- A new DB table or column.

## Decisions

### Decision 1: New route `/collections/manage` (additive), not a replacement of `/collections`

**Choice**: Add a new route `/collections/manage` for the management grid. Leave `/collections` (picker landing) and `/collections/[name]` (workspace) untouched.

**Why over promoting `/collections` to the grid**: promoting would modify the existing `collection-dashboard-ui` requirement "Three-pane collection workspace" (whose "no collection selected" scenario currently targets `/collections`) — a breaking spec change with a wider blast radius. The user asked to "add a page", and an additive route yields a purely-ADDED delta spec (no MODIFIED/REMOVED requirements), which is cheaper to review and reversible. The minor redundancy (two collection-listing surfaces) is acceptable because they serve different intents: `/collections` is the chat-driven "jump into a collection" entry; `/collections/manage` is the CRUD surface.

**Alternative considered**: promote `/collections` to the grid, move the picker into the workspace. Rejected — breaking change to a working flow, larger spec delta.

### Decision 2: Backend shape — one `update_collection` tool, partial update

**Choice**: Add `update_collection(name, new_name=None, description=None)` to `registry_service`, exposed as the `update_collection` tool in `daas_tools.py` and the `update` subcommand in `collection_writer.py`. At least one of `new_name` / `description` MUST be provided; omitted fields are left unchanged. Unique-name check fires only when `new_name` is set AND differs from the current name (so `update_collection(name="x", description="y")` does not trip the uniqueness guard).

**Why over alternatives**:
- *Separate `set_description` tool*: rejected — proliferates tools; `rename_collection` + `set_description` would be two calls for a common "edit metadata" action and two specs.
- *Fold into `rename_collection`*: rejected — `rename_collection` has clean single-purpose semantics and an existing spec; overloading it with `description` muddies the contract and the spec scenario "Rename collides".
- *Full-replace `update_collection(name, new_name, description)` (both required)*: rejected — forces the caller to thread the current name/description through every edit, and makes partial edits impossible from a single dialog field.

`update_collection` is purely additive and does not deprecate `rename_collection` (the workspace switcher keeps calling `rename` / `PATCH { new_name }`). They coexist.

### Decision 3: API — extend the existing PATCH, not a new route

**Choice**: Extend `PATCH /api/collections/[name]` to accept `{ new_name?, description? }` (at least one required) and dispatch to the `update` writer subcommand. The existing `{ new_name }` body keeps working unchanged.

**Why over `PUT /api/collections/[name]` or a new `POST /api/collections/[name]/update`**: PATCH already exists, is already partial (rename is a partial update of `name`), and extending its body is the smallest surface. A new route would split the "edit collection metadata" operation across two endpoints. The `collection_writer.py update` subcommand is the single write path, so the route is a thin validator+dispatcher (matches the existing route style in `route.ts` / `items/route.ts`).

### Decision 4: UI — server component + client grid + modal dialog; reuse `loadCollections`

**Choice**:
- `dashboard/src/app/collections/manage/page.tsx` (server component) calls `loadCollections()` (already returns `id, name, description, created_at, updated_at, item_count`) and renders a client `<CollectionManager>` grid.
- `<CollectionManager>` (new client component) renders cards; each card has: name, description (or placeholder), item count, and actions: Open (→ `/collections/[name]`), Edit (modal), Delete (`confirm()` then `DELETE`).
- A "+ New collection" button opens a create modal with `name` + `description` fields → `POST /api/collections` (extend POST to accept optional `description`; today it already does — `route.ts` reads `body.description`).
- Edit modal shows `name` + `description` → `PATCH /api/collections/[name] { new_name?, description? }`.
- After every write, call `router.refresh()` (matches the existing workspace pattern in `workspace.tsx`) to re-run the server component against a fresh DB read. No client-side cache to reconcile.

**Why**: mirrors the existing read-`sql.js`/write-`writer`/refresh-router pattern; no new state library; the modal keeps the NotebookLM "card → edit" mental model. `loadCollections` is reused as-is (no new read helper).

### Decision 5: POST `/api/collections` already accepts `description` — keep it

**Choice**: the existing `POST /api/collections` route already reads `body.description` and passes it to `collection_writer.py create`. The create dialog simply adds a description field and sends it. No route change for create.

## Risks / Trade-offs

- **[Last-write-wins on concurrent edits]** Two tabs editing the same collection's description can clobber each other. → *Mitigation*: low-concurrency single-user dashboard; show `updated_at` on the card so the user can see staleness. No ETag/versioning (out of scope).
- **[New dashboard vs old backend]** If the new UI is deployed but the daas-mcp `update` writer subcommand isn't, edit-description fails with a writer error. → *Mitigation*: deploy daas-mcp + dashboard together; the `update` subcommand is additive and harmless to older dashboards. Rollback: revert the UI route; old `rename`-only flow keeps working.
- **[PATCH body backward-compat]** A future caller sending `{ new_name, description }` to an old PATCH route that only reads `new_name` would silently drop the description. → *Mitigation*: the route validates "at least one of new_name/description" and errors otherwise; the workspace rename control continues to send `{ new_name }` only. Documented in the spec scenario.
- **[Two collection-listing surfaces]** `/collections` picker and `/collections/manage` grid both list collections. → *Mitigation*: acceptable (different intents); the grid links into the workspace, the picker is the chat jump-off. Could collapse later if confusing.

## Migration Plan

1. **Backend first** (additive, safe to deploy before UI):
   - `registry_service.update_collection(...)` + unit check via existing `selfcheck` patterns.
   - `daas_tools.update_collection` tool wrapper.
   - `collection_writer.py` `update` subcommand (add to `choices` + dispatch).
2. **API**: extend `PATCH /api/collections/[name]` body; keep `new_name`-only working.
3. **UI**: add `/collections/manage` page + `<CollectionManager>` + create/edit modal; add nav "Manage" link.
4. **Verify**: `uv run --directory mcp/daas-mcp python selfcheck_gateway.py` not applicable (that's leader-mcp); instead exercise the writer directly: `uv run --directory mcp/daas-mcp python collection_writer.py update --json '{"name":"<test>","description":"x"}'`. Dashboard: `cd dashboard && npm run build` for typecheck; manual smoke of create→edit-description→rename→delete.
5. **Rollback**: revert UI route + nav link (workspace keeps working); revert PATCH body extension (rename keeps working); `update` writer subcommand and `update_collection` tool are additive and can stay or be reverted independently.

## Open Questions

- Should the management grid also show **which datasources** each collection contains (a collapsed item list under the card)? *Tentative: no — keep the card lightweight; "Open" goes to the workspace which already lists items.* Resolve during implementation.
- Should create require a description? *Tentative: no — optional, matches `create_collection` signature.*
- Should delete move from `confirm()` to a custom modal for parity with the new edit modal? *Tentative: keep `confirm()` for now; revisit if the UI feels inconsistent.*
