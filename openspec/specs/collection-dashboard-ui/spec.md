# collection-dashboard-ui

## Purpose

NotebookLM-style three-pane dashboard workspace for managing and using `daas-mcp` datasource collections: a catalog (left) listing every enabled datasource grouped by category, a center pane showing the active collection's items with drag-and-drop add and intra-pane reorder, and a chat pane (right) bound to that collection. Anchored at `/collections` (no active collection) and `/collections/[name]` (active collection workspace).
## Requirements
### Requirement: Three-pane collection workspace

The dashboard SHALL provide a route (e.g. `/collections` or `/collections/[id]`) that renders a three-pane workspace: a **catalog** pane on the left, a **collection** pane in the center, and a **chat** pane on the right. The workspace is anchored on a single active collection at a time.

#### Scenario: Open the workspace with no collection selected

- **WHEN** the user visits `/collections` and no collection is selected
- **THEN** the catalog and chat panes are visible; the center pane prompts the user to pick or create a collection

#### Scenario: Open the workspace on a specific collection

- **WHEN** the user visits `/collections/<name>` for an existing collection
- **THEN** all three panes are populated: the catalog lists all datasources, the center pane lists that collection's items, and the chat pane is bound to that collection

### Requirement: Datasource catalog with search and grouping

The catalog pane SHALL list every datasource in `daas-mcp`, grouped by category (from the `categories` tree), with a text search box that filters by datasource label, name, form name, or section name.

#### Scenario: Browse by category

- **WHEN** the catalog renders
- **THEN** datasources are grouped under their category (uncategorized sources fall under a "(uncategorized)" group), and groups are collapsible

#### Scenario: Search narrows the list

- **WHEN** the user types `edgar` into the catalog search box
- **THEN** only datasources, forms, or sections matching `edgar` (case-insensitive substring) are shown

#### Scenario: Catalog items expose sections

- **WHEN** a datasource has forms with sections in `daas-mcp`
- **THEN** the catalog renders the datasource as a collapsible node whose children are individual sections, each draggable independently of the parent

### Requirement: Drag-and-drop into a collection

The user SHALL be able to drag a datasource node (whole source) or a section node from the catalog and drop it into the center pane to add it to the active collection.

#### Scenario: Drag a whole datasource

- **WHEN** the user drags the `edgar` node into the center pane
- **THEN** an `add_to_collection(collection=<active>, source_name="edgar")` write is issued and the new item appears in the center pane with `section = null`

#### Scenario: Drag a specific section

- **WHEN** the user drags the `Item 1 Business` section under `edgar` into the center pane
- **THEN** an `add_to_collection(collection=<active>, source_name="edgar", section_name="Item 1 Business")` write is issued and the new item appears in the center pane

#### Scenario: Drop a duplicate

- **WHEN** the user drops an item that is already in the active collection
- **THEN** the dashboard shows a non-blocking message (e.g. toast) saying the item is already in the collection and does not create a duplicate

### Requirement: Manage items in the active collection

The center pane SHALL allow the user to **remove** an item, **reorder** items by drag, and view each item's resolved name, section name (if any), and `instruction` text.

#### Scenario: Remove an item

- **WHEN** the user clicks the remove control on a collection item
- **THEN** a `remove_from_collection(...)` write is issued and the item disappears from the center pane

#### Scenario: Reorder items

- **WHEN** the user drags item B above item A within the center pane
- **THEN** a reorder write is issued so the listed order persists across reloads

#### Scenario: Inspect item instruction

- **WHEN** the user expands a section-item
- **THEN** the dashboard renders the `instruction` text stored on that section (used by chat routing)

### Requirement: Collection switching and lifecycle

The workspace SHALL provide controls to **select** an existing collection, **create** a new one, **rename** the active one, and **delete** the active one (with confirmation).

#### Scenario: Switch collections

- **WHEN** the user picks a different collection from the collection picker
- **THEN** the center pane and chat pane re-bind to that collection; the catalog is unchanged

#### Scenario: Create a new collection

- **WHEN** the user clicks "New collection" and enters a unique name
- **THEN** a `create_collection` write is issued and the new (empty) collection becomes active

#### Scenario: Rename the active collection

- **WHEN** the user renames the active collection to a unique new name
- **THEN** a rename write is issued, the collection picker reflects the new name, and the URL updates to the new slug

