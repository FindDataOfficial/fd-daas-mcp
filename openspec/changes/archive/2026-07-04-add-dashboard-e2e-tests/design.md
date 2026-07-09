## Context

The dashboard is a Next.js 15 app (App Router, React 19, sql.js reads against `mcp/daas.db`). It already ships Cypress 14 (`dashboard/cypress.config.ts`, `dashboard/cypress/e2e/`) and two passing-by-design spec files. The nav (`dashboard/src/components/nav.tsx`) lists 11 destinations; only 5 have any e2e coverage. The pages under test read `mcp/daas.db` directly via sql.js (`getDb('daas')` + `queryAll`) — the same single DB the MCPs write to — so the suite runs against real, seeded data (agents=11, workflows=1, collections=1, sources=20; process rules/indicators=0).

Three confirmed blockers mean the suite is not runnable today as-is:

1. **Three different ports.** `dashboard/cypress.config.ts` sets `baseUrl: 'http://localhost:3459'`; `dashboard/package.json` `dev` script runs `next dev --port 3000`; root `.env` sets `DASHBOARD_PORT=4000`. There is no script that starts the dashboard on 3459, so `cypress run` against a freshly started dev server hits ECONNREFUSED.
2. **Stale DB assertion.** `dashboard/cypress/e2e/dashboard.cy.ts:11` asserts `cy.contains('leader_mcp.db').should('exist')`. The project consolidated to a single `mcp/daas.db` (per `construction/mcp.md`); `leader_mcp.db` does not exist. That test fails.
3. **No one-command runner.** There is no `test:e2e` that starts the server, waits for readiness, runs Cypress, and tears down — a contributor has to start `next dev` in one terminal and `cypress run` in another, on matching ports, manually.

Constraints: no new heavy dependencies; the suite must stay runnable on a developer laptop without external services (no live MCP server, no LLM keys — pages that need them degrade gracefully and the chat pages already assert only the empty state + input). The dashboard reads `mcp/daas.db` read-only from the browser; specs must not mutate the shared DB (writes go through API routes that spawn `collection_writer.py`, which the suites already exercise for cron/settings).

## Goals / Non-Goals

**Goals:**

- Every nav destination has at least one e2e test asserting the page loads and its primary structural elements render.
- `npm run test:e2e` from `dashboard/` starts the dashboard, waits for it to be ready, runs Cypress headless, exits non-zero on any failure, and tears the server down — no manual terminal juggling.
- The existing two spec files pass against the current `mcp/daas.db` (fix the stale `leader_mcp.db` assertion and any other drift).
- The new specs pass against the current DB state (seeded agents/workflows/collections/sources; empty process rules/indicators) and degrade gracefully against an empty DB.
- One canonical port for dev + test, documented in one place.

**Non-Goals:**

- Full functional CRUD e2e for every form (create/update/delete flows that hit `collection_writer.py` or leader-mcp spawn paths). The existing cron/settings specs already cover the write-path shape; this change covers load + render + nav for the new pages, not a full write-flow matrix. (Targeted create/edit round-trips are in scope only where they are cheap and DB-stateless — e.g. agent `new`/`edit` form renders.)
- Visual / screenshot regression testing.
- Running the suite in CI (GitHub Actions) — out of scope; this change makes the suite *CI-ready* (deterministic, one command) but does not add the workflow file.
- Cross-browser testing (Cypress ships Electron by default; that is sufficient).
- Mocking `mcp/daas.db` — the suite runs against the real repo DB, read-only. Mutating specs reset any rows they create (the existing `settings.cy.ts` already edits runtime env in place; this change does not add new mutating tests beyond what already exists).

## Decisions

### Decision 1 — Unify on port 3459 for the test runner; keep `next dev` on 3000 for ad-hoc dev

