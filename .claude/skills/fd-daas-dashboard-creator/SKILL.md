---
name: fd-daas-dashboard-creator
description: Build a dashboard for daas data as a single standalone HTML file — propose a name + introduction + structure, validate the source data, build the HTML with ECharts and interactive entity + time filters, offer to open it, iterate on changes, then register the dashboard in the `dashboards` DB table (which regenerates the charts index). Use this skill whenever the user wants to visualize daas data / indicators / scraw tables as a dashboard — phrases like "给这些指标做一个看板", "build a dashboard for these indicators", "画一个图看看这个 scraw 表", "visualize this series", "做个图表", or any daas data + "dashboard / chart / visualize / 看板 / 图表". Do NOT use this skill to OPEN or FIND an existing dashboard (use fd-daas-dashboard for that), or for the Next.js dashboard app at dashboard/ (that app already exists and is untouched), or to create indicators/cron (use fd-daas-indicators-creator); this skill only builds standalone HTML dashboards under dashboard/my-charts-dashboard/, and writes a companion instruction md under daas-doc/ (or under the workflow dir when nested in fd-daas-workflow-creator).
---

# fd-daas-dashboard-creator

Build a standalone HTML dashboard for daas data. Each dashboard is one self-contained HTML file at `dashboard/my-charts-dashboard/<slug>.html`, rendered with **ECharts** (vendored locally) and carrying interactive **entity + time-range filters**. The existing Next.js `dashboard/` app is **untouched** — no new routes, no `dashboard/src/app/...` pages. Every dashboard's metadata (name, introduction, source tables, entity/time scope, refresh cadence, chart config, file url) is registered in the `dashboards` table in `mcp/daas.db` via `mcp__dashboard-mcp__register_dashboard`; that call also regenerates `dashboard/my-charts-dashboard/index.html` + `daas.md` from the DB, so the charts index can never drift from the registry.

## Mental model

Seven steps, with two gates before any state mutates:

1. **Propose structure** as markdown — a human-readable **name**, a one-paragraph **introduction**, the charts/tables, the **entity scope**, the **time range**, and the refresh cadence.
2. **Permission gate** — ask the user to accept before doing anything.
3. **Validate source data** — fetch the rows and confirm they actually cover the requested entities + time range + columns before baking. Gate: shortfalls surface to the user (skip / widen / abort); empty data aborts.
4. **Build** — write `dashboard/my-charts-dashboard/<slug>.html` with ECharts + entity/time filters + the validated data baked as JSON.
5. **Open** — offer to open in the default browser.
6. **Iterate then register** — change loop → accept → call `register_dashboard` (writes the DB row + regenerates `index.html`/`daas.md`).
7. **Write instruction md** — companion `<slug>-dashboard.md` under `daas-doc/` (standalone) or the workflow dir (when nested).

Never write files or call MCP tools that mutate state before step 2's permission is granted. Never bake data before step 3's validation passes (or the user explicitly decides how to handle a shortfall).

## Step 1 — Propose the structure (name + introduction + entity/time scope)

Goal: agree on what the dashboard shows — in human terms — before building.

1. Read the data the user wants to visualize. Call `mcp__dashboard-mcp__query_table` with `database="daas"`, `table="<scraw_slug or observations>"`, `limit=20` to see the shape. For indicators, `mcp__daas-mcp__list_indicators` + `get_indicator` give the binding (which `source_table` + `value_column` + `op`).
2. Draft the structure as markdown in the conversation, with ALL of these:
   - **Name** — a short, human-readable title the user will recognize later, e.g. "比亚迪日行情 + 5日均线" (not just the slug). This is what shows up in the charts index and the `dashboards` table.
   - **Introduction** — one paragraph: what the dashboard shows, over which entities and time, and why someone would look at it. This is recorded in the DB so the `fd-daas-dashboard` skill can answer "what dashboards do we have" by intro.
   - **Charts** — one entry per chart: ECharts type (line / bar / candlestick / scatter / pie), source table + column(s), x-axis, which entity field and date field drive the filters.
   - **Tables** — raw data tables (which `scraw_<slug>`, which columns, how many rows shown).
   - **Entity scope** — which entities/codes the dashboard covers (e.g. `["600519","000858"]`), or "unscoped" if it's a single aggregate.
   - **Time range** — the start/end dates the user wants to see (e.g. `2024-01-01` to `2024-12-31`), or "latest N days".
   - **Refresh cadence** — static snapshot vs. refreshed by a cron (note the cron name if one exists from `fd-daas-indicators-creator`).
