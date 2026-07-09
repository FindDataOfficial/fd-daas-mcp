## 1. Nav entry + process rules list page

- [x] 1.1 Add a "Process" entry (`{ href: '/process/rules', label: 'Process' }`) to `dashboard/src/components/nav.tsx` `LINKS` array (placed near "Workflows" / "Datasources"). Ensure `pathname.startsWith('/process')` marks it active.
- [x] 1.2 Create `dashboard/src/app/process/rules/page.tsx` (Next.js server component, `// @ts-nocheck` like sibling pages) that reads `process_rules` + each rule's `process_results` count from `mcp/daas.db` via `getDb('daas')` + `queryAll` (single SQL query with a correlated subquery/LEFT JOIN for the result count, mirroring the `/workflows` list-page pattern). Wrap the read in try/catch so a missing DB table renders an empty state, not a crash.
- [x] 1.3 Render a "New rule" link to `/process/rules/new` at the top, then a table of rules (name → link to `/process/rules/[name]`, source_table, text_column, model or "default", enabled toggle, last_rowid, result count).
- [x] 1.4 Render an empty-state row ("No rules yet") when `process_rules` is empty.
- [ ] 1.5 Verify: `/process/rules` with no rules shows the empty state; with rules seeded (via chat `create_rule`) the list + result counts render; page renders with `process-mcp` stopped.

## 2. Process rule detail page

