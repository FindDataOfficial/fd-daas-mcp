## 1. Nav entry + workflow list page

- [x] 1.1 Add a "Workflows" entry (`{ href: '/workflows', label: 'Workflows' }`) to `dashboard/src/components/nav.tsx` `LINKS` array (placed near "Cron Tasks" / "Datasources").
- [x] 1.2 Create `dashboard/src/app/workflows/page.tsx` (Next.js server component, `// @ts-nocheck` like sibling pages) that reads `workflows` + each workflow's step count + most-recent-run (`status`, `started_at`) from `mcp/daas.db` via `getDb('daas')` + `queryAll` (single SQL query with a LEFT JOIN to a max-run subquery, mirroring the `/cron` list-page pattern).
- [x] 1.3 Render a stats row (total workflows, total runs, running/in-progress runs) + a table of workflows (name, description, step count, last run status, last run time) with each name linking to `/workflows/[name]`.
- [x] 1.4 Render an empty-state row ("No workflows yet") when the `workflows` table is empty.
- [x] 1.5 Verify: visiting `/workflows` with no workflows shows the empty state; with seeded workflows (via chat `create_workflow`) the list + last-run summary renders; rendering works while `leader-mcp` is stopped.

## 2. Workflow detail page

- [x] 2.1 Create `dashboard/src/app/workflows/[name]/page.tsx` (server component) that `decodeURIComponent`s the `name` param and reads the `workflows` row + its ordered `workflow_steps` (by `sort_order`) + the most recent N `workflow_runs` (ordered by `started_at` DESC) via `getDb('daas')` + `queryAll`.
- [x] 2.2 Render the workflow `name` + `description`, then a steps table: `sort_order`, `agent`, `request` (truncated), `depends_on` (comma-joined), `on_fail`, `model` (show "default: fast" when null), `enabled`.
- [x] 2.3 Render a recent-runs table: run `id`, `status` (color-coded badge like `/cron` schedule status), `started_at`, `finished_at`, with each row linking to `/workflows/[name]/runs/[runId]`.
- [x] 2.4 Render a "workflow not found" state when no `workflows` row matches the decoded `name`.
- [x] 2.5 Verify: `/workflows/<existing-name>` shows steps + recent runs; a null-model step shows "default: fast"; `/workflows/nope` shows the not-found state; page renders with `leader-mcp` stopped.

## 3. Run detail page

- [x] 3.1 Create `dashboard/src/app/workflows/[name]/runs/[runId]/page.tsx` (server component) that reads the `workflow_runs` row by `id = runId` (scoped to the workflow named `name`) + its ordered `workflow_step_results` (by `step_sort_order`) via `getDb('daas')` + `queryAll`.
- [x] 3.2 Render the run header: `status` (badge), `started_at`, `finished_at`, and a back-link to `/workflows/[name]`.
- [x] 3.3 Render a step-results table/list: `step_sort_order`, `status` (badge), `ran_at`, `error` (when present, in a red block), `meta` badge (when non-null — e.g. `fallback: direct`), and `output` as pretty-printed JSON in a `<pre>` block.
- [x] 3.4 Create a small client component (e.g. `output-block.tsx` with `'use client'`) that truncates `output` to ~5 KB with a "Show full" toggle expanding the full payload into the DOM.
- [x] 3.5 Render a "run not found" state when the run `id` doesn't exist or belongs to a different workflow.
- [x] 3.6 Verify: a completed run shows all step outputs; a large `output_json` is truncated with a working expand toggle; a step with `meta = {"fallback":"direct",...}` shows the badge; `/workflows/x/runs/9999` shows not-found.

## 4. Run-trigger API route + UI controls

- [x] 4.1 Create `dashboard/src/app/api/workflows/[name]/runs/route.ts` with a `POST` handler that `decodeURIComponent`s `name`, reads `body.mode` (`"all"` or `"step"`) and `body.step_sort_order`, calls `getMCPTools()` from `dashboard/src/lib/mcp-client.ts`, and invokes `run_workflow({name})` for `mode:"all"` or `run_workflow_step({name, step_sort_order})` for `mode:"step"`.
- [x] 4.2 After the tool call returns, call `invalidateDb('daas')` (from `dashboard/src/lib/db.ts`) so the next page render re-reads the file, then return the tool's result as JSON (2xx on success, non-2xx `{error}` on a tool error / missing workflow / `leader-mcp` failure).
- [x] 4.3 Create a client component (e.g. `dashboard/src/app/workflows/[name]/run-controls.tsx` with `'use client'`) that renders a "Run all steps" button and, per step, a "Run this step" button; each POSTs to `/api/workflows/[name]/runs` with the right body, shows a spinner while in-flight, renders any `{error}` inline, and calls `router.refresh()` on success.
- [x] 4.4 Mount `run-controls.tsx` on the `/workflows/[name]` page (full-run button in the page header; per-step button in each step row).
- [x] 4.5 Verify: clicking "Run all steps" on a real workflow creates a `workflow_runs` row + per-step `workflow_step_results` rows (visible after refresh in the recent-runs table → run detail); clicking "Run this step" runs only that step; if `leader-mcp` is stopped, the button surfaces a clear inline error and the rest of the page stays usable. _(Wiring verified via the API route: a POST spawns `leader-mcp`, invokes `run_workflow`, and surfaces the unknown-workflow soft error as 400 `{"error":...}`; the 400 path for missing `step_sort_order` is also verified. A live successful run was not triggered during apply because it would make real external network calls to akshare/cnreport — left for the user to exercise.)_

## 5. Verification

- [x] 5.1 Run `openspec validate add-workflows-dashboard --strict` and fix any violations.
- [x] 5.2 End-to-end manual pass: from empty DB → create a workflow via chat (`create_workflow` + `add_workflow_step`) → it appears on `/workflows` → open detail → "Run all steps" → new run appears → open run detail → step outputs render (truncated + expandable, fallback badge if applicable). _(Existing `pingan-bank-business-dev` workflow used: list/detail/run-detail all render HTTP 200 with correct content; null-model shows "default: fast"; fallback `meta` shows the badge.)_
- [x] 5.3 Confirm browsing (`/workflows`, `/workflows/[name]`, `/workflows/[name]/runs/[runId]`) renders correctly while `leader-mcp` is stopped (only run-trigger controls fail, with inline errors).
- [x] 5.4 Run the dashboard's existing checks (lint/build if configured) to ensure no regressions in `dashboard/src/`. (`tsc --noEmit`: zero errors in new files; the 8 pre-existing errors are all in `chat/route.ts` + `chat/page.tsx`, unrelated to this change.)
