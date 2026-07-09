## ADDED Requirements

### Requirement: Entity collections list page

The system SHALL provide a `/entities` dashboard route that lists every entity collection (`name`, `description`, `item_count`, `rule` indicator) with a control to create a new collection (name + optional description + optional rule JSON) and links to `/entities/[name]` for each collection. Reads SHALL go through sql.js against `mcp/daas.db`.

#### Scenario: Browse collections

- **WHEN** the user navigates to `/entities`
- **THEN** the page shows all entity collections with their item counts, and a "New collection" control

#### Scenario: Create a collection from the page

- **WHEN** the user submits a name (and optional description / rule JSON) in the "New collection" control
- **THEN** a POST to `/api/entities` spawns `collection_writer.py create-entity-collection ...`, the row is created, and the page refreshes to show the new collection

### Requirement: Entity collection detail page

The system SHALL provide a `/entities/[name]` route showing the collection's metadata (editable), its current members (each row: code, name, ticker, exchange, entity_type, added_at, added_reason), an "Add member" control with live entity search, a per-member "Remove" action, and a "Sync now" button for rule-based collections. Writes SHALL go through `/api/entities/[name]/*` routes that spawn the `collection_writer.py` entity-collection subcommands.

#### Scenario: View members

- **WHEN** the user opens `/entities/a-share-leaders`
- **THEN** the page lists the current members in sort order with their entity details and `added_at`

#### Scenario: Add a member via search

- **WHEN** the user types "茅台" into the "Add member" search box and selects the match
- **THEN** a POST to `/api/entities/[name]/items` resolves the entity and adds it; the page refreshes showing the new member at the end of the list

#### Scenario: Remove a member

- **WHEN** the user clicks "Remove" on a member row and confirms
- **THEN** a DELETE to `/api/entities/[name]/items` removes the membership; the page refreshes without that member

#### Scenario: Edit collection metadata

- **WHEN** the user edits the collection name/description/rule and saves
- **THEN** a PATCH to `/api/entities/[name]` updates the collection; members are preserved

#### Scenario: Sync a rule-based collection

- **WHEN** the user clicks "Sync now" on a rule-based collection
- **THEN** a POST to `/api/entities/[name]/sync` invokes the sync; the resulting `added`/`removed` summary is surfaced to the user, and the member list refreshes

#### Scenario: Delete a collection

- **WHEN** the user clicks "Delete collection" and confirms
- **THEN** a DELETE to `/api/entities/[name]` deletes the collection and the user is redirected to `/entities`

### Requirement: Add-in / remove-out history view

The system SHALL provide a "History" panel on the `/entities/[name]` page (and a `/entities/[name]/history` view) that lists `entity_collection_changes` rows newest-first, each showing the entity code/name, the `action` (`add_in` / `remove_out`), the `source` (`manual` / `cron`), the `reason`, and `changed_at`. The panel SHALL be filterable by action.

#### Scenario: View history

- **WHEN** the user opens the History panel for a collection
- **THEN** every `add_in` and `remove_out` event is listed newest-first with entity, action, source, reason, and timestamp

#### Scenario: Filter history by action

- **WHEN** the user selects "add_in only" in the history filter
- **THEN** only `add_in` events are shown

### Requirement: Navigation entry

The system SHALL add an "Entities" entry to the dashboard navigation (`dashboard/src/components/nav.tsx`) linking to `/entities`.

#### Scenario: Nav link present

- **WHEN** the dashboard renders the nav
- **THEN** an "Entities" link pointing to `/entities` is present