**Choice.** Cypress `baseUrl` stays `http://localhost:3459`. The new `test:e2e` script launches `next dev --port 3459` (or `next start` after a build) for the duration of the run. `npm run dev` keeps `--port 3000` so ad-hoc development on 3000 is unaffected. `DASHBOARD_PORT=4000` in root `.env` is left as-is (it is consumed elsewhere if at all; the dashboard's `dev` script does not read it today, and this change does not introduce that coupling).

**Rationale.** Cypress's `baseUrl` is the only thing that must match the running server. Picking 3459 (already in `cypress.config.ts`) means zero churn to the Cypress config. Forcing every contributor onto one canonical port for *dev* would be churn for no guard benefit — the test runner owns its own port.

**Alternatives considered.**
- Unify everyone on 4000 (the `DASHBOARD_PORT` value): rejected — requires editing `cypress.config.ts` *and* `package.json` *and* assumes `DASHBOARD_PORT` is wired into `next dev` (it is not today).
- Unify on 3000: rejected — collides with ad-hoc `next dev` running in another terminal during test runs.

### Decision 2 — `test:e2e` = a per-spec runner script (`scripts/run-e2e.mjs`)

**Choice.** `package.json` gains:

```json
"test:e2e": "node scripts/run-e2e.mjs",
"test:e2e:open": "start-server-and-test 'next dev --port 3459' http://localhost:3459 'cypress open'"
```

`scripts/run-e2e.mjs` is a self-contained Node script (no new deps — only `node:child_process` + `node:fs`) that: starts `next dev --port 3459` as a child process (or reuses one already running on the port), polls `http://localhost:3459` until it returns 2xx, then runs **each spec file in its own `cypress run` invocation** (`cypress run --browser $E2E_BROWSER --spec <file>`), aggregates pass/fail, tears the server down, and exits non-zero if any spec failed. `E2E_BROWSER` env var overrides the browser (default `chrome`). `test:e2e:open` keeps `start-server-and-test` + `cypress open` (interactive mode launches one browser session for the user, so the per-spec split is unnecessary there).

**Rationale (revised during implementation).** The original design used `start-server-and-test 'next dev --port 3459' http://localhost:3459 'cypress run'` (a single `cypress run` for all specs). On this machine (Node 25 + Cypress 14 Electron 130) that failed two ways: (1) the bundled **Electron** browser could not connect to its own Chrome DevTools Protocol (`Cypress failed to make a connection to the Chrome DevTools Protocol after retrying for 50 seconds`) — Node 25 is very new and the bundled Electron does not launch cleanly under it; (2) switching to `--browser chrome` fixed the launch, but Chrome **failed to relaunch between specs** — `cypress run` launches a fresh browser per spec file, and the second spec's browser launch hung (`Timed out waiting for the browser to connect. Retrying...` indefinitely). Running each spec in its own `cypress run` process avoids the within-process relaunch entirely: each process launches Chrome once, runs one spec, and exits. Verified: the per-spec runner completes all 7 specs green where a single `cypress run` (Chrome or Electron) hung on spec 2.

**Why default to `chrome` (not the bundled Electron).** Electron does not launch under Node 25 on this machine (CDP failure). Chrome is installed (`/Applications/Google Chrome.app`) and launches reliably per-spec. A contributor on a standard Node LTS (20/22) can override with `E2E_BROWSER=electron` if they prefer the zero-dep bundled browser. The default prioritizes "works on this machine."

**Alternatives considered.**
- `start-server-and-test` + single `cypress run` (Electron): the original design — rejected, Electron CDP failure under Node 25.
- `start-server-and-test` + single `cypress run --browser chrome`: rejected, between-specs Chrome relaunch hang.
- Cypress `experimentalRunAllSpecs`: rejected after checking Cypress 14 docs — it enables the interactive "Run All Specs" UI for `cypress open`, not headless `cypress run`. `experimentalSingleTabRunMode` is component-only. Neither applies.
- Custom Node script with `spawn` + `fetch` loop for server readiness + per-spec `spawnSync('cypress', ...)`: **chosen** — same idea as `start-server-and-test` but with the per-spec loop that avoids the relaunch hang.

**Dependency cost.** Zero new npm deps (the script uses only Node built-ins). `start-server-and-test` remains a devDependency for `test:e2e:open`.

### Decision 3 — One spec file per nav area; tests assert load + render, not row content

**Choice.** Five new spec files, named by nav area: `collections.cy.ts`, `workflows.cy.ts`, `agents.cy.ts`, `process.cy.ts`, `scores.cy.ts`. Each test asserts (a) the route responds 200, (b) the page's `h1` / heading renders the expected title, (c) one or two primary structural elements exist (table, form, button), (d) nav links to/from the page work. Tests do **not** assert specific row counts or row names unless the row is part of seeded fixture data that the test itself relies on (e.g. the seeded agents are not asserted by name — the list page is asserted to render a table, and if rows exist, to render them).

**Rationale.** Row-content assertions are brittle (they break the moment seed data drifts) and are not what e2e is for here — the goal is "did this page render without throwing". The pages already wrap DB reads in `try/catch` and render an empty state, so "page loads with empty table" is a meaningful, stable assertion.

**Alternatives considered.**
- One mega-spec: rejected — slow, fails-whole-file semantics, hard to navigate.
- Per-route files (`agents.new.cy.ts`, `agents.edit.cy.ts`, …): rejected — 20 files for ~5 areas is over-granular; one file per area with multiple `it()` blocks is the Cypress convention and matches the existing `dashboard.cy.ts` / `settings.cy.ts` shape.

### Decision 4 — Fix the stale assertion; add a `databases` sanity check that survives DB drift

**Choice.** In `dashboard.cy.ts`, replace `cy.contains('leader_mcp.db').should('exist')` with an assertion that the `daas.db` row renders (the single-DB truth), and assert the table list is non-empty without hard-coding a second DB name. Keep the rest of the file's intent.

**Rationale.** The assertion was written when the dashboard listed multiple DB files; the unified-DB migration (`construction/mcp.md`) removed `leader_mcp.db` but the test was not updated. The fix is one line; the alternative (delete the assertion) loses coverage of "the databases list renders a known DB".

### Decision 5 — Empty-state and error-state assertions for the process pages

**Choice.** `process.cy.ts` explicitly covers both the empty state (current DB: 0 rules, 0 indicators → assert the empty-state copy and the "New rule" / "New indicator" buttons render) and the `new` / `[name]` / `[name]/edit` sub-routes (assert the form renders; do not submit, since there is no seeded rule to navigate to for `[name]`). The `[name]` route is exercised by visiting a known-seeded path only if a row exists; otherwise the test asserts the `new` route's form and skips the detail route with a `cy.skip()`-style guard.

**Rationale.** The process pages are empty today; a test that requires a seeded rule would fail or require a mutating setup step. Asserting the empty state is more valuable (it guards the "DB read returned [] → render empty state" branch) and stays green as seed data is added later.

## Risks / Trade-offs

- **[Risk] Tests depend on `mcp/daas.db` being non-corrupt and present.** If a contributor wipes `mcp/daas.db`, the dashboard's `getDb` throws inside `try/catch` and pages render their empty/error state — the tests assert "page renders", so they still pass, but a test that specifically asserts seeded data (the `databases` list has `daas.db`) would fail. → *Mitigation:* the `daas.db` file is checked into the repo and is the single source of truth for all MCPs; wiping it is not a supported state. The few assertions that depend on seeded data are limited to `databases` (has `daas.db`) and `agents` (table renders; not row-count-dependent).
- **[Risk] `next dev` first-build is slow (~10-30s) under Cypress's default 30s command timeout.** → *Mitigation:* `start-server-and-test` polls the URL *before* launching Cypress, so Cypress never starts until the server returns 2xx. `defaultCommandTimeout: 30000` (already set) covers in-page waits.
- **[Risk] New dev dependency `start-server-and-test` may not be in `package-lock.json`.** → *Mitigation:* added via `npm install --save-dev` in the tasks; lockfile updated in the same commit.
- **[Trade-off] Specs do not exercise write flows on the new pages.** A regression in `POST /api/agents` would not be caught by `agents.cy.ts` (it only loads the list/new/edit forms). → *Accepted:* the write path is shared infrastructure (`collection_writer.py` sidecar / leader-mcp spawn), already guarded by the existing `settings.cy.ts` write tests and the Python self-checks. Adding full CRUD e2e per page is a follow-up.
- **[Trade-off] Running against the real `mcp/daas.db` means a flaky test could be caused by a concurrent MCP write.** → *Accepted:* local dev is single-user; CI (future) would snapshot the DB. Not worth mocking for the local-runner goal.
- **[Risk] A page renders but throws a console error (e.g. a hydration warning) that does not fail the test.** → *Mitigation:* enable Cypress's `onLog`/`onError` capture for uncaught exceptions in a `supportFile` (currently `supportFile: false`). Decision: do **not** add a support file in this change (keeps scope small); instead, manually verify each new spec in `cypress open` during implementation and fix any uncaught-error page bugs surfaced. If a page does throw, fix the page (in scope per proposal).

## Migration Plan

1. Add `start-server-and-test` devDependency; update `package.json` scripts.
2. Fix `dashboard.cy.ts:11` stale assertion.
3. Add the 5 new spec files (one PR / one branch).
4. Run `npm run test:e2e` locally; fix any page-level bugs the specs surface (e.g. a route that 500s under Cypress).
5. Commit lockfile + specs + fixes together.

**Rollback.** Revert the commit. The new devDependency is dev-only and isolated; removing the spec files and the `test:e2e` script restores the prior state with no data or schema impact.

## Open Questions

- Should the `test:e2e` script run against `next dev` (fast feedback, no build step) or `next build && next start` (production-render path)? *Default: `next dev` — matches the existing `dev` workflow and avoids a multi-minute build per run. Revisit if a prod-only rendering bug slips through.*
- Should the suite snapshot/restore `mcp/daas.db` before/after the run to guarantee a clean state? *Default: no — the tests are read-only by design and do not depend on a specific row count. Add a snapshot if a future write-flow test lands.*