3. Show the draft and ask: "Does this look right — name, intro, entity/time scope, and charts? I'll validate the data and build once you confirm."

## Step 2 — Permission gate

Do NOT write any file, bake any data, or mutate any state until the user accepts the proposed structure (name + intro + entity/time scope + charts). If the user requests changes, revise the draft and re-ask. If the user declines, stop.

## Step 3 — Validate the source data

Goal: make sure the data you're about to bake actually matches what the dashboard claims to show. A dashboard with empty series or a missing entity fails silently and misleads — catch it here.

1. Fetch the rows you'll chart via `mcp__dashboard-mcp__query_table` against each source table (limit high enough to cover the time range, e.g. `limit=1000`). **Stale-DB fallback**: if `query_table` returns `no such table` for a `scraw_*` table you know exists, `dashboard-mcp` is reading its own stale local `daas.db`. Fall back to a direct `python3 -c "import sqlite3,json; ..."` one-liner against `<repo-root>/mcp/daas.db`, and tell the user `dashboard-mcp` needs a restart (the repo-root URL fix is in place, but a running process may predate it).
2. Check the fetched rows against the proposed structure:
   - **Columns** — every column a chart needs exists in the source table.
   - **Entity coverage** — every entity in the proposed entity scope has at least one row. List which entities are missing.
   - **Time range** — the rows actually fall within the proposed time range (note the real min/max date).
   - **Row count** — non-zero overall (and per entity, if multi-entity).
3. Surface a **coverage summary** to the user: "Fetched N rows over D1–D2 for entities X, Y (M of K requested). Columns: …"
4. **On any shortfall** (a missing entity, zero rows in the time range, a missing column): do NOT silently bake partial data. Tell the user what's missing and ask how to proceed — skip the missing entity / widen the time range / abort. Re-validate after their choice.
5. **On empty** (zero rows total): abort the build with a clear message naming the source table and the filter that produced no rows. Do not write an HTML file.

Only proceed to Step 4 once validation passes (or the user has explicitly chosen skip/widen for each shortfall).

## Step 4 — Build the standalone HTML (ECharts + entity/time filters)

Goal: one self-contained HTML file at `dashboard/my-charts-dashboard/<slug>.html` that renders with ECharts and lets the user filter by entity and time client-side.

1. **Slug**: derive a kebab-case `<slug>` from the dashboard name (e.g. "比亚迪日行情 + 5日均线" → `byd-daily-sma5`). The filename MUST match `^[A-Za-z0-9_-]+$`.
2. **Ensure ECharts is vendored locally.** The page loads ECharts from `dashboard/my-charts-dashboard/vendor/echarts.min.js` via a relative `<script src="vendor/echarts.min.js">` — NOT from a CDN. Reason: dashboards open via `file://` in environments where CDNs (jsdelivr, unpkg, cdnjs) are blocked by a proxy or firewall, and a `<canvas>` whose ECharts lib never loads fails *silently* (blank space, no error). A locally vendored file renders with zero network. Ensure the file exists:
   - If `dashboard/my-charts-dashboard/vendor/echarts.min.js` already exists, reuse it.
   - If not, fetch it once: `curl -fsSL https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js -o dashboard/my-charts-dashboard/vendor/echarts.min.js` (create `vendor/` first). This is a one-time bootstrap; the file is then committed.
   - If the fetch fails (offline), tell the user to download `echarts.min.js` (v5) into `dashboard/my-charts-dashboard/vendor/` manually, and stop. Do not fall back to a CDN `<script>` — that reintroduces the silent-failure mode.
