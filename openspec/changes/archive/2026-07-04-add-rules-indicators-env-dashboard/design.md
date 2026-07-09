## Context

`process-mcp` (spec: `process-mcp-server` + `process-mcp-indicators`) persists two replayable artifacts in `mcp/daas.db`:
- **LLM extraction rules** — `process_rules` (name, source_table, text_column, schema_json, prompt, model, max_chars, enabled, last_rowid, datasource) → `process_results` (rule_id, source_table, source_rowid, extracted_json, model, run_at). Tools: `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, plus ad-hoc `extract_*`. Identifier guard validates `^[A-Za-z_][A-Za-z0-9_]*$` on dynamic table/column names.
- **Math indicators** — `indicator_rules` (name, datasource, function_name, source_table, date_column, value_column, op, params_json, indicator_name, enabled) → `observations` (source, function_name, indicator, date, value, metadata) upserts keyed on `(source, function_name, indicator, date)`. Tools: `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`, `calculate`. Plus `list_models`, `list_source_tables`, `list_indicator_ops`.

There is no dashboard surface for either — every other MCP domain (Cron, Datasources, Databases, Collections, Workflows) has one. The `/workflows` page (change `add-workflows-dashboard`) is the direct template: sql.js reads for list/detail, `getMCPTools()` for the run trigger, nav entry, `invalidateDb` after mutations.

Separately, the `/settings` page (code at `dashboard/src/app/settings/page.tsx` + `dashboard/src/app/api/settings/route.ts`) manages env vars in a `settings` table but only syncs the two `bootstrap` keys to root `.env` (via `syncToEnv`). Runtime keys (`LLM_*`, proxy, `CKAN_URL`) and per-MCP overrides live only in the DB; MCPs read `.env` at startup (root first, then `mcp/<mcp>/.env` with `override=True`) and never see dashboard changes. So the page cannot actually "define the `.env` file."

The dashboard already has the building blocks: sql.js reads (`dashboard/src/lib/db.ts` → `getDb('daas')` + `queryAll` + `invalidateDb`), interactive client components that `fetch` to `/api/...` then `router.refresh()` (e.g. `cron/schedule-list.tsx`), an MCP client singleton (`dashboard/src/lib/mcp-client.ts` → `getMCPTools()`), an `echarts-wrapper.tsx` component, and a nav (`dashboard/src/components/nav.tsx`).

Constraint: rule/indicator **execution** (LLM extraction, indicator math, `observations` upsert, identifier validation, schema enforcement) lives inside `process-mcp`. The dashboard must not reimplement it. Constraint: `.env` is read by MCPs only at startup, so writes are restart-required.

## Goals / Non-Goals

**Goals:**
- A `/process/rules` list page + `/process/rules/[name]` detail page (config, recent `process_results` with pretty-printed/truncated `extracted_json`, run/toggle/edit/delete actions).
- A `/process/indicators` list page + `/process/indicators/[name]` detail page (config, recent `observations`, an ECharts line chart of the series, run/toggle/edit/delete actions).
- Create-rule and create-indicator forms (model/source-table/op pickers, raw-JSON schema/params textarea) proxying to `create_rule` / `create_indicator`.
- Browsing (list/detail) works from direct `daas.db` reads without requiring `process-mcp` to start; only mutations spawn it.
- The `/settings` page writes every managed key through to the real `.env` file(s) — root `.env` for globals, `mcp/<mcp>/.env` for per-MCP overrides — so the dashboard is the source of truth for `.env`.
- A raw root-`.env` text editor on `/settings` (textarea, save, reset-from-disk).
- A "Process" nav entry.

**Non-Goals:**
- A visual JSON-Schema builder (v1 uses a raw-JSON textarea + parse-error display).
- Scheduling rules/indicators from this page (already solved via `--run-rule`/`--run-indicator` CLI branches + `cron-mcp`; `/cron` covers it).
- A top-level observations browser route (observations are viewed on the indicator detail page, filtered to that indicator).
- Editing `PROCESS_MODELS` / `LEADER_MODELS` JSON blobs from the UI (use chat for now).
- Raw editors for per-MCP `.env` files (per-MCP overrides are edited via the structured per-MCP table; only root `.env` gets a raw editor in v1).
- Auth / permissions (the dashboard has none today).

## Decisions

### Decision 1: Read path = sql.js direct reads (not MCP tools)

List and detail pages read `process_rules`, `process_results`, `indicator_rules`, and `observations` directly via `getDb('daas')` + `queryAll`.

**Why:** Matches the established `/workflows`, `/cron`, `/datasources` pattern. The tables are ours and simple. Spawning `process-mcp` (a stdio subprocess) on every page render would add cold-start latency and a failure mode that doesn't exist for `/workflows`. The MCP read tools (`list_rules`, `get_rule`, `list_indicators`, `get_indicator`) also don't surface `process_results` or `observations` — a single SQL join gets results/series cheaper than extra round-trips.

**Alternatives considered:**
- `getMCPTools()` for reads — rejected: subprocess spawn cost per render, and the tools don't expose result/observation listings.
- Adding new read-only MCP tools (`list_results`, `list_observations`) — rejected: unnecessary; the dashboard already reads sibling tables directly.

### Decision 2: Mutations = `process-mcp` tools via `getMCPTools()` (not direct SQL, not CLI branches)

Create/update/delete/run/toggle all go through `process-mcp`'s tools (`create_rule`, `update_rule`, `delete_rule`, `run_rule`, `create_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`) via the existing `getMCPTools()` singleton, exposed through new `/api/process/*` routes.

**Why:** Only `process-mcp` validates identifiers (`^[A-Za-z_][A-Za-z0-9_]*$`), enforces the JSON schema, runs the LLM extraction (chunked map-reduce, model registry), computes indicators (pandas), and upserts `observations`. Reimplementing any of that in the dashboard would duplicate and drift. `getMCPTools()` is already wired (used by chat) and reuses one cached subprocess.

**Alternatives considered:**
- Direct SQL writes — rejected: skips identifier validation, schema enforcement, and execution entirely (no extraction, no indicator math, no `observations` upsert).
- CLI branches `--run-rule` / `--run-indicator` — kept for `cron-mcp` scheduling, but rejected for the dashboard: they only *run* (no create/update/delete), and spawning a fresh venv'd Python process per action is heavier than the cached MCP client.

### Decision 3: Route structure = `/process/rules` + `/process/indicators` under one "Process" nav entry

Detail routes key off the rule/indicator unique `name` (`uq_process_rule_name` / `uq_indicator_rule_name`), mirroring `/workflows/[name]` and `/collections/[name]`.

**Why:** Rules and indicators are two domains of one MCP; grouping under `/process` keeps the nav to one new entry (the nav is already 8 items) while giving each domain its own list/detail URLs (shareable, refreshable). Names are unique and the MCP tools take `name`, so no id→name lookup.

**Alternatives considered:**
- Top-level `/rules` + `/indicators` (two nav entries) — rejected: nav bloat.
- A single `/process` page with tabs — rejected: detail views need their own URLs for sharing/refresh; tabs force a single-page design that doesn't scale to detail pages.

### Decision 4: Create/edit forms use a raw-JSON textarea for schema + params (no visual builder in v1)

The create-rule form has fields for name, source_table (picker), text_column (picker), model (picker from `list_models`), max_chars, enabled, and `schema_json` as a raw-JSON textarea with a parse-error display. The create-indicator form has name, datasource, function_name, source_table (picker), date_column + value_column (pickers), op (picker from `list_indicator_ops`), `params_json` (raw-JSON textarea), indicator_name, enabled.

**Why:** A visual JSON-Schema builder is substantial UI; `create_rule` / `create_indicator` accept JSON directly; a textarea + parse-error display is enough for v1 and matches the power-user audience that already authors rules via chat.

**Alternatives considered:**
- Visual schema builder — rejected: out of scope for v1; the raw JSON is what the MCP tool stores anyway.
- Chat-only creation — rejected: the user explicitly asked to "manage" rules and indicators from the page.

### Decision 5: Create-form pickers fetched via `getMCPTools()` on the create-form page

The create form needs `list_models` (LLM registry), `list_source_tables` (`scraw_*` tables), and `list_indicator_ops` (fixed op catalog). These are fetched server-side via `getMCPTools()` when the create-form page renders.

**Why:** These are dynamic (models from env, source tables from `sqlite_master`, ops from the process-mcp catalog) and fetching them via the MCP tool avoids drift. The spawn cost is paid only on the create-form page (not the list/detail pages), and only when the user clicks "New" — acceptable for an interactive action.

**Alternatives considered:**
- Read `sqlite_master` for `scraw_*` directly in sql.js + hardcode the op catalog — rejected: hardcoding the op catalog drifts from `process-mcp`'s `list_indicator_ops`; mixing sources is uglier than one spawn.
- Cache the lists in the `settings` table — rejected: stale-prone; not worth it for v1.

### Decision 6: Indicator series chart = ECharts via existing `echarts-wrapper.tsx`, capped to latest N points

The indicator detail page renders the `observations` series for that indicator (filtered `WHERE source=datasource AND function_name=function_name AND indicator=indicator_name`, ordered by `date`) as a line chart using the existing `echarts-wrapper.tsx`, capped to the latest 365 points with a count badge.

**Why:** `echarts-wrapper.tsx` already exists in the dashboard; observations are a `(date, value)` series; a line chart is the clearest way to see an indicator. The cap bounds DOM/render cost for long-running indicators.

**Alternatives considered:**
- Plain table only — rejected: a chart is the natural view for a time series and a cheap win given the component exists.
- A separate top-level observations browser — rejected (Non-Goal): scoped to the indicator detail page.

### Decision 7: `.env` write-through = extend `syncToEnv` (line-patch + remove-on-delete) to all categories + per-MCP files

The existing `syncToEnv(key, value)` in `dashboard/src/app/api/settings/route.ts` line-patches root `.env` (replace if the key exists, else append). This change extends it to: (a) all categories (not just `bootstrap`) for global scope → root `.env`; (b) per-MCP scope → `mcp/<mcp>/.env` (created on first write, holding only the override `KEY=value` lines); (c) on delete from the `settings` table, remove the corresponding `.env` line. Unmanaged lines (comments, blanks, hand-added keys not in the `settings` table) are preserved.

**Why:** The `settings` table is already the UI's source of truth; line-patching (not full regeneration) preserves hand-edited structure and comments. Per-MCP `.env` files hold only overrides (loaded after root with `override=True` per `construction/mcp.md`), so they're small. Removing on delete keeps `.env` consistent with the table.

**Alternatives considered:**
- Full regeneration of `.env` from the `settings` table on every save — rejected: clobbers comments and any hand-edited unmanaged keys; line-patch is safer.
- Line-patch in place (current behavior, bootstrap only) — rejected: doesn't cover runtime keys or per-MCP, so MCPs never see dashboard changes (the bug this change fixes).

### Decision 8: Raw `.env` editor = full-file read/replace via `GET/PUT /api/settings/env`, root only

A new section on `/settings` renders the live root `.env` in a textarea. `GET /api/settings/env` returns the file text; `PUT /api/settings/env` replaces it wholesale. A "Reset from disk" button re-reads. A banner warns that saving here overwrites dashboard-managed lines and that the structured table re-syncs on its next save.

**Why:** Power users want to see/edit the whole file; it's also an escape hatch for keys the structured forms don't cover. Root only for v1 (per-MCP overrides are edited via the structured per-MCP table).

**Trade-off:** a raw save can clobber dashboard-managed lines. → Mitigation: warning banner + the structured table is still the source of truth for the UI (the next structured save re-writes managed lines via `syncToEnv`).

### Decision 9: `restartRequired` hint on every `.env` write

Every `PUT /api/settings` and `PUT /api/settings/env` that touches a `.env` file returns `restartRequired: true`; the settings form surfaces a "Restart MCPs for changes to take effect" message (the existing `restartMsg` state in `settings-form.tsx`).

**Why:** MCPs load `.env` only at startup (root then per-MCP with `override=True`). Without the hint, users would expect live effect. The flag already exists for `bootstrap`; this extends it to all `.env` writes.

## Risks / Trade-offs

- **Stale reads after a mutation** — `run_rule` / `run_indicator` / create/update/delete write via `process-mcp` (a separate process), and the dashboard's sql.js DB is cached in-process (`dbCache` in `db.ts`). → Mitigation: every `/api/process/*` mutation route calls `invalidateDb('daas')` after the tool returns, so `router.refresh()` re-reads fresh data. (Mirrors the `add-workflows-dashboard` pattern.)
- **`.env` write clobbers hand-edited content** — a raw save or a sync could overwrite a user's manual `.env` edits. → Mitigation: structured sync only touches lines whose key is in the managed set (preserves comments, blanks, and unmanaged keys); the raw editor shows a warning banner; the managed-key set is documented in the page. On delete, only the matching `KEY=...` line is removed.
- **`.env` changes need MCP restart** — users may expect live effect. → Mitigation: `restartRequired` banner on every save (Decision 9); documented in the settings page.
- **`process-mcp` unavailable when mutating** — browsing still works (sql.js reads), but create/run/edit/delete fail. → Mitigation: the API route returns a clear `{error}`; the client surfaces it inline. List/detail pages render with `process-mcp` stopped (only mutation controls fail).
- **Large `extracted_json` in DOM** — `process_results.extracted_json` could be large (LLM output). → Mitigation: truncate to a display budget (≈5 KB) with a "Show full" toggle, mirroring `add-workflows-dashboard`'s `output-block.tsx`.
- **Observations series size** — a long-running indicator could have thousands of points. → Mitigation: chart capped to the latest 365 points with a count badge; the table shows the most recent N rows.
- **Create-form spawn cost** — rendering the create form spawns `process-mcp` for `list_models` / `list_source_tables` / `list_indicator_ops`. → Mitigation: only the create-form page spawns (list/detail don't); acceptable for an interactive action. If the spawn fails, the form degrades to free-text inputs with an inline warning.

## Migration Plan

- **Process pages**: additive only — new files under `dashboard/src/app/process/` + new `/api/process/*` routes + one nav line. No DB migration (`process_rules`, `process_results`, `indicator_rules`, `observations` already exist). No `process-mcp` change, no `.mcp.json` change.
- **`.env` editor**: modifies the existing `dashboard/src/app/settings/page.tsx` (raw-editor section + per-MCP write-through UI) and `dashboard/src/app/api/settings/route.ts` (extend `syncToEnv` to all categories + per-MCP + remove-on-delete) in place; adds `dashboard/src/app/api/settings/env/route.ts`. The `settings` table schema is unchanged; existing rows are preserved. The first save after deploy writes through to `.env` for all categories (idempotent line-patch).
- **Deploy:** `dashboard/` rebuilds on next `next dev` / `next build`; nothing else restarts. MCPs pick up `.env` changes on their next restart.
- **Rollback:** revert the dashboard files. `.env` files keep their last-written state (no automatic undo — the structured table still holds the values, so a re-deploy re-syncs).

## Open Questions

- **Raw editor scope** — root `.env` only, or also per-MCP? → Resolved: root only for v1 (per-MCP overrides are edited via the structured per-MCP table; a per-MCP raw editor is a follow-up if needed).
- **Top-level observations browser** — separate route or indicator-detail only? → Resolved: indicator-detail only for v1 (a filtered view); a top-level browser is a follow-up if users need cross-indicator comparison.
- **`list_indicator_ops` drift** — fetch live vs. hardcode? → Resolved: fetch live via `getMCPTools()` on the create-form page (Decision 5) to avoid drift.
