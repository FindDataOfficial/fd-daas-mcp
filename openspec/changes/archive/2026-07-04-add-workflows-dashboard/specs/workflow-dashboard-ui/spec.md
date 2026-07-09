## ADDED Requirements

### Requirement: Workflows navigation entry

The dashboard navigation (`dashboard/src/components/nav.tsx`) SHALL include a "Workflows" entry linking to `/workflows`, placed alongside the other top-level pages (Chat, Collections, Databases, Cron Tasks, Datasources, Settings).

#### Scenario: Workflows link is visible in the nav

- **WHEN** any dashboard page renders
- **THEN** the left-hand nav contains a "Workflows" link pointing to `/workflows`
- **AND** visiting `/workflows` marks the nav entry active

### Requirement: Workflow list page

The dashboard SHALL provide a `/workflows` route (Next.js server component) that lists every row in the `workflows` table, ordered by `created_at` descending. For each workflow the page SHALL show the workflow `name`, `description`, step count (count of `workflow_steps` rows for that `workflow_id`), and the most recent `workflow_runs` row's `status` and `started_at` (derived via a single SQL query joining `workflows` → `workflow_runs`). The page SHALL render an empty-state message when no workflows exist. The page SHALL read directly from `mcp/daas.db` via the existing sql.js path (`getDb('daas')` + `queryAll`) and SHALL NOT spawn `leader-mcp` to render.

#### Scenario: List workflows with last-run summary

- **WHEN** the user visits `/workflows` and `workflows` contains two rows, each with steps and at least one `workflow_runs` row
- **THEN** both workflows are listed ordered by `created_at` descending
- **AND** each row shows its name, description, step count, and the status + start time of its most recent run

#### Scenario: Workflow with no runs

- **WHEN** a workflow exists but has zero `workflow_runs` rows
- **THEN** the list row shows the workflow's step count and a "No runs yet" marker in place of a last-run status

#### Scenario: Empty state when no workflows exist

- **WHEN** the user visits `/workflows` and the `workflows` table is empty
- **THEN** the page renders an empty-state message (e.g. "No workflows yet") instead of a table

#### Scenario: List page renders without leader-mcp

- **WHEN** `leader-mcp` cannot start (e.g. its venv is missing) and the user visits `/workflows`
- **THEN** the page still renders the workflow list from `mcp/daas.db` reads without error

### Requirement: Workflow detail page

The dashboard SHALL provide a `/workflows/[name]` route that resolves a workflow by its unique `name` (`decodeURIComponent`-decoded path param) and renders: the workflow `name` and `description`; the ordered `workflow_steps` (by `sort_order`) showing `sort_order`, `agent`, `request`, `depends_on` (rendered as a comma-joined list), `on_fail`, `model` (or "default: fast" when null), and `enabled`; and a recent-runs table (the most recent N `workflow_runs` rows for that workflow, ordered by `started_at` descending) showing run `id`, `status`, `started_at`, `finished_at`, with each run linking to `/workflows/[name]/runs/[runId]`. When the workflow `name` does not exist, the page SHALL render a clear "workflow not found" state. The page SHALL read directly from `mcp/daas.db` and SHALL NOT spawn `leader-mcp` to render.

#### Scenario: Detail page shows steps and recent runs

- **WHEN** the user visits `/workflows/aapl-due-diligence` for an existing workflow with 3 steps and 2 prior runs
- **THEN** the page renders the 3 steps in `sort_order` with their agent, request, depends_on, on_fail, and model fields
- **AND** the recent-runs table lists the 2 runs newest-first, each linking to its run-detail page

#### Scenario: Null step model is shown as the fast default

- **WHEN** a step has `model = null`
- **THEN** the detail page renders that step's model as "default: fast" (mirroring the runner's null-model-defaults-to-fast-tier semantics)

#### Scenario: Unknown workflow name

- **WHEN** the user visits `/workflows/nope` and no row exists in `workflows` with `name = "nope"`
- **THEN** the page renders a "workflow not found" state and no steps or runs

### Requirement: Run detail page

