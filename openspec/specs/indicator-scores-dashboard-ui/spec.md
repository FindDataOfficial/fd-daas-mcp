# indicator-scores-dashboard-ui Specification

## Purpose
TBD - created by archiving change add-indicator-scores. Update Purpose after archive.
## Requirements
### Requirement: Indicator score column on the indicators page

The `/process/indicators` dashboard page SHALL show, for every indicator rule, an inline-editable `score` input (number, blank when NULL = inherit) alongside a read-only "datasource default" hint column showing the indicator's datasource `sources.score`. The page SHALL read both via sql.js (`getDb('daas')` + `queryAll`) in a single query that LEFT JOINs `sources` on `sources.name = indicator_rules.datasource`. Saving a score SHALL `POST` to `/api/indicators/score`; the route SHALL invalidate the daas.db sql.js cache on success so subsequent reads see the new value.

#### Scenario: Indicators page shows the indicator score and the datasource default

- **WHEN** the user opens `/process/indicators`
- **THEN** each row shows an inline number input pre-filled with the indicator's `score` (blank when NULL), and a read-only "datasource default" cell showing the datasource's `sources.score` (blank when NULL)

#### Scenario: Saving a score updates the indicator

- **WHEN** the user enters `0.8` in the score input for "rsi_5" and clicks Save
- **THEN** a `POST /api/indicators/score` fires with `{name: "rsi_5", score: 0.8}`, the indicator's `score` becomes `0.8`, and the page reflects the new value after cache invalidation

#### Scenario: Clearing a score inherits the datasource default

- **WHEN** the user blanks the score input for "rsi_5" and clicks Save
- **THEN** `POST /api/indicators/score` fires with `{name: "rsi_5", score: null}`, the indicator's `score` becomes NULL, and the row shows a blank score with the datasource default still visible

### Requirement: Set indicator score API

The system SHALL expose a `POST /api/indicators/score` API route that accepts `{ name: string, score: number | null }` and invokes the `collection_writer.py set-indicator-score` subcommand. `score = null` clears the indicator's default score. The route SHALL return the updated indicator dict (including `effective_default_score`) and SHALL invalidate the daas.db sql.js cache on success. The route SHALL respond 404 with an error message when the indicator does not exist.

#### Scenario: Update an indicator score

- **WHEN** `POST /api/indicators/score` is called with `{ "name": "rsi_5", "score": 0.8 }`
- **THEN** the `indicator_rules.score` for rsi_5 is set to `0.8` and the response returns the updated indicator dict including `"score": 0.8`

#### Scenario: Clear an indicator score

- **WHEN** `POST /api/indicators/score` is called with `{ "name": "rsi_5", "score": null }`
- **THEN** the `indicator_rules.score` for rsi_5 is set to NULL and the response returns `"score": null`

#### Scenario: Unknown indicator

- **WHEN** `POST /api/indicators/score` is called with `{ "name": "nope", "score": 0.5 }` and the indicator does not exist
- **THEN** the route responds with status 404 and an error message indicating the indicator was not found

### Requirement: Indicator collections dashboard page

The dashboard SHALL add an **Indicator Collections** page at `/process/indicators/collections` (list) and `/process/indicators/collections/[name]` (detail), linked from the `/process/indicators` page. The list page SHALL enumerate every `indicator_collections` row (name, description, item_count) via sql.js with a "New collection" action and per-row "Open" / "Delete" actions. The detail page SHALL list the collection's items ordered by `sort_order`, each row showing: indicator name, an inline-editable per-item `score` input (blank = inherit), a read-only "indicator default" column, a read-only "datasource default" column, and the resolved effective score — plus add/remove/reorder controls. All reads via sql.js; all writes via `/api/indicators/collections/*` routes that spawn `collection_writer.py` subcommands and invalidate the daas.db cache.

#### Scenario: Collections list page

- **WHEN** the user opens `/process/indicators/collections`
- **THEN** every `indicator_collections` row is listed with name, description, and item_count, and each row has "Open" and "Delete" actions

#### Scenario: Collection detail page shows per-item scores with resolution

