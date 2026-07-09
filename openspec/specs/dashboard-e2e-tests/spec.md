# dashboard-e2e-tests Specification

## Purpose
TBD - created by archiving change add-dashboard-e2e-tests. Update Purpose after archive.
## Requirements
### Requirement: Every nav destination loads under a real browser

The dashboard SHALL be covered by Cypress e2e specs that visit every destination listed in the sidebar nav (`/chat`, `/collections`, `/collections/manage`, `/databases`, `/cron`, `/workflows`, `/agents`, `/process/rules`, `/datasources`, `/scores`, `/settings`) and assert the route responds and its primary heading renders. No nav destination SHALL 500 or render a blank screen under a normal visit.

#### Scenario: Collections list page loads

- **WHEN** the browser visits `/collections`
- **THEN** the page responds 200 and renders the collections picker/heading, and either a list of existing collections or the empty-state copy

#### Scenario: Collections manage page loads

- **WHEN** the browser visits `/collections/manage`
- **THEN** the page responds 200 and renders the collection-management UI

#### Scenario: Workflows list page loads

- **WHEN** the browser visits `/workflows`
- **THEN** the page responds 200 and renders the Workflows heading and the workflows table (empty or seeded)

#### Scenario: Workflows detail page loads for a seeded workflow

- **WHEN** the browser visits `/workflows/<name>` for a workflow that exists in `mcp/daas.db`
- **THEN** the page responds 200 and renders that workflow's steps and run history

#### Scenario: Agents list page loads

- **WHEN** the browser visits `/agents`
- **THEN** the page responds 200 and renders the Specialist Agents heading, a "New agent" link, and the agents table (empty or seeded)

#### Scenario: Agents new-agent form loads

- **WHEN** the browser visits `/agents/new`
- **THEN** the page responds 200 and renders the new-agent form with its expected fields

#### Scenario: Process rules list page loads (empty state)

- **WHEN** the browser visits `/process/rules` and there are no rows in `process_rules`
- **THEN** the page responds 200 and renders the Process Rules heading, a "New rule" link, and the empty-state UI without throwing

#### Scenario: Process indicators list page loads (empty state)

- **WHEN** the browser visits `/process/indicators` and there are no rows in `indicator_rules`
- **THEN** the page responds 200 and renders the Process Indicators heading, a "New indicator" link, and the empty-state UI without throwing

#### Scenario: Scores page loads

- **WHEN** the browser visits `/scores`
- **THEN** the page responds 200 and renders the default-scores table and the collection-scores section

### Requirement: One-command headless test runner

The dashboard SHALL provide an `npm run test:e2e` script that starts the Next.js server on the port Cypress expects, waits for it to be ready, runs the Cypress suite headless, exits non-zero on any spec failure, and tears the server down on exit. A contributor SHALL be able to run the entire e2e suite with a single command from `dashboard/` with no manual server start.

#### Scenario: Fresh checkout run

- **WHEN** a contributor runs `npm run test:e2e` from `dashboard/` with no server already running
- **THEN** the script starts the Next.js server on the Cypress `baseUrl` port, waits until that URL returns 2xx, runs `cypress run`, and exits 0 iff every spec passes

#### Scenario: Server teardown on failure

- **WHEN** a spec fails during `npm run test:e2e`
- **THEN** the script exits non-zero and the Next.js server process is terminated (no orphaned process)

#### Scenario: Interactive runner

- **WHEN** a contributor runs `npm run test:e2e:open`
- **THEN** the Cypress interactive runner opens against a server started on the Cypress `baseUrl` port

### Requirement: Suite is green against the current repository database

The e2e suite SHALL pass against the `mcp/daas.db` checked into the repository. No assertion in the suite SHALL reference a database, table, or row that does not exist in the current single-DB schema. Specifically, the suite SHALL NOT assert the presence of `leader_mcp.db` (removed during the single-DB consolidation).

#### Scenario: Databases list asserts the real single DB

- **WHEN** the browser visits `/databases`
- **THEN** the test asserts the presence of `daas.db` and does NOT assert the presence of any `leader_mcp.db` row

#### Scenario: Full suite run

- **WHEN** `npm run test:e2e` runs against the repo's `mcp/daas.db`
- **THEN** every spec in `dashboard/cypress/e2e/` passes with zero failures

### Requirement: Empty-state pages do not throw

Pages whose data source may be empty (`/process/rules`, `/process/indicators`, and any list page when its backing table has zero rows) SHALL render an empty state rather than throwing an uncaught error. The e2e specs SHALL visit these pages against the current (empty-for-process) DB and assert a 200 response plus the empty-state UI.

#### Scenario: Process rules page with no rules

- **WHEN** `process_rules` has zero rows and the browser visits `/process/rules`
- **THEN** the page responds 200 and renders the heading and a "New rule" link, with no uncaught exception

#### Scenario: Process indicators page with no indicators

- **WHEN** `indicator_rules` has zero rows and the browser visits `/process/indicators`
- **THEN** the page responds 200 and renders the heading and a "New indicator" link, with no uncaught exception

### Requirement: Sidebar navigation reaches every destination

The sidebar nav SHALL link to every destination the e2e suite covers, and clicking each link SHALL navigate to the corresponding route without a 404 or 500. The suite SHALL include at least one test that walks the nav across the newly-covered destinations.

#### Scenario: Walk nav to a new destination

- **WHEN** the browser is on `/databases` and clicks the "Workflows" nav link
- **THEN** the URL changes to `/workflows` and the Workflows heading renders

#### Scenario: Walk nav to collections

- **WHEN** the browser is on `/cron` and clicks the "Collections" nav link
- **THEN** the URL changes to `/collections` and the collections page renders