3. **First-run scaffolding**: if `dashboard/my-charts-dashboard/` does not exist, create it (and `vendor/`). You do NOT seed `index.html` or `daas.md` here — Step 6's `register_dashboard` regenerates them from the DB.
4. **Bake the validated data** from Step 3 into the HTML as `<script id="dashboard-data" type="application/json">…</script>`. The JSON should be the rows the charts need, keyed so the filter logic can slice by entity + date (e.g. `{"entities":["600519","000858"],"series":{"600519":[{date,close,ma5},…],…}}`). Baking (not fetching client-side) is required because `file://` pages can't fetch.
5. **Write the HTML** using `references/template.html` as the starting point. It MUST include:
   - `<script src="vendor/echarts.min.js"></script>` (relative).
   - The baked JSON blob.
   - An **entity filter**: a `<select id="entity-select">` with one `<option>` per covered entity.
   - A **time-range filter**: start + end `<input type="date">` (or `<input type="text">` for `YYYY-MM-DD`), defaulting to the dashboard's full range.
   - A small `<script>` that, on any filter change, slices the baked JSON by the selected entity + [start,end] and calls `chart.setOption({...})` on every chart to re-render — no page reload, no network fetch.
   - One or more `<div id="chart-N">` containers initialized with `echarts.init`.
6. Report the file path + the `file://` URL to the user.

A CDN chart lib or CSS-only bar divs are NOT acceptable chart methods for new dashboards. ECharts (vendored) is the constraint. See `references/template.html` for a copy-pasteable line + table example with the filter wiring.

## Step 5 — Open in the default browser

Offer to open the dashboard. On macOS (the project host is darwin): `open <file-url or path>`. **Ask permission first** — do not auto-launch.

- Accept → run `open dashboard/my-charts-dashboard/<slug>.html` (or the `file://` URL), confirm the browser launched.
- Decline → print the path/URL and don't launch.

## Step 6 — Iterate then register (in the database)

Goal: let the user request changes; on accept, register the dashboard in the `dashboards` table.

1. After the first build (and any open), ask: "Want any changes, or does this look good?"
2. **Changes**: apply them, re-validate (Step 3) if the data scope moved, re-write the HTML, re-offer to open. Loop until the user accepts.
3. **Accept**: register the dashboard by calling `mcp__dashboard-mcp__register_dashboard` with:
   - `slug` — the kebab slug.
   - `name` — the human-readable name from Step 1.
   - `intro` — the introduction paragraph from Step 1.
   - `source_tables` — JSON list of the backing tables, e.g. `["scraw_byd_daily","observations"]`.
   - `entity_coverage` — JSON list of entities, e.g. `["600519","000858"]`, or `null` if unscoped.
   - `time_range` — JSON `{"start":"2024-01-01","end":"2024-12-31"}`, or `null`.
   - `refresh_cadence` — the cadence string from Step 1.
   - `chart_config` — JSON structural description of the charts, e.g. `[{"type":"line","source_table":"scraw_byd_daily","x":"date","y":["close","ma5"],"filterable":true}]`. (A structural description, NOT a full ECharts option blob — keeps the DB row small and lets the `fd-daas-dashboard` skill summarize the charts.)
   - `file_path` — `dashboard/my-charts-dashboard/<slug>.html`.
   - `file_url` — the absolute `file://` URL.
   `register_dashboard` upserts by slug (idempotent — re-accepting an already-registered dashboard updates the row, no duplicate) AND regenerates `dashboard/my-charts-dashboard/index.html` + `daas.md` from the DB.
4. Confirm to the user: "Registered `<slug>` in the `dashboards` table; `index.html` + `daas.md` regenerated. Open or find it later via the `fd-daas-dashboard` skill."

## Step 7 — Write the dashboard instruction md

Goal: leave a human-readable companion doc alongside the HTML.

