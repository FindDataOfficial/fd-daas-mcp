## Why

The `fd-daas-dashboard-creator` skill today stores dashboard metadata in two hand-appended text files (`index.html` + `daas.md`), defaults to offline CSS bar charts with no interactivity, and has no entity or time filtering. That makes dashboards hard for AI to discover or reuse (no queryable registry), limits them to static snapshots, and gives no guarantee the baked data actually matches what the dashboard claims to show. We need dashboard metadata in the shared `mcp/daas.db` (queryable by a companion "use" skill), ECharts as the mandated charting tech, interactive entity + time-range filtering, and a data-validation gate before build.

## What Changes

- **ADD a `dashboards` table** to the shared schema (`mcp/models/`) as the single source of truth for dashboard metadata: human-readable name, slug, introduction, source tables, entity/time coverage, refresh cadence, ECharts chart config, file path + `file://` URL, timestamps. Created via `Base.metadata.create_all` (additive, no Alembic) — same pattern as the other 40+ tables.
- **ADD dashboard-registry CRUD tools to `dashboard-mcp`**: `register_dashboard`, `list_dashboards`, `get_dashboard`, `search_dashboards`, `update_dashboard`, `delete_dashboard`, backed by the new table. `index.html` + `daas.md` are **regenerated from the DB** on each register (no more hand-append, no three-way drift). dashboard-mcp resolves `DAAS_DATABASE_URL` against the repo root so the new tools hit the canonical DB (fixes the known stale-DB gotcha).
- **MODIFY `fd-daas-dashboard-creator`**:
  - Capture a **human-readable name** and an **introduction paragraph** at the propose-structure step, confirmed by the user before build.
  - **Register metadata into the `dashboards` DB table** via `mcp__dashboard-mcp__register_dashboard` (replaces the `index.html`/`daas.md` append).
  - **Constrain chart rendering to ECharts** — vendor `echarts.min.js` locally under `dashboard/my-charts-dashboard/vendor/` (one-time fetch; relative `<script src>`), replacing the CSS-bars-as-default philosophy. CSS bars are dropped as the baseline.
  - Add **interactive entity + time-range filters** that re-render ECharts from data baked as a JSON `<script>` blob (multi-entity × time series, filtered client-side via `chart.setOption`).
  - Add a **data-validation gate** before baking: verify the fetched rows cover the requested entities, fall in the requested date range, and carry the expected columns; surface a coverage summary + discrepancies to the user and ask how to proceed (skip / widen / abort) when requirements aren't met.
  - Keep: standalone HTML at `dashboard/my-charts-dashboard/<slug>.html`, the permission gate, open-in-browser offer, iterate loop, and the companion instruction md under `daas-doc/`.
- **ADD `fd-daas-dashboard` skill** (built via `fd-skill-creator`): helps AI **use** existing standalone HTML dashboards — list/search the `dashboards` table by keyword (name/intro/source), show a dashboard's intro + data lineage + entity/time coverage, open it in the browser, and query the data backing it via `mcp__dashboard-mcp__query_table`. Scope is standalone HTML dashboards only (not the Next.js `dashboard/` app).
- **Migrate** the one existing dashboard (`us-leaders-trend-monitor`) into the new `dashboards` table (one-time backfill script).

## Capabilities

### New Capabilities
- `dashboard-registry`: The `dashboards` DB table + `dashboard-mcp` CRUD tools that back both skills. The DB is the single source of truth; `index.html` + `daas.md` are regenerated from it.
- `fd-daas-dashboard`: The new "use a dashboard" skill — list/search/open standalone HTML dashboards and query their backing data.

### Modified Capabilities
- `fd-daas-dashboard-creator`: Captures name + introduction; registers into the `dashboards` DB table (not file append); mandates ECharts; adds entity + time-range filters; adds a data-validation gate before build.

## Impact

- **Code**:
  - `mcp/models/models.py` + `mcp/models/__init__.py` — new `Dashboard` model + export.
  - `mcp/dashboard-mcp/server.py` (+ a small `dashboard_database.py` if needed) — 6 CRUD tools + `index.html`/`daas.md` regen; repo-root URL resolution.
  - `.claude/skills/fd-daas-dashboard-creator/SKILL.md` + `references/template.html` — ECharts + filters + validation rewrite.
  - `.claude/skills/fd-daas-dashboard/` — new skill (built via `fd-skill-creator`).
  - One-time migration script for `us-leaders-trend-monitor`.
- **Dependencies**: ECharts JS bundled locally into `dashboard/my-charts-dashboard/vendor/echarts.min.js` (one-time `curl` from jsdelivr; manual fallback if offline). No new Python dep (SQLAlchemy already present).
- **Systems / DB**: `mcp/daas.db` gains a `dashboards` table (additive — no existing data moved). dashboard-mcp must read the canonical `DAAS_DATABASE_URL` for the new tools to work.
- **Specs**: adds `dashboard-registry` + `fd-daas-dashboard`; modifies `fd-daas-dashboard-creator`.