- **WHEN** the user opens `/process/indicators/collections/momentum`
- **THEN** the page lists the collection's items (ordered by `sort_order`) each with an inline number input (the per-item `score`, blank when NULL), a read-only "indicator default" cell, a read-only "datasource default" cell, and a resolved "effective" cell

#### Scenario: Create a new collection

- **WHEN** the user clicks "New collection" and submits a name (and optional description)
- **THEN** a `POST /api/indicators/collections` route creates the collection and the list page reflects it

#### Scenario: Add an indicator to a collection

- **WHEN** the user picks an indicator from the add control on the detail page and clicks Add
- **THEN** a route spawns `collection_writer.py add-indicator-item` and the new membership row appears (with an `add_in` audit event recorded)

#### Scenario: Remove an indicator from a collection

- **WHEN** the user clicks Remove on an item row
- **THEN** a route spawns `collection_writer.py remove-indicator-item`, the membership row is removed, and a `remove_out` audit event is recorded

#### Scenario: Save a per-item score override

- **WHEN** the user enters `0.9` in the per-item score input for "rsi_5" in collection "momentum" and clicks Save
- **THEN** a `POST /api/indicators/collections/momentum/items/rsi_5/score` route fires with `{score: 0.9}`, the override is set, and the resolved effective score updates

### Requirement: Indicator collection score API

The system SHALL expose a `POST /api/indicators/collections/[name]/items/[indicator]/score` API route that accepts `{ score: number | null }` and invokes the `collection_writer.py set-indicator-collection-item-score` subcommand. `score = null` clears the override. The route SHALL return the updated item dict (including the resolved effective score and the raw `item_score` / `indicator_default_score` / `source_default_score`) and SHALL invalidate the daas.db sql.js cache on success. The route SHALL respond 404 when the collection or the item does not exist.

#### Scenario: Set a per-item override

- **WHEN** `POST /api/indicators/collections/momentum/items/rsi_5/score` is called with `{ "score": 0.9 }`
- **THEN** the matching `indicator_collection_items.score` is set to `0.9` and the response returns the updated item dict with the resolved effective score

#### Scenario: Clear a per-item override

- **WHEN** `POST /api/indicators/collections/momentum/items/rsi_5/score` is called with `{ "score": null }`
- **THEN** the override is cleared and the resolved score falls back to the indicator default (or datasource default)

#### Scenario: Item not in collection

- **WHEN** the route is called for an indicator not in the collection
- **THEN** the route responds 404 with an error indicating the item was not found in the collection

### Requirement: Indicator score writer subcommands

The `collection_writer.py` CLI sidecar SHALL support new subcommands: `set-indicator-score` (args `{name, score}`), `set-indicator-collection-item-score` (args `{collection_name, indicator_name, score}`), plus `create-indicator-collection` (args `{name, description?}`), `delete-indicator-collection` (args `{name}`), `add-indicator-item` (args `{collection_name, indicator_name, score?, reason?}`), `remove-indicator-item` (args `{collection_name, indicator_name, reason?}`), and `reorder-indicator-items` (args `{collection_name, ordered_item_ids}`). `score` SHALL accept `null` to clear on both score subcommands. Each SHALL print one JSON line on stdout and exit non-zero with `{"error": "..."}` on failure, matching the existing writer contract (mirrors `set-source-score` / `set-item-score`).

#### Scenario: set-indicator-score subcommand

- **WHEN** `collection_writer.py set-indicator-score --json '{"name":"rsi_5","score":0.8}'` is run
- **THEN** the `indicator_rules.score` for rsi_5 is updated to `0.8` and the updated indicator dict is printed as one JSON line on stdout

#### Scenario: set-indicator-collection-item-score subcommand with null

- **WHEN** `collection_writer.py set-indicator-collection-item-score --json '{"collection_name":"momentum","indicator_name":"rsi_5","score":null}'` is run
- **THEN** the item's override is cleared (set to NULL) and the updated item dict is printed as one JSON line on stdout

#### Scenario: create-indicator-collection subcommand

- **WHEN** `collection_writer.py create-indicator-collection --json '{"name":"momentum","description":"..."}'` is run
- **THEN** the collection is created and its dict is printed as one JSON line on stdout

