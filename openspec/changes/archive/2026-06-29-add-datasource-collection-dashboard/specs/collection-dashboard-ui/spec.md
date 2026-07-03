# collection-dashboard-ui

## ADDED Requirements

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