#### Scenario: Delete the active collection

- **WHEN** the user confirms deletion of the active collection
- **THEN** the collection and its `datasource_collection_items` rows are removed (datasources themselves are untouched) and the workspace returns to the no-collection state

### Requirement: Read directly, write through API routes

The dashboard SHALL keep the existing `sql.js` direct-read pattern for catalog and collection listings, and SHALL issue mutating actions (`create`/`add`/`remove`/`rename`/`reorder`/`delete`) through Next.js API routes under `/api/collections/...` rather than through `sql.js`.

#### Scenario: Catalog read uses sql.js

- **WHEN** the workspace loads
- **THEN** the catalog and collection lists are fetched via the existing `sql.js` helper in `dashboard/src/lib/db.ts`

#### Scenario: Write goes through API route

- **WHEN** the user adds, removes, reorders, renames, creates, or deletes
- **THEN** the dashboard issues an HTTP request to `/api/collections/...` which performs the write against `mcp/daas.db` using the shared `mcp/models` package

### Requirement: Collection management home page

The dashboard SHALL provide a management home page at `/collections/manage` that lists every datasource collection as a card in a grid, each showing the collection's name, description (or an empty-state placeholder when none), item count, and `updated_at` timestamp. The page SHALL provide actions to **create** a new collection (with both name and description in a single dialog), **rename** a collection, **edit a collection's description**, **delete** a collection (with confirmation), and **open** a collection's three-pane workspace at `/collections/[name]`. The page SHALL be reachable from the dashboard navigation via a "Manage" link alongside the existing "Collections" entry.

#### Scenario: View all collections
- **WHEN** the user visits `/collections/manage` and one or more collections exist
- **THEN** the page renders one card per collection showing name, description (or placeholder), item count, and last-updated timestamp, sorted by name

#### Scenario: Empty state
- **WHEN** the user visits `/collections/manage` and no collections exist
- **THEN** the page renders an empty-state message prompting the user to create their first collection

#### Scenario: Create a collection with a description
- **WHEN** the user clicks "New collection", enters a unique name and a description, and confirms
- **THEN** a `POST /api/collections` with `{ name, description }` is issued and the new collection appears as a card

#### Scenario: Edit a collection's description
- **WHEN** the user opens the edit dialog for a collection, changes the description, and saves
- **THEN** a `PATCH /api/collections/[name]` with `{ description }` is issued and the card's description updates

#### Scenario: Rename a collection from the management page
- **WHEN** the user opens the edit dialog, changes the name to a unique new name, and saves
- **THEN** a `PATCH /api/collections/[name]` with `{ new_name }` is issued and the card reflects the new name

#### Scenario: Delete a collection
- **WHEN** the user clicks delete on a card and confirms
- **THEN** a `DELETE /api/collections/[name]` is issued, the collection and its `datasource_collection_items` rows are removed, and the card disappears

#### Scenario: Open a collection's workspace
- **WHEN** the user clicks "Open" on a card
- **THEN** the dashboard navigates to `/collections/[name]` (the three-pane workspace)

#### Scenario: Duplicate name on create is rejected
- **WHEN** the user creates a collection with a name that already exists
- **THEN** the dialog shows the error returned by the API and does not create a duplicate

### Requirement: Management page reads via sql.js and writes through API routes

The management home page SHALL follow the existing collections-workspace data pattern: reads (the collection list with description and item count) SHALL use the `sql.js` direct-read helper in `dashboard/src/lib/collections.ts` (`loadCollections`), and mutating actions (create / rename / edit-description / delete) SHALL be issued as HTTP requests to Next.js API routes under `/api/collections/...` which perform the write against `mcp/daas.db` via `collection_writer.py` and the shared `mcp/models` package. The page SHALL NOT write to `daas.db` directly through `sql.js`.

#### Scenario: List read uses sql.js
- **WHEN** the management page loads
- **THEN** the collection list is fetched via `loadCollections()` (sql.js read against `mcp/daas.db`)

#### Scenario: Edit-description write goes through the API route
- **WHEN** the user edits a collection's description and saves
- **THEN** the dashboard issues `PATCH /api/collections/[name]` with `{ description }`, which dispatches to the `collection_writer.py update` subcommand (and ultimately `update_collection`)

