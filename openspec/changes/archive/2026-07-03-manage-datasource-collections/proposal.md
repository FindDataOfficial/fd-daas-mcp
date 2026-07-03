## Why

The dashboard's `/collections` route is a per-collection workspace (catalog → items → chat), but there is no NotebookLM-style "notebooks home" for managing the collections themselves. Today the user manages collections through a thin `<select>` picker plus inline rename/delete controls: they cannot see all collections at a glance with their descriptions and item counts, cannot create a collection with a description in the same dialog (the switcher's "+ New" sends only `name`), and — critically — **cannot edit a collection's description after creation at all**, because the daas-mcp registry exposes `rename_collection` (name only) but no `update_collection`. `description` is set-only-at-create. This change adds a dedicated management page (the NotebookLM "notebooks grid") and closes the description-edit gap in the backend.

## What Changes

- **New management home page** at a new route `/collections/manage`: a NotebookLM-style grid/list of every collection showing name, description, item count, and last-updated, with create / rename / edit-description / delete actions and a link into each collection's three-pane workspace at `/collections/[name]`. The existing `/collections` picker landing is left intact (additive, not a replacement).
- **Create-with-description dialog**: create a collection supplying both `name` and `description` in one form (today's switcher only sends `name`).
- **Edit-description support** (the real gap): add an `update_collection` tool to `daas-mcp` — partial update of `description` and/or `name` in one call — plus a `collection_writer.py update` subcommand and an extension to the `PATCH /api/collections/[name]` route body (today accepts `{ new_name }` only; will accept `{ new_name?, description? }`).
- **Three-pane workspace unchanged** at `/collections/[name]` (catalog → items → chat). The new management page is a sibling route; the inline switcher remains on the workspace for quick switching.
- **Nav**: add a secondary "Manage" link so the management grid is one click from anywhere (the existing "Collections" link still goes to the picker/workspace entry).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `datasource-collections`: add an `update_collection` requirement so a collection's `description` (and optionally `name`) can be edited after creation. Today only `rename_collection` (name) exists; `description` is immutable post-create.
- `collection-dashboard-ui`: add a management home page requirement — a grid of all collections with create-with-description, rename, edit-description, delete, and a link into the per-collection workspace. Lives at a new `/collections/manage` route; the existing `/collections` picker landing and `/collections/[name]` workspace are unchanged.

## Impact

- **`mcp/daas-mcp/registry_service.py`**: add `update_collection(name, new_name=None, description=None)` — partial update; unique-name check only when `new_name` is set and differs; raises on not-found.
- **`mcp/daas-mcp/daas_tools.py`**: add `update_collection` tool wrapper (so the MCP surface matches the writer).
- **`mcp/daas-mcp/collection_writer.py`**: add `update` subcommand (`{name, new_name?, description?}`).
- **`dashboard/src/app/api/collections/[name]/route.ts`**: extend PATCH to accept `{ new_name?, description? }` and dispatch to the `update` writer; at least one of the two required; backward-compatible with today's `{ new_name }` callers (the workspace rename control).
- **`dashboard/src/app/collections/manage/page.tsx`** (new): the management home page (server component reading `loadCollections`).
- **`dashboard/src/components/collections/`**: new management-grid + create/edit-dialog client components; reuse existing `CollectionSwitcher` on the workspace.
- **`dashboard/src/lib/collections.ts`**: `loadCollections` already returns `description` + `item_count` — reused as-is; no new read helper needed.
- **`dashboard/src/components/nav.tsx`**: add a "Manage" link under the Collections entry pointing at `/collections/manage` (existing "Collections" link unchanged).
- **No DB schema change** — `description` already exists on `datasource_collections` (`mcp/models`).
- **Backward compatibility**: the existing PATCH `{ new_name }` contract is preserved (the workspace rename control keeps working); `update_collection` is purely additive.
