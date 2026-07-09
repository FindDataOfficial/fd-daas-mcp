## Context

`fd-daas-dashboard-creator` (`.claude/skills/fd-daas-dashboard-creator/`) builds standalone HTML dashboards under `dashboard/my-charts-dashboard/<slug>.html`. Today it (a) records dashboard metadata by hand-appending to two text files (`index.html` + `daas.md`) with no queryable registry, (b) defaults to offline CSS bar divs and treats a CDN chart lib as an optional enhancement, and (c) has no entity or time filtering — every dashboard is a static snapshot. The existing `vendor/chart.umd.min.js` is Chart.js, used by the two hand-built dashboards (`us-leaders-trend-monitor.html`, `market-data-full.html`).

The shared schema package `mcp/models/` already holds 40+ tables across all MCP domains, all created via `Base.metadata.create_all` (additive, no Alembic). `dashboard-mcp` already reads `mcp/daas.db` via `DAAS_DATABASE_URL` and exposes `query_table` (with a known stale-DB gotcha: it doesn't resolve a relative URL against the repo root, so it sometimes reads its own `mcp/dashboard-mcp/daas.db`). The `entities` table (stocks + countries) already exists for entity scoping.

The user wants: dashboard metadata in the DB (queryable), ECharts as the mandated charting tech, interactive entity + time filters, and a data-validation gate — plus a companion `fd-daas-dashboard` "use" skill built via `fd-skill-creator`.

## Goals / Non-Goals

**Goals:**
- A `dashboards` table in `mcp/daas.db` is the single source of truth for dashboard metadata (name, slug, intro, source tables, entity/time coverage, refresh cadence, chart config, file path/url).
- `dashboard-mcp` CRUD tools over that table; `index.html` + `daas.md` regenerated from the DB (idempotent).
- `fd-daas-dashboard-creator` captures a human-readable name + introduction, mandates ECharts (vendored locally), bakes data as JSON with interactive entity + time filters, and validates the source data before build.
- A new `fd-daas-dashboard` skill (built via `fd-skill-creator`) lets AI list/search/open existing dashboards and query their backing data.

**Non-Goals:**
- Rewriting the two existing Chart.js dashboards (`us-leaders-trend-monitor.html`, `market-data-full.html`) to ECharts. They are backfilled into the registry as-is; only new dashboards use ECharts.
- Streaming / live-updating dashboards. Data is baked at build time; filters are client-side over the baked JSON.
- The Next.js `dashboard/` app. Untouched. The new `fd-daas-dashboard` skill covers standalone HTML dashboards only.
- A full `fd-skill-creator` eval loop (subagents + `claude -p` + benchmark viewer) as a blocker. We draft the use skill + lightweight manual test; the full eval loop is offered as a follow-up.

## Decisions

### Decision 1: DB table as single source of truth (drop `dashboards.json`)
The `dashboards` table replaces the earlier `dashboards.json` idea. **Why:** the project's unified-DB philosophy (`mcp/daas.db` holds every MCP domain); MCP tools can query it directly; AI reads it via `dashboard-mcp` tools rather than parsing a file; and there's no three-way drift between JSON + `index.html` + `daas.md` — the two HTML/markdown files are *derived* from the DB on every write. **Alternative considered:** `dashboards.json` as source + regenerate the two files — rejected because it duplicates the registry outside the DB and can't be queried by MCP tools. **Alternative considered:** hand-append `index.html`/`daas.md` only (status quo) — rejected: not queryable, drifts, no intro field.

### Decision 2: `Dashboard` model lives in the shared `mcp/models/` package
Add `class Dashboard(Base)` to `mcp/models/models.py` + export from `__init__.py`, created via `Base.metadata.create_all`. **Why:** matches the 40+ table pattern; every MCP and the dashboard share one `Base`; additive (no migration of existing tables). Columns: `id, name, slug (UNIQUE), intro (Text), source_tables (JSON), entity_coverage (JSON nullable), time_range (JSON nullable), refresh_cadence (String), chart_config (JSON), file_path (String), file_url (String), created_at, updated_at`. **Alternative:** a dashboard-mcp-local model — rejected because the shared package is the project's one-schema rule.

### Decision 3: `dashboard-mcp` owns the CRUD tools
Add `register_dashboard` / `list_dashboards` / `get_dashboard` / `search_dashboards` / `update_dashboard` / `delete_dashboard` to `dashboard-mcp`. **Why:** it's the "dashboard" MCP and already reads `mcp/daas.db`; the use skill and creator skill both call it. **Alternative:** put them in `daas-mcp` — rejected: `daas-mcp` is source/registry/indicator-focused; dashboard metadata is a dashboard-mcp concern. The new tools resolve a relative `DAAS_DATABASE_URL` against the repo root (mirroring `daas_database.py`'s fix) so they hit the canonical DB — this also fixes the stale-DB gotcha for the new tool surface.

### Decision 4: ECharts vendored locally; CSS bars dropped as the baseline
The creator skill must use ECharts loaded from `dashboard/my-charts-dashboard/vendor/echarts.min.js` via a relative `<script src>`. **Why:** user mandate + offline robustness — a CDN `<script>` fails silently behind proxies (the old skill's whole reason for CSS bars), but a locally vendored file renders via `file://` with zero network. **Alternative:** keep CSS bars as default — rejected (user wants ECharts; CSS bars can't do interactive filters, candlesticks, linked charts). **Alternative:** CDN ECharts — rejected (silent-failure mode). The skill ensures `vendor/echarts.min.js` exists (one-time `curl https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js`); if offline, it tells the user to drop the file there manually. Chart.js (`vendor/chart.umd.min.js`) stays for the existing dashboards — the two libs coexist under different filenames.

