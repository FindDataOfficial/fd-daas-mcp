## Why

The dashboard has grown to 11 nav destinations and ~20 routes, but e2e coverage is only two spec files (`dashboard.cy.ts`, `settings.cy.ts`) that together exercise ~5 destinations (databases, cron, datasources, chat, settings). The newer pages — collections, workflows, agents, process rules, process indicators, scores — ship with **zero** e2e guard, so regressions land silently. Worse, running the existing suite today fails before any new test runs: Cypress's `baseUrl` is `http://localhost:3459` while `npm run dev` starts Next.js on `3000` and root `.env` sets `DASHBOARD_PORT=4000` (three different ports), and `dashboard.cy.ts:11` asserts a `leader_mcp.db` row that no longer exists in the single-DB world (`mcp/daas.db` is the only database). This change closes the coverage gap and makes the suite green so it can actually guard future work.

## What Changes

- **New e2e spec files** for the untested pages, one per area, each asserting "page loads, core elements render, empty/seeded state is handled, primary nav works":
  - `collections.cy.ts` — `/collections` picker, `/collections/manage`, `/collections/[name]` three-pane workspace (catalog · collection · chat).
  - `workflows.cy.ts` — `/workflows` stats + list, `/workflows/[name]` step list + run history, `/workflows/[name]/runs/[runId]` per-step results.
  - `agents.cy.ts` — `/agents` list (seeded: 11 agents), `/agents/new` form, `/agents/[name]` detail, `/agents/[name]/edit` form.
  - `process.cy.ts` — `/process/rules` + `/process/indicators` lists (empty-state today), the `new` / `[name]` / `[name]/edit` sub-routes for each.
  - `scores.cy.ts` — `/scores` default-scores table + collection-scores section.
- **Fix the port mismatch**: align Cypress `baseUrl`, the `dev`/`start` port, and `DASHBOARD_PORT` to a single value, and add a `test:e2e` npm script that starts the dashboard on the Cypress-expected port, waits for it to be ready, runs Cypress headless, and tears it down. Add a `test:e2e:open` variant for the interactive runner.
- **Fix the stale `leader_mcp.db` assertion** in `dashboard.cy.ts` (the single-DB world only has `daas.db`) and tighten any other assertion that depends on a since-removed table/row.
- **Empty-state guards**: the new specs pass against the current DB (process rules/indicators are empty; the rest are seeded) and against a fresh DB with no rows — they assert the page renders, not that specific rows exist, unless the row is part of seeded fixture data.
- No production code changes unless a page fails to render under Cypress (e.g. a hydration error or an unhandled thrown error surfaces); those are fixed in-page as part of this change.

## Capabilities

### New Capabilities

- `dashboard-e2e-tests`: End-to-end (Cypress) coverage of the dashboard — every nav destination loads and its core elements render under a real browser, a one-command `test:e2e` script starts the dashboard and runs the suite headless, and the suite is green against the current `mcp/daas.db` (including the empty-state pages). Covers CI-readiness: deterministic, no manual server start, no stale assertions.

### Modified Capabilities

None — the e2e tests verify existing UI capabilities (`collection-dashboard-ui`, `workflow-dashboard-ui`, `specialist-agents-dashboard-ui`, `process-dashboard-ui`, `score-dashboard-ui`) but do not change their requirements.

## Impact

- `dashboard/cypress/e2e/`: +5 spec files (`collections.cy.ts`, `workflows.cy.ts`, `agents.cy.ts`, `process.cy.ts`, `scores.cy.ts`); edit `dashboard.cy.ts` to drop the stale `leader_mcp.db` assertion; edit `settings.cy.ts` to drop the stale `Live` badge assertion and account for the restart-warning modal staying open after a save (ponytail-cuts behavior).
- `dashboard/cypress.config.ts`: `baseUrl` port 3459 left unchanged.
- `dashboard/scripts/run-e2e.mjs`: new self-contained Node script (no new deps) — starts `next dev` on the Cypress port, waits for readiness, runs each spec in its own `cypress run` process (avoids a between-specs browser-relaunch hang seen with a single `cypress run`), aggregates results, tears the server down. Browser overridable via `E2E_BROWSER` (default `chrome`).
- `dashboard/package.json`: add `test:e2e` (`node scripts/run-e2e.mjs`) and `test:e2e:open` (`start-server-and-test … 'cypress open'`) scripts; the existing `test` / `test:open` remain as `cypress run` / `cypress open`.
- Root `.env`: `DASHBOARD_PORT=4000` left as-is (not wired into `next dev`); the test runner owns port 3459.
- No backend / MCP changes. No schema changes. Tests read `mcp/daas.db` via the running dashboard only — no direct DB mutation from specs (the existing `settings.cy.ts` write tests mutate the `settings` table + `.env` as before — a pre-existing side effect, unchanged by this work).
