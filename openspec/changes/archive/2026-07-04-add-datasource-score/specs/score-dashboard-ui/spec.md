# score-dashboard-ui

## ADDED Requirements

### Requirement: Scores dashboard page

The system SHALL provide a `/scores` page in the Next.js dashboard with two sections: a **Default scores** table listing every datasource with an inline-editable score, and a **Collection scores** section with a collection picker and the selected collection's items each showing an inline-editable per-item score alongside the datasource's default score for reference. The page SHALL read all data via sql.js (`getDb('daas.db')` + `queryAll`, the same read path as the collections workspace) and write through Python CLI sidecars (no direct DB writes from the browser).

#### Scenario: Page lists every datasource with its default score

- **WHEN** the user opens `/scores`
- **THEN** the Default scores section lists every row from `sources` with its `name`, `label`, and current `score` (blank when NULL), each row presenting an inline number input and a Save button

#### Scenario: Page lists a collection's items with per-item scores

- **WHEN** the user picks collection "us-disclosure" in the Collection scores section
- **THEN** the section lists that collection's items (ordered by `sort_order`) showing `source_name`, optional `section_name`, the inline-editable per-item `score`, and a read-only "default" column showing the datasource's default score; the resolved effective score is displayed

### Requirement: Set datasource default score API

The system SHALL expose a `POST /api/scores/source` API route that accepts `{ name: string, score: number | null }` and invokes the `collection_writer.py set-source-score` subcommand to update the datasource's default `score`. `score = null` clears it. The route SHALL return the updated datasource dict and SHALL invalidate the daas.db sql.js cache on success so subsequent reads see the new value.

#### Scenario: Update a default score

- **WHEN** `POST /api/scores/source` is called with `{ "name": "edgar", "score": 0.9 }`
- **THEN** the `sources.score` for edgar is set to `0.9` and the response returns the updated datasource dict including `"score": 0.9`

#### Scenario: Clear a default score

- **WHEN** `POST /api/scores/source` is called with `{ "name": "edgar", "score": null }`
- **THEN** the `sources.score` for edgar is set to NULL and the response returns `"score": null`

#### Scenario: Unknown datasource

- **WHEN** `POST /api/scores/source` is called with `{ "name": "nope", "score": 0.5 }` and the datasource does not exist
- **THEN** the route responds with status 404 and an error message indicating the datasource was not found

### Requirement: Set collection item score API

The system SHALL expose a `POST /api/scores/item` API route that accepts `{ collection_name: string, source_name: string, section_name?: string | null, score: number | null }` and invokes the `collection_writer.py set-item-score` subcommand. `score = null` clears the override. The route SHALL return the updated item dict (including resolved effective score) and SHALL invalidate the daas.db sql.js cache on success.

#### Scenario: Set a per-item override

- **WHEN** `POST /api/scores/item` is called with `{ "collection_name": "us-disclosure", "source_name": "edgar", "score": 0.8 }`
- **THEN** the matching `datasource_collection_items.score` is set to `0.8` and the response returns the updated item dict with the resolved effective score

#### Scenario: Clear a per-item override

- **WHEN** `POST /api/scores/item` is called with `{ "collection_name": "us-disclosure", "source_name": "edgar", "score": null }`
- **THEN** the item's override is set back to NULL and the response reflects the fallback to the datasource default

#### Scenario: Item not in collection

- **WHEN** `POST /api/scores/item` is called for a `(collection, source, section)` that is not in the collection
- **THEN** the route responds with status 404 and an error indicating the item was not found in the collection

### Requirement: Score writer subcommands

The `collection_writer.py` CLI sidecar SHALL support two new subcommands: `set-source-score` (args: `{ name, score }`) and `set-item-score` (args: `{ collection_name, source_name, section_name?, score }`). `score` SHALL accept `null` to clear. Both SHALL print one JSON line on stdout and exit non-zero with `{"error": "..."}` on failure, matching the existing writer contract.

#### Scenario: set-source-score subcommand

- **WHEN** `collection_writer.py set-source-score --json '{"name":"edgar","score":0.9}'` is run
- **THEN** the `sources.score` for edgar is updated to `0.9` and the updated datasource dict is printed as one JSON line on stdout

#### Scenario: set-item-score subcommand with null

- **WHEN** `collection_writer.py set-item-score --json '{"collection_name":"us-disclosure","source_name":"edgar","score":null}'` is run
- **THEN** the item's override is cleared (set to NULL) and the updated item dict is printed as one JSON line on stdout

### Requirement: Scores nav entry

The dashboard navigation SHALL include a "Scores" entry linking to `/scores`, placed alongside the other management entries (after "Datasources").

#### Scenario: Nav shows Scores

- **WHEN** the dashboard nav is rendered
- **THEN** a "Scores" link pointing to `/scores` is present and active when the pathname starts with `/scores`