### Decision 5: Entity + time filters via baked JSON + `chart.setOption`
The fetched rows are baked into the HTML as a `<script id="dashboard-data" type="application/json">…</script>` blob (multi-entity × time series). A `<select>` of entities + start/end date inputs filter the baked JSON client-side and call `chart.setOption` to re-render every chart. **Why:** standalone `file://` pages can't fetch; the data must be in the file. `setOption` is ECharts' idiomatic update path (no full re-init). **Alternative:** server-side render per filter — rejected (no server for `file://`).

### Decision 6: Data-validation gate before build
After the user accepts the structure, the skill queries the source table(s) via `mcp__dashboard-mcp__query_table` (falling back to a `sqlite3` one-liner when dashboard-mcp hits its stale-DB gotcha) and checks: expected columns present, every requested entity has rows, rows fall in the requested time range, row count > 0. It surfaces a coverage summary and, on any shortfall, asks the user (skip / widen / abort) before baking. **Why:** "确保展示和获取的数据符合要求" — catch empty/missing data before it becomes a blank dashboard. The `sqlite3` fallback is the same workaround the current skill documents for the dashboard-mcp gotcha.

### Decision 7: `chart_config` stores a structural description, not a full ECharts option
The `chart_config` JSON column stores a structural description per chart (`{type, source_table, x_column, y_columns, entity_field, date_field, filterable}`) that the skill expands into an ECharts option at build time. **Why:** keeps the DB row small and human-readable; the use skill can summarize "what charts are in this dashboard" without rendering ECharts. **Alternative:** store the full ECharts option JSON — rejected (large, opaque, couples the DB to a specific ECharts version).

### Decision 8: `fd-daas-dashboard` built via `fd-skill-creator` methodology
The use skill is authored by following `fd-skill-creator/SKILL.md` (capture intent → draft SKILL.md → 2-3 test prompts → review → iterate). The full eval loop (subagents + benchmark viewer + description-optimization via `claude -p`) is offered as a follow-up, not a blocker — it needs subagents and `claude -p` which may be unavailable. **Why:** the user explicitly asked to use `fd-skill-creator`; its draft→test→review core works everywhere, the heavy eval machinery is optional.

## Risks / Trade-offs

- **[ECharts vendor file size ~1 MB, git-tracked]** → acceptable; one-time; `vendor/` is already git-tracked (Chart.js is there). Add a `.gitignore` exception if needed.
- **[dashboard-mcp stale-DB gotcha bites the new tools too]** → the new CRUD tools resolve the relative URL against the repo root (mirroring daas-mcp). The creator skill's *data fetch* still keeps its `sqlite3` fallback documented in the gotcha.
- **[Baked JSON gets large for many entities × long history]** → mitigate: cap rows per entity (e.g. last N dates), aggregate, or warn the user. Streaming is a non-goal.
- **[Mixing Chart.js (existing) + ECharts (new) under `vendor/`]** → fine; different filenames (`chart.umd.min.js` vs `echarts.min.js`). Existing dashboards keep loading Chart.js; new ones load ECharts.
- **[Existing dashboard backfill is metadata-only]** → `us-leaders-trend-monitor` gets a `dashboards` row but its HTML stays Chart.js. Documented as a non-goal; a later change can rebuild it to ECharts.
- **[fd-skill-creator eval loop unavailable in some environments]** → fall back to manual review of test prompts; the skill still ships.

## Migration Plan

1. Add `Dashboard` model to `mcp/models/models.py` + `__init__.py`.
2. Add the 6 CRUD tools + `index.html`/`daas.md` regen + repo-root URL resolution to `dashboard-mcp`.
3. One-time backfill script: insert a `dashboards` row for `us-leaders-trend-monitor` (name + intro + source + refresh from the existing `daas.md` row; `chart_config` as a structural description), then regenerate `index.html` + `daas.md` from the DB.
4. Rewrite `fd-daas-dashboard-creator/SKILL.md` + `references/template.html` (ECharts + filters + validation + DB registration).
5. Author `fd-daas-dashboard/SKILL.md` via `fd-skill-creator` methodology.
6. Manual smoke: build one new ECharts dashboard end-to-end (propose → validate → build → register → open); list/search it via the use skill.

**Rollback:** drop the `dashboards` table (`DROP TABLE dashboards`), revert `dashboard-mcp` server.py, revert the two skill dirs. The existing `us-leaders-trend-monitor.html` is never modified, so rollback leaves it intact.

## Open Questions

- **Filter behavior for single-entity snapshot dashboards** — resolved: filters are always present; a single-entity dashboard's entity `<select>` has one entry, and the time filter still applies. No special-casing.
- **Should `register_dashboard` accept a `score`/priority like the datasource registry?** — out of scope for this change; can be added later if dashboards need ordering beyond `created_at`.
- **Full `fd-skill-creator` eval loop for `fd-daas-dashboard`** — deferred; ship the draft + manual test first, offer the eval loop as a follow-up task.