- [x] 2.1 Create `dashboard/src/app/process/rules/[name]/page.tsx` (server component) that `decodeURIComponent`s the `name` param and reads the `process_rules` row + the most recent N `process_results` rows (ordered by `run_at` DESC) via `getDb('daas')` + `queryAll`.
- [x] 2.2 Render the rule's full config: `name`, `source_table`, `text_column`, `schema_json` (pretty-printed in a `<pre>`), `prompt`, `model` (or "default"), `max_chars`, `datasource`, `enabled`, `last_rowid`.
- [x] 2.3 Render a recent-results table: `source_rowid`, `model`, `run_at`, and `extracted_json` as pretty-printed JSON in a `<pre>` block, truncated to ~5 KB via a `output-block.tsx`-style client component with a "Show full" toggle (copy `dashboard/src/app/workflows/[name]/runs/[runId]/`'s truncation pattern).
- [x] 2.4 Mount action controls (Run rule, Enable/Disable, Edit, Delete) using a client component (e.g. `rule-controls.tsx` with `'use client'`) that POSTs to `/api/process/rules/[name]` with the right `action` body, shows a spinner while in-flight, renders any `{error}` inline, and calls `router.refresh()` on success. Delete confirms before submission and redirects to `/process/rules` on success.
- [x] 2.5 Render a "rule not found" state when no `process_rules` row matches the decoded `name`.
- [ ] 2.6 Verify: `/process/rules/<existing-name>` shows config + results; a large `extracted_json` is truncated with a working expand toggle; `/process/rules/nope` shows not-found; page renders with `process-mcp` stopped (only action buttons fail when clicked).

## 3. Process indicators list page

- [x] 3.1 Create `dashboard/src/app/process/indicators/page.tsx` (server component) that reads `indicator_rules` + each indicator's latest `observations` value/date (filtered by `source=datasource`, `function_name=function_name`, `indicator=indicator_name`, ordered by `date` DESC) via a single SQL query with correlated subqueries.
- [x] 3.2 Render a "New indicator" link to `/process/indicators/new`, then a table of indicators (name → link to `/process/indicators/[name]`, datasource, op, value_column, indicator_name, enabled toggle, latest value + date or "No observations yet").
- [x] 3.3 Render an empty-state row ("No indicators yet") when `indicator_rules` is empty.
- [ ] 3.4 Verify: `/process/indicators` with no indicators shows empty state; with indicators seeded (via chat `create_indicator` + `run_indicator`) the list + latest observation renders; page renders with `process-mcp` stopped.

## 4. Process indicator detail page with chart

- [x] 4.1 Create `dashboard/src/app/process/indicators/[name]/page.tsx` (server component) that reads the `indicator_rules` row + its `observations` series (filtered by `source=datasource`, `function_name=function_name`, `indicator=indicator_name`, ordered by `date` ASC) via `getDb('daas')` + `queryAll`.
- [x] 4.2 Render the indicator's full config: `name`, `datasource`, `function_name`, `source_table`, `date_column`, `value_column`, `op`, `params_json` (pretty-printed), `indicator_name`, `enabled`.
- [x] 4.3 Render an ECharts line chart of the observation series using `dashboard/src/components/echarts-wrapper.tsx`, capped to the latest 365 points with a count badge ("showing N of M observations"). Pass `[{date, value}]` mapped to ECharts `xAxis`/`series` data.
- [x] 4.4 Render a recent-observations table (most recent N rows ordered by `date` DESC) showing `date` and `value`.
- [x] 4.5 Mount action controls (Run indicator, Enable/Disable, Edit, Delete) using `indicator-controls.tsx` (`'use client'`) that POSTs to `/api/process/indicators/[name]`, with spinner, inline error, `router.refresh()` on success, and delete-confirmation + redirect to `/process/indicators`.
- [x] 4.6 Render an "indicator not found" state when no `indicator_rules` row matches.
- [ ] 4.7 Verify: `/process/indicators/<existing-name>` shows config + chart + table; the chart caps at 365 points with the correct count; an indicator with no observations shows empty states for chart + table; `/process/indicators/nope` shows not-found; page renders with `process-mcp` stopped.

## 5. Rule and indicator create forms

- [x] 5.1 Create `dashboard/src/app/process/rules/new/page.tsx` (server component) that fetches `list_models` and `list_source_tables` via `getMCPTools()` (one spawn on this page only) and reads `scraw_*` table columns via `PRAGMA table_info` through `getDb('daas')`. On spawn failure, degrade to free-text inputs with an inline warning.
- [x] 5.2 Create `dashboard/src/app/process/rules/new/rule-form.tsx` (`'use client'`) with fields: name, source_table (picker), text_column (picker, populated from the chosen source_table's columns), model (picker from `list_models`), max_chars (number, default 12000), enabled (checkbox), and `schema_json` (raw-JSON textarea with live parse-error display that blocks submit on invalid JSON). Submits to `POST /api/process/rules` with `action: "create"`.
- [x] 5.3 Create `dashboard/src/app/process/indicators/new/page.tsx` (server component) that fetches `list_indicator_ops` and `list_source_tables` via `getMCPTools()` and reads source-table columns via `PRAGMA table_info`. On spawn failure, degrade to free-text inputs.
- [x] 5.4 Create `dashboard/src/app/process/indicators/new/indicator-form.tsx` (`'use client'`) with fields: name, datasource, function_name, source_table (picker), date_column + value_column (pickers), op (picker from `list_indicator_ops`), `params_json` (raw-JSON textarea with parse-error display), indicator_name, enabled (checkbox). Submits to `POST /api/process/indicators` with `action: "create"`.
- [ ] 5.5 Verify: filling the create-rule form with a valid schema creates a rule (appears on `/process/rules` after refresh); malformed `schema_json` blocks submit with a parse error; the create-indicator form similarly creates an indicator; both forms degrade to free-text inputs with a warning when `process-mcp` is stopped.

## 6. Process mutation API routes

- [x] 6.1 Create `dashboard/src/app/api/process/rules/route.ts` with a `POST` handler that reads `body.action` (`"create"`) + the rule fields, calls `getMCPTools()`, invokes `create_rule(...)`, then `invalidateDb('daas')`, and returns the tool's result as JSON (2xx on success, non-2xx `{error}` on a tool error / `process-mcp` failure).
- [x] 6.2 Create `dashboard/src/app/api/process/rules/[name]/route.ts` with a `POST` handler that `decodeURIComponent`s `name`, reads `body.action` (`"run"`, `"update"`, `"delete"`, `"toggle"`), and dispatches to `run_rule`, `update_rule`, `delete_rule`, or `update_rule({enabled: !current})` via `getMCPTools()`. After the tool returns, call `invalidateDb('daas')` and return the result as JSON. Return a clear `{error}` (non-2xx) when `process-mcp` is unavailable or the tool errors.
- [x] 6.3 Create `dashboard/src/app/api/process/indicators/route.ts` (`POST`, `action: "create"` → `create_indicator`) mirroring 6.1.
- [x] 6.4 Create `dashboard/src/app/api/process/indicators/[name]/route.ts` (`POST`, `action` ∈ `run`/`update`/`delete`/`toggle` → `run_indicator` / `update_indicator` / `delete_indicator` / toggle) mirroring 6.2.
- [ ] 6.5 Verify: clicking "Run rule" creates `process_results` rows (visible after refresh); "Run indicator" upserts `observations` (chart updates after refresh); toggle flips `enabled`; delete removes the rule/indicator (and cascades `process_results`) and redirects; if `process-mcp` is stopped, every action surfaces a clear inline error and the page stays usable.

## 7. Settings .env write-through

- [x] 7.1 In `dashboard/src/app/api/settings/route.ts`, extend `syncToEnv` into a `syncKeyToEnv(scope, key, value)` that: for `scope === 'global'` line-patches the repo-root `.env` (replace `^KEY=.*$` or append); for a per-MCP scope line-patches `mcp/<scope>/.env` (creating the file on first write). Preserve unmanaged lines (comments, blanks, keys not in the `settings` table).
- [x] 7.2 In the `PUT` handler, call `syncKeyToEnv` for every save (all categories, not just `bootstrap`), and set `restartRequired = true` whenever a `.env` file is touched.
- [x] 7.3 In the `DELETE` handler, after deleting the `settings` row, remove the matching `KEY=...` line from the relevant `.env` file (root or `mcp/<scope>/.env`), preserving unmanaged lines.
- [x] 7.4 Update `dashboard/src/app/settings/page.tsx` so the per-MCP proxy-override section and the runtime-keys section both surface the `restartRequired` hint after save (the existing `SettingsForm` `restartMsg` state already handles this — verify it fires for runtime + per-MCP categories, not just bootstrap).
- [ ] 7.5 Verify: setting `LLM_API_KEY` (runtime) writes `LLM_API_KEY=…` to the repo-root `.env`; setting an `HTTP_PROXY` override scoped to `akshare-mcp` writes to `mcp/akshare-mcp/.env` (file created on first write) and leaves root `.env` unchanged for that key; deleting a synced row removes the line; comments and hand-edited unmanaged keys in `.env` are preserved across all operations; a `restartRequired` banner shows after each save.

## 8. Raw .env editor

- [x] 8.1 Create `dashboard/src/app/api/settings/env/route.ts` with `GET` (return the repo-root `.env` file text as `{content}`; 404 if the file doesn't exist) and `PUT` (replace the repo-root `.env` wholesale from `body.content`; return `{ok: true, restartRequired: true}`). Read/write through `REPO_ROOT` from `dashboard/src/lib/paths.ts`.
- [x] 8.2 Add a "Raw .env editor" section to `dashboard/src/app/settings/page.tsx` rendering the live root `.env` in a `<textarea>` (server-side read of the file to populate the initial value), a warning banner ("Saving here overwrites dashboard-managed lines; the structured table re-syncs managed lines on its next save"), a "Save" button (PUT), and a "Reset from disk" button (re-read).
- [x] 8.3 Use a small client component (`env-editor.tsx` with `'use client'`) for the textarea + Save/Reset buttons: Save PUTs to `/api/settings/env` and shows the `restartRequired` banner; Reset re-`fetch`es GET and repopulates the textarea, discarding unsaved edits.
- [ ] 8.4 Verify: opening the section shows the current root `.env` contents; editing + Save replaces the file (verify by re-reading the file from disk); Reset discards unsaved edits and repopulates from disk; the warning banner is visible; the raw editor covers only the root `.env` (per-MCP files are not editable here).

## 9. Verification

- [x] 9.1 Run `openspec validate add-rules-indicators-env-dashboard --strict` and fix any violations.
- [ ] 9.2 End-to-end manual pass (rules): empty DB → create a rule via `/process/rules/new` → it appears on `/process/rules` → open detail → "Run rule" → new `process_results` rows appear (truncated + expandable) → toggle enabled off/on → delete → redirected to list.
- [ ] 9.3 End-to-end manual pass (indicators): create an indicator via `/process/indicators/new` → open detail → "Run indicator" → `observations` appear in the chart (capped at 365) + table → delete → redirected to list.
- [ ] 9.4 End-to-end manual pass (.env): on `/settings`, set a runtime key (`LLM_API_KEY`) → verify it lands in root `.env`; set a per-MCP `HTTP_PROXY` override → verify it lands in `mcp/<mcp>/.env`; delete a synced row → verify the line is removed; open the raw `.env` editor → edit + Save → verify the file is replaced; Reset → verify it repopulates from disk; confirm a `restartRequired` banner shows after each save.
- [ ] 9.5 Confirm browsing (`/process/rules`, `/process/rules/[name]`, `/process/indicators`, `/process/indicators/[name]`) renders correctly while `process-mcp` is stopped (only mutation controls fail, with inline errors).
- [ ] 9.6 Confirm comments and unmanaged keys in root `.env` and per-MCP `.env` files are preserved across structured saves and deletes.
- [x] 9.7 Run the dashboard's existing checks (lint/build if configured) to ensure no regressions in `dashboard/src/`.
