## 1. Shared schema — `Dashboard` model

- [x] 1.1 Add `class Dashboard(Base)` to `mcp/models/models.py` with columns: `id, name, slug (UNIQUE), intro (Text), source_tables (JSON), entity_coverage (JSON nullable), time_range (JSON nullable), refresh_cadence (String), chart_config (JSON), file_path (String), file_url (String), created_at, updated_at`. Follow the existing model style (docstring, `__tablename__ = "dashboards"`).
- [x] 1.2 Export `Dashboard` from `mcp/models/__init__.py` (add to the import list + a `# dashboards` section comment).
- [x] 1.3 Verify `Base.metadata.create_all` creates the `dashboards` table on a temp DB (quick `python3 -c` check importing `from models import Dashboard, Base`).

## 2. `dashboard-mcp` — registry CRUD tools + index/daas.md regen

- [x] 2.1 Add a repo-root URL resolver to dashboard-mcp's DB connect (mirror `daas_database.py._resolve_database_url`) so a relative `sqlite:///mcp/daas.db` resolves to `<repo-root>/mcp/daas.db`. Reuse the existing `mcp/models` `Base`.
- [x] 2.2 Implement `register_dashboard(slug, name, intro, source_tables, entity_coverage?, time_range?, refresh_cadence, chart_config, file_path, file_url)` — upsert by `slug` (insert or update), then regenerate `index.html` + `daas.md`.
- [x] 2.3 Implement `list_dashboards()` → every row's `name, slug, intro, file_url`.
- [x] 2.4 Implement `get_dashboard(slug)` → full row (incl. `source_tables, entity_coverage, time_range, refresh_cadence, chart_config`); not-found returns a clear error.
- [x] 2.5 Implement `search_dashboards(keyword)` → case-insensitive match against `name + intro + source_tables` (JSON text), return `name, slug, intro`.
- [x] 2.6 Implement `update_dashboard(slug, **fields)` — patch provided fields, bump `updated_at`, regenerate `index.html` + `daas.md`.
- [x] 2.7 Implement `delete_dashboard(slug)` — remove the row, regenerate `index.html` + `daas.md`.
- [x] 2.8 Implement `_regenerate_index_and_daas()` — read all `dashboards` rows ordered by `created_at`, write `dashboard/my-charts-dashboard/index.html` (the existing styled scaffold with one `<li><a>` per row) and `daas.md` (the `| Title | Intro | URL | Source | Refresh |` table). Idempotent (full rewrite, no append).
- [x] 2.9 Add an offline self-check (`selfcheck_dashboards.py`) with a temp DB: register → get → search → update → list → delete, asserting index.html + daas.md reflect each state; verify relative-URL resolution points at the repo-root DB.

## 3. Migration — backfill the existing dashboard

- [x] 3.1 Write `mcp/dashboard-mcp/backfill_dashboards.py`: read the existing `dashboard/my-charts-dashboard/daas.md` row for `us-leaders-trend-monitor`, derive `name/intro/source_tables/refresh_cadence/file_path/file_url`, set `chart_config` to a structural description (its charts), and `register_dashboard` it. Idempotent (upsert by slug). `--dry-run` supported.
- [x] 3.2 Run the backfill; verify `list_dashboards` returns 1 row and `index.html` + `daas.md` are regenerated unchanged (same content, now DB-derived).

## 4. `fd-daas-dashboard-creator` skill rewrite