1. **Path resolution**:
   - **Standalone** (no `workflow-name <X>` token in this skill's `args`): write to `daas-doc/dashboard/<slug>-dashboard.md`. Create `daas-doc/dashboard/` on first use.
   - **Nested inside `fd-daas-workflow-creator`** (the invoker passed `workflow-name <X>` in `args`): write to `daas-doc/<X>/<slug>-dashboard.md`. Create `daas-doc/<X>/` if missing.
2. **Content** — plain markdown, no JS, mirroring the DB row so the doc and the registry stay consistent:
   - `# <Name>` + the dashboard slug.
   - The **introduction** paragraph (same as the DB `intro`).
   - `file://` URL of the built HTML.
   - **Entity coverage** + **time range** (the scope a user can filter within).
   - Source tables + columns backing each chart (`scraw_*` / `observations`).
   - Refresh cadence — static snapshot vs cron (name the cron if wired).
   - A one-line "how to refresh" note.
3. Report the instruction-md path to the user (in addition to the HTML path).

This is additional to (not a replacement for) the HTML build + DB registration in step 6. See `construction/daas-doc.md` for the shared layout.

## Gotchas

- **No Next.js route.** The existing `dashboard/` Next.js app is untouched. Dashboards are standalone HTML only. If the user asks for a route inside the Next.js app, redirect them — this skill doesn't do that.
- **ECharts is the constraint; vendor it locally.** New dashboards MUST render charts with ECharts loaded from `dashboard/my-charts-dashboard/vendor/echarts.min.js` (relative `<script src>`). Do not use a CDN `<script>` (silent failure behind proxies) and do not fall back to CSS-only bar divs (no interactivity, can't do candlesticks/linked charts). Ensure the vendored file exists before building (Step 4.2). The existing `vendor/chart.umd.min.js` is Chart.js, used only by the two legacy dashboards — leave it; new dashboards add `vendor/echarts.min.js` alongside it.
- **Entity + time filters are mandatory.** Every dashboard bakes its data as JSON and wires a `<select>` (entities) + date inputs (time range) that re-render via `chart.setOption`. A single-entity dashboard still has the `<select>` (one option) and the time filter. Without this the user can't explore — and the data is already baked, so filtering is free.
- **Validate before you bake.** Step 3 exists because a dashboard with a missing entity or an empty time range looks fine but lies. Always fetch + check coverage first; surface shortfalls; abort on empty. Never bake partial data silently.
- **`dashboard-mcp` "no such table" gotcha**: if `mcp__dashboard-mcp__query_table` returns `no such table` for a `scraw_*` table you know exists, `dashboard-mcp` is reading a stale DB (a running process that predates the repo-root URL fix, or `DAAS_DATABASE_URL` unset). Fall back to a `python3 -c "import sqlite3,json; ..."` one-liner against `<repo-root>/mcp/daas.db` to fetch the rows for validation + baking. Tell the user to restart `dashboard-mcp`. The new `register_dashboard` / `list_dashboards` / `get_dashboard` / `search_dashboards` tools resolve the URL correctly, so registration is unaffected.
- **Registration lives in the DB, not the files.** `index.html` + `daas.md` are regenerated from the `dashboards` table by `register_dashboard` — never hand-edit or hand-append them. Rollback for a dashboard = `mcp__dashboard-mcp__delete_dashboard("<slug>")` (removes the row + regenerates the index) + `rm dashboard/my-charts-dashboard/<slug>.html` + removing the companion `daas-doc/.../<slug>-dashboard.md`.
- **`chart_config` is structural, not an ECharts option.** Store `[{type, source_table, x, y, filterable}]` in the DB, not the full `chart.setOption` payload — the DB row stays small and the `fd-daas-dashboard` skill can describe the charts without rendering ECharts.
- **Instruction md is a companion, not a replacement.** Always build the standalone HTML at `dashboard/my-charts-dashboard/<slug>.html` + register it in the DB (step 6), THEN write the companion instruction md under `daas-doc/` (step 7). When nested inside `fd-daas-workflow-creator` (signaled by a `workflow-name <X>` token in `args`), write the instruction md under `daas-doc/<X>/` instead of `daas-doc/dashboard/`. The token is the only nesting signal.
- **To open or find an existing dashboard, use `fd-daas-dashboard`.** That skill lists/searches the `dashboards` table, shows a dashboard's intro + data lineage, and opens it. This skill only builds new ones.
