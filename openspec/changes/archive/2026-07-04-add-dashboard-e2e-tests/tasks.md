## 1. Unbreak the existing suite

- [x] 1.1 In `dashboard/cypress/e2e/dashboard.cy.ts`, replace the stale `cy.contains('leader_mcp.db').should('exist')` assertion (line 11) with an assertion that the `daas.db` row renders, without hard-coding a second DB name.
- [x] 1.2 Audit `dashboard.cy.ts` and `settings.cy.ts` for any other assertion referencing a since-removed table/row/route; fix or drop each.
- [x] 1.3 Confirm `dashboard/cypress.config.ts` `baseUrl` port (3459) is the canonical test port; leave it unchanged.

## 2. Add the one-command test runner

- [x] 2.1 Add `start-server-and-test` as a devDependency (`npm install --save-dev start-server-and-test` from `dashboard/`); commit the updated `package.json` + `package-lock.json`.
- [x] 2.2 Add `test:e2e` script: `start-server-and-test 'next dev --port 3459' http://localhost:3459 'cypress run'`.
- [x] 2.3 Add `test:e2e:open` script: `start-server-and-test 'next dev --port 3459' http://localhost:3459 'cypress open'`.
- [x] 2.4 Keep the existing `test` / `test:open` aliases as `cypress run` / `cypress open` (assumes a server is already up on 3459).

## 3. Add e2e specs for untested pages

- [x] 3.1 Create `dashboard/cypress/e2e/collections.cy.ts`: visit `/collections` (assert picker + list/empty state), `/collections/manage` (assert management UI renders), `/collections/<name>` for a seeded collection (assert three-pane workspace: catalog · collection · chat renders).
- [x] 3.2 Create `dashboard/cypress/e2e/workflows.cy.ts`: visit `/workflows` (assert Workflows heading + table + stats render), `/workflows/<name>` for the seeded workflow (assert steps + run history render), and assert nav from `/databases` via the "Workflows" sidebar link.
- [x] 3.3 Create `dashboard/cypress/e2e/agents.cy.ts`: visit `/agents` (assert Specialist Agents heading, "New agent" link, agents table renders against the 11 seeded agents), `/agents/new` (assert new-agent form fields render), `/agents/<name>` and `/agents/<name>/edit` for one seeded agent (assert detail + edit form render).
- [x] 3.4 Create `dashboard/cypress/e2e/process.cy.ts`: visit `/process/rules` (assert heading + "New rule" link + empty-state UI), `/process/indicators` (assert heading + "New indicator" link + empty-state UI), `/process/rules/new` + `/process/indicators/new` (assert forms render; do not submit).
- [x] 3.5 Create `dashboard/cypress/e2e/scores.cy.ts`: visit `/scores` (assert default-scores table renders + collection-scores section renders; if a collection is seeded, assert its items load).
- [x] 3.6 Add a nav-walk test across the newly-covered destinations (e.g. `/databases` → Workflows → `/workflows`; `/cron` → Collections → `/collections`).

## 4. Run the suite and fix surfaced errors

- [x] 4.1 Run `npm run test:e2e` from `dashboard/`; capture every failure (page 500, missing element, hydration/throw).
- [x] 4.2 For each failing spec: triage whether the failure is a test bug (fix the spec) or a page bug (fix the page — e.g. an uncaught throw in a `page.tsx`, a broken `try/catch`, a wrong selector).
- [x] 4.3 Fix page-level bugs surfaced by the new specs (in scope per proposal); prefer minimal fixes that make the page render its intended state under Cypress.
- [x] 4.4 Re-run `npm run test:e2e` until the full suite is green (0 failures).

## 5. Verification

- [x] 5.1 Run `npm run test:e2e` once more from a clean state (no pre-running server); confirm it starts the server, runs every spec green, and tears the server down (no orphan `next` process).
- [x] 5.2 Spot-check `npm run test:e2e:open` opens the interactive runner against the running server.
- [x] 5.3 Confirm the `dashboard/cypress/e2e/` directory now has 7 spec files (2 existing + 5 new) and all pass.
- [x] 5.4 Update `CLAUDE.md` / construction docs only if a run instruction changed (port, script name) — otherwise leave docs untouched.
