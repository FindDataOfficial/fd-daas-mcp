## ADDED Requirements

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