- [x] 4.1 Rewrite `.claude/skills/fd-daas-dashboard-creator/SKILL.md` Step 1 (Propose): the proposal now includes a human-readable **name**, a one-paragraph **introduction**, the **entity scope**, and the **time range**, confirmed at the permission gate. Update the `description` frontmatter to keep trigger phrasing.
- [x] 4.2 Add a new **Step 2.5 — Validate source data** between the permission gate and the build: query via `mcp__dashboard-mcp__query_table` (with the `sqlite3` one-liner fallback for the stale-DB gotcha), check columns/entities/time-range/row-count, surface a coverage summary, and ask skip/widen/abort on shortfalls. Abort on empty.
- [x] 4.3 Rewrite Step 3 (Build): mandate **ECharts** loaded from `vendor/echarts.min.js` (relative `<script src>`); ensure the file exists (one-time `curl` from jsdelivr; manual-fallback message if offline); bake the validated rows as a `<script type="application/json">` blob; drop the CSS-bars-as-default language and the CDN-optional language.
- [x] 4.4 Add the **entity filter** (`<select>` of covered entities) and **time-range filter** (start/end date inputs) to the build step, with a small client-side JS snippet that filters the baked JSON and calls `chart.setOption` on every chart on change. No network fetch on filter change.
- [x] 4.5 Rewrite Step 5 (Register): on accept, call `mcp__dashboard-mcp__register_dashboard` with slug, name, intro, source_tables, entity_coverage, time_range, refresh_cadence, chart_config, file_path, file_url. Remove the hand-append to `index.html`/`daas.md` (dashboard-mcp regenerates them). Note a `mcp/daas.db` row IS now written.
- [x] 4.6 Replace `references/template.html` with an ECharts template: vendored `echarts.min.js` relative include, a `<select>` + date inputs, a JSON blob, a `setOption`-based render+filter script, and one line + one table chart. Keep the "why this pattern" comment header (updated for ECharts + offline vendor).
- [x] 4.7 Update the **Gotchas** section: remove the "CSS bars are the default" gotcha; keep the dashboard-mcp stale-DB gotcha (now also mitigated for the new CRUD tools by repo-root resolution, but the *data-fetch* `query_table` path still needs the `sqlite3` fallback); add a gotcha that `vendor/echarts.min.js` must exist locally (offline fallback).
- [x] 4.8 Update the companion instruction-md step (Step 6) to also record the dashboard's `name` + `intro` + `entity_coverage` + `time_range` (mirroring the DB row) so the `daas-doc/` doc and the DB row stay consistent.

## 5. `fd-daas-dashboard` use skill (via `fd-skill-creator`)

- [x] 5.1 Invoke the `fd-skill-creator` skill to author `fd-daas-dashboard`: capture intent (list/search/open/query-backing-data for standalone HTML dashboards; read-only), draft `.claude/skills/fd-daas-dashboard/SKILL.md` with frontmatter `name` + a pushy `description` (triggers on "打开看板 / show me the dashboard / 我们有哪些看板 / what data backs …"; does NOT trigger on build intent).
- [x] 5.2 Draft the SKILL.md body: list (`mcp__dashboard-mcp__list_dashboards`), search (`search_dashboards`), get metadata (`get_dashboard` — intro + source + entity/time coverage + refresh + file_url), open (`open <file_url>`, ask permission), query backing data (`mcp__dashboard-mcp__query_table` on the recorded source_tables), and a redirect-to-creator rule for build/edit/delete intent.
- [x] 5.3 Write 2-3 realistic test prompts (e.g. "我们有哪些看板", "打开 leaders 那个看板", "BYD 有没有看板"), run them manually (or via subagents if available), and iterate on the SKILL.md from the results.
- [x] 5.4 (Optional follow-up) Offer the full `fd-skill-creator` eval loop (subagents + benchmark viewer + description optimization via `claude -p`); skip if unavailable.

## 6. End-to-end smoke + docs sync

- [x] 6.1 Build one new ECharts dashboard end-to-end via the rewritten creator skill: propose (name + intro + entity/time) → validate → build → iterate → register. Confirm `list_dashboards` returns it and `index.html` + `daas.md` list it.
- [x] 6.2 Use the `fd-daas-dashboard` skill to list, search, get metadata, and open the dashboard built in 6.1; confirm the backing-data query works.
- [x] 6.3 Sync `CLAUDE.md` — add a `dashboards` table note under the `dashboard-mcp` section (the 6 new CRUD tools + regen + repo-root URL resolution) and a one-line pointer to the new `fd-daas-dashboard` skill alongside `fd-daas-dashboard-creator`.
- [x] 6.4 Update `construction/dashboard.md` (or `construction/daas-storage.md`) with a short section on the `dashboards` table as the dashboard-metadata registry, if those docs cover dashboard storage.
- [x] 6.5 Run `openspec validate optimize-daas-dashboard-skills --strict` and fix any reported issues; confirm `openspec status --change "optimize-daas-dashboard-skills"` shows the change apply-ready.
