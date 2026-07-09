## ADDED Requirements

### Requirement: Process navigation entry

The dashboard navigation (`dashboard/src/components/nav.tsx`) SHALL include a "Process" entry linking to `/process/rules`, placed alongside the other top-level pages (Chat, Collections, Databases, Cron Tasks, Workflows, Datasources, Settings).

#### Scenario: Process link is visible in the nav

- **WHEN** any dashboard page renders
- **THEN** the left-hand nav contains a "Process" link pointing to `/process/rules`
- **AND** visiting `/process/rules` or `/process/indicators` marks the nav entry active

### Requirement: Process rules list page

The dashboard SHALL provide a `/process/rules` route (Next.js server component) that lists every row in the `process_rules` table, ordered by `created_at` descending. For each rule the page SHALL show the rule `name`, `source_table`, `text_column`, `model` (or "default" when null), `enabled` (as a toggle), the `last_rowid` cursor, and the count of `process_results` rows for that rule (derived via a single SQL query with a LEFT JOIN/subquery). The page SHALL render a "New rule" action linking to the create form, an empty-state message when no rules exist, and SHALL read directly from `mcp/daas.db` via the existing sql.js path (`getDb('daas')` + `queryAll`) without spawning `process-mcp`.

#### Scenario: List rules with result counts

- **WHEN** the user visits `/process/rules` and `process_rules` contains two rows, each with extracted `process_results` rows
- **THEN** both rules are listed ordered by `created_at` descending
- **AND** each row shows its name, source_table, text_column, model, enabled toggle, last_rowid, and result count

#### Scenario: Rule with no results yet

- **WHEN** a rule exists but has zero `process_results` rows
- **THEN** the list row shows a result count of 0

#### Scenario: Empty state when no rules exist

- **WHEN** the user visits `/process/rules` and the `process_rules` table is empty
- **THEN** the page renders an empty-state message instead of a table

#### Scenario: List page renders without process-mcp

- **WHEN** `process-mcp` cannot start and the user visits `/process/rules`
- **THEN** the page still renders the rule list from `mcp/daas.db` reads without error

### Requirement: Process rule detail page

The dashboard SHALL provide a `/process/rules/[name]` route that resolves a rule by its unique `name` (`decodeURIComponent`-decoded path param) and renders: the rule's full config (`source_table`, `text_column`, `schema_json` pretty-printed, `prompt`, `model`, `max_chars`, `datasource`, `enabled`, `last_rowid`); a recent-`process_results` table (the most recent N rows for that rule, ordered by `run_at` descending) showing `source_rowid`, `model`, `run_at`, and `extracted_json` rendered as pretty-printed JSON truncated to a display budget with a "Show full" toggle; and actions for **Run rule**, **Enable/Disable**, **Edit**, and **Delete**. When the rule `name` does not exist, the page SHALL render a clear "rule not found" state. The page SHALL read directly from `mcp/daas.db` and SHALL NOT spawn `process-mcp` to render.

#### Scenario: Rule detail with recent results

- **WHEN** the user visits `/process/rules/<existing-name>` for a rule with extracted results
- **THEN** the page shows the rule's full config and a recent-results table with pretty-printed `extracted_json`
- **AND** a large `extracted_json` is truncated with a working "Show full" toggle

#### Scenario: Rule not found

- **WHEN** the user visits `/process/rules/nope` and no rule has that name
- **THEN** the page renders a "rule not found" state

#### Scenario: Rule detail renders without process-mcp

- **WHEN** `process-mcp` cannot start and the user visits `/process/rules/<existing-name>`
- **THEN** the page still renders the rule config and results from `mcp/daas.db` reads; only the Run/Edit/Delete actions fail when invoked

### Requirement: Process indicators list page

The dashboard SHALL provide a `/process/indicators` route (Next.js server component) that lists every row in the `indicator_rules` table, ordered by `created_at` descending. For each indicator the page SHALL show `name`, `datasource`, `op`, `value_column`, `indicator_name`, `enabled` (as a toggle), and the latest `observations` value + date for that indicator (filtered by `source=datasource`, `function_name=function_name`, `indicator=indicator_name`, ordered by `date` descending). The page SHALL render a "New indicator" action linking to the create form, an empty-state message when no indicators exist, and SHALL read directly from `mcp/daas.db` without spawning `process-mcp`.

#### Scenario: List indicators with latest observation

- **WHEN** the user visits `/process/indicators` and `indicator_rules` contains rows with computed `observations`
- **THEN** each row shows its name, datasource, op, value_column, indicator_name, enabled toggle, and the latest observation value + date

#### Scenario: Indicator with no observations yet

- **WHEN** an indicator exists but has zero `observations` rows
- **THEN** the list row shows a "No observations yet" marker

#### Scenario: Empty state when no indicators exist