### Requirement: Mutating writes resolve to the same database as reads, independent of process cwd

The dashboard's mutating routes (`/api/collections/*`) SHALL spawn `collection_writer.py` such that the writer connects to the **same** `mcp/daas.db` file the dashboard's sql.js read path uses, regardless of the directory from which the Next.js dev or build server was launched. The dashboard SHALL derive the repo root by walking upward from `process.cwd()` until it finds a directory containing both `mcp/daas-mcp/collection_writer.py` and `dashboard/package.json`, and SHALL resolve both `DAAS_MCP_DIR` (the writer's launch directory) and the sql.js read DB path from that repo root — not from `process.cwd()` alone. If no ancestor directory satisfies both markers, the dashboard SHALL fail with a clear error rather than silently resolving to a wrong database path.

#### Scenario: Launched from the dashboard directory

- **WHEN** the Next.js server is launched from `dashboard/` (the conventional launch directory) and a user creates a collection
- **THEN** the spawned writer writes a row to `mcp/daas.db` and the subsequent sql.js read of `datasource_collections` returns that row

#### Scenario: Launched from the repository root

- **WHEN** the Next.js server is launched from the repository root (a directory containing both `dashboard/` and `mcp/`) and a user creates a collection
- **THEN** the spawned writer writes to the same `mcp/daas.db` and the subsequent sql.js read returns that row (no "unable to open database file" error, no path divergence)

#### Scenario: Launched from a directory with no repo-root ancestor

- **WHEN** the Next.js server is launched from a directory whose ancestor chain contains no directory with both `mcp/daas-mcp/collection_writer.py` and `dashboard/package.json`
- **THEN** the mutating route returns an error indicating the repo root could not be located, rather than silently writing to or reading from a wrong database path

### Requirement: The writer loads environment files in repo-root-first order

The `collection_writer.py` sidecar SHALL load the repository-root `.env` (the directory containing `mcp/` and `dashboard/`) before its own per-MCP `.env` (loaded with `override=True`), matching the documented "single `.env`" convention so a standalone run of the writer (or of `daas-mcp`'s `server.py`, which shares this load order and is spawned by the MCP host without the dashboard's env) honors a `DAAS_DATABASE_URL` configured in the repo-root `.env`. The repo-root load SHALL use `override=False` (the `dotenv` default), so when the dashboard spawns the writer and `DAAS_DATABASE_URL` is already present in the inherited process env, the inherited value takes precedence and the writer stays in sync with the dashboard. The writer SHALL still resolve any relative `DAAS_DATABASE_URL` against the repo root (its cwd is `mcp/daas-mcp/` under `uv run --directory`), and SHALL fall back to an absolute default `mcp/daas.db` when `DAAS_DATABASE_URL` is unset.

#### Scenario: Standalone writer run uses the repo-root .env

- **WHEN** `collection_writer.py` is run without `DAAS_DATABASE_URL` in the inherited process env and the repo-root `.env` defines `DAAS_DATABASE_URL=sqlite:///mcp/custom.db`
- **THEN** the writer connects to `mcp/custom.db` (resolved against the repo root) and the create succeeds there

#### Scenario: Inherited env var takes precedence over the repo-root .env

- **WHEN** the dashboard spawns the writer and `DAAS_DATABASE_URL` is present in the inherited process env (loaded by Next.js from `dashboard/.env.local`)
- **THEN** the writer uses the inherited value and does NOT override it with the repo-root `.env`'s value (load order is repo-root first with `override=False`, per-MCP last with `override=True`)

#### Scenario: Unset DAAS_DATABASE_URL falls back to the absolute default

- **WHEN** `DAAS_DATABASE_URL` is not present in the inherited process env, not in the repo-root `.env`, and not in the per-MCP `.env`
- **THEN** the writer connects to the absolute default `mcp/daas.db` (resolved via the writer's own file location) and the create succeeds

#### Scenario: Per-MCP .env override still wins

- **WHEN** the repo-root `.env` sets `DAAS_DATABASE_URL=sqlite:///mcp/daas.db` and `mcp/daas-mcp/.env` sets `DAAS_DATABASE_URL=sqlite:///:memory:` with override enabled
- **THEN** the writer uses `:memory:` (the per-MCP override wins) — confirming the load order is repo-root first, per-MCP last with override