The dashboard SHALL provide a `/workflows/[name]/runs/[runId]` route that renders one `workflow_runs` row (looked up by `id = runId`, scoped to the workflow named `name`) and its ordered `workflow_step_results` (by `step_sort_order`). For each step result the page SHALL show `step_sort_order`, `status`, `ran_at`, `error` (when present), `meta` (rendered as a small badge when non-null — e.g. a `{"fallback":"direct",...}` or `_truncated` signal), and `output` rendered as pretty-printed JSON in a `<pre>` block. When `output` exceeds a display budget (≈5 KB) the page SHALL render a truncated prefix with a "Show full" control that expands the full payload on demand. When the run or workflow does not exist, the page SHALL render a clear not-found state. The page SHALL read directly from `mcp/daas.db` and SHALL NOT spawn `leader-mcp` to render.

#### Scenario: Run detail shows per-step outputs

- **WHEN** the user visits `/workflows/aapl-due-diligence/runs/42` for a completed run with 2 step results
- **THEN** the page renders the run's `status`, `started_at`, and `finished_at`
- **AND** each step result is listed in `step_sort_order` with its status, ran_at, and pretty-printed JSON output

#### Scenario: Large output is truncated with an expand control

- **WHEN** a step result's `output` is larger than the display budget
- **THEN** the page renders a truncated prefix of the output in a `<pre>` block
- **AND** a "Show full" control is present that, when activated, expands the full `output` payload into the DOM

#### Scenario: Fallback meta is surfaced as a badge

- **WHEN** a step result has `meta = {"fallback":"direct","reason":"crewai unavailable"}`
- **THEN** the page renders a small badge near that step indicating the direct fallback was used (so fallbacks are never silent in the UI)

#### Scenario: Unknown run id

- **WHEN** the user visits `/workflows/aapl-due-diligence/runs/9999` and no `workflow_runs` row has `id = 9999` (or that run belongs to a different workflow)
- **THEN** the page renders a "run not found" state

### Requirement: Trigger a workflow run from the UI

The dashboard SHALL provide a "Run all steps" control on the `/workflows/[name]` page that, when activated, POSTs to `/api/workflows/[name]/runs` with `{mode: "all"}` and triggers `leader-mcp`'s `run_workflow(name)` MCP tool via the existing `getMCPTools()` client. The dashboard SHALL provide a "Run this step" control per step row that POSTs to the same route with `{mode: "step", step_sort_order: <n>}` and triggers `leader-mcp`'s `run_workflow_step(name, step_sort_order)` MCP tool. The API route SHALL await the tool call, then invalidate the dashboard's cached `daas.db` handle (`invalidateDb('daas')`) so the next page render sees the new run/step-result rows, and SHALL return the tool's result (run summary or single-step output). The client SHALL show an in-flight spinner during the call, render any `{error}` inline on failure, and call `router.refresh()` on success so the new run appears in the recent-runs table. The route SHALL return a clear error if `leader-mcp` cannot start or the named workflow does not exist.

#### Scenario: Run all steps creates a run and refreshes the list

- **WHEN** the user clicks "Run all steps" on `/workflows/aapl-due-diligence`
- **THEN** a POST to `/api/workflows/aapl-due-diligence/runs` with `{mode:"all"}` is made
- **AND** the route invokes `leader-mcp`'s `run_workflow(name="aapl-due-diligence")` via `getMCPTools()`
- **AND** the dashboard's cached `daas.db` handle is invalidated so the next render re-reads the file
- **AND** the page refreshes and the new run appears at the top of the recent-runs table

#### Scenario: Run a single step via run_workflow_step

- **WHEN** the user clicks "Run this step" on step `sort_order = 2` of `/workflows/aapl-due-diligence`
- **THEN** a POST to `/api/workflows/aapl-due-diligence/runs` with `{mode:"step", step_sort_order:2}` is made
- **AND** the route invokes `leader-mcp`'s `run_workflow_step(name="aapl-due-diligence", step_sort_order=2)` via `getMCPTools()`
- **AND** the page refreshes and the run (reused `in_progress` or new) reflects the step's result

#### Scenario: Run trigger surfaces leader-mcp errors

- **WHEN** the user clicks "Run all steps" and `leader-mcp` cannot start (e.g. venv missing) or the workflow name does not exist
- **THEN** the API route returns a non-2xx response with an `{error}` body
- **AND** the client renders that error inline without navigating away

#### Scenario: Browsing does not depend on leader-mcp, only triggering does

- **WHEN** `leader-mcp` cannot start and the user browses `/workflows`, `/workflows/[name]`, and `/workflows/[name]/runs/[runId]`
- **THEN** all three pages render their data from `mcp/daas.db` without error
- **AND** only the "Run all steps" / "Run this step" controls fail (with a clear inline error) — the rest of the page remains usable