- **WHEN** the user visits `/process/indicators` and the `indicator_rules` table is empty
- **THEN** the page renders an empty-state message instead of a table

### Requirement: Process indicator detail page with observations chart

The dashboard SHALL provide a `/process/indicators/[name]` route that resolves an indicator by its unique `name` and renders: the indicator's full config (`datasource`, `function_name`, `source_table`, `date_column`, `value_column`, `op`, `params_json` pretty-printed, `indicator_name`, `enabled`); a recent-`observations` table for that indicator (filtered by `source=datasource`, `function_name=function_name`, `indicator=indicator_name`, ordered by `date` descending) showing `date` and `value`; an ECharts line chart of the observation series (using `dashboard/src/components/echarts-wrapper.tsx`) capped to the latest 365 points with a count badge; and actions for **Run indicator**, **Enable/Disable**, **Edit**, and **Delete**. When the indicator `name` does not exist, the page SHALL render a clear "indicator not found" state. The page SHALL read directly from `mcp/daas.db` and SHALL NOT spawn `process-mcp` to render.

#### Scenario: Indicator detail with chart and table

- **WHEN** the user visits `/process/indicators/<existing-name>` for an indicator with computed observations
- **THEN** the page shows the indicator config, a recent-observations table, and a line chart of the series capped to the latest 365 points

#### Scenario: Indicator with no observations

- **WHEN** the user visits an indicator that has zero `observations` rows
- **THEN** the page shows the config and an empty-state where the chart and table would be

#### Scenario: Indicator not found

- **WHEN** the user visits `/process/indicators/nope` and no indicator has that name
- **THEN** the page renders an "indicator not found" state

### Requirement: Rule and indicator create forms

The dashboard SHALL provide a create-rule form (reachable from `/process/rules`) and a create-indicator form (reachable from `/process/indicators`) that collect the fields required by `create_rule` and `create_indicator` respectively. The create-rule form SHALL offer pickers for `source_table` (from `list_source_tables`), `text_column` (derived from the chosen source table's columns via `PRAGMA table_info`), and `model` (from `list_models`), with `schema_json` edited as a raw-JSON textarea with a parse-error display. The create-indicator form SHALL offer pickers for `source_table`, `date_column` + `value_column`, `op` (from `list_indicator_ops`), and `datasource`, with `params_json` edited as a raw-JSON textarea. Both forms SHALL submit to a `/api/process/*` route that proxies to the corresponding `process-mcp` tool via `getMCPTools()`. The create-form pages MAY spawn `process-mcp` to populate pickers; list and detail pages SHALL NOT.

#### Scenario: Create a rule via the form

- **WHEN** the user fills the create-rule form with a valid name, source_table, text_column, model, and schema_json and submits
- **THEN** the dashboard calls `create_rule` via `process-mcp` and the new rule appears on `/process/rules` after refresh

#### Scenario: Invalid JSON schema rejected client-side

- **WHEN** the user enters malformed JSON in the `schema_json` textarea and submits
- **THEN** the form shows a parse error and does not submit

#### Scenario: Create-form picker spawn failure

- **WHEN** `process-mcp` cannot start when the create form renders
- **THEN** the form degrades to free-text inputs with an inline warning and remains submittable

### Requirement: Process mutations go through process-mcp tools

The dashboard SHALL perform every rule/indicator mutation (create, update, delete, enable/disable toggle, run) by invoking the corresponding `process-mcp` tool (`create_rule`, `update_rule`, `delete_rule`, `run_rule`, `create_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`) through `getMCPTools()` from `dashboard/src/lib/mcp-client.ts`, exposed via `/api/process/*` Next.js routes. The dashboard SHALL NOT write to `process_rules`, `process_results`, `indicator_rules`, or `observations` via direct SQL. After a successful mutation, the API route SHALL call `invalidateDb('daas')` so the next render re-reads the file. When `process-mcp` is unavailable, the route SHALL return a clear `{error}` to the client.

#### Scenario: Run rule from the detail page

- **WHEN** the user clicks "Run rule" on `/process/rules/<name>`
- **THEN** the dashboard calls `run_rule` via `process-mcp`, the API route invalidates the sql.js cache, and the new `process_results` rows appear after refresh

#### Scenario: Toggle enabled

- **WHEN** the user toggles a rule's enabled flag on the list or detail page
- **THEN** the dashboard calls `update_rule` with the new `enabled` value and the toggle reflects the new state after refresh

#### Scenario: Delete rule

- **WHEN** the user clicks "Delete" and confirms
- **THEN** the dashboard calls `delete_rule` and the rule (and its `process_results` via FK CASCADE) is removed; the user is redirected to `/process/rules`

#### Scenario: Mutation fails when process-mcp is stopped

- **WHEN** the user clicks "Run rule" while `process-mcp` cannot start
- **THEN** the action surfaces a clear inline error and the rest of the page stays usable
