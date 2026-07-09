# fd-daas-dashboard-creator Specification

## Purpose
The skill that builds standalone HTML daas dashboards with ECharts and interactive entity/time filters, validates the source data before building, and registers each dashboard in the `dashboards` DB table.
## Requirements
### Requirement: Skill exists and triggers on dashboard-creation intent

The system SHALL ship a skill at `.claude/skills/fd-daas-dashboard-creator/SKILL.md` (project scope) whose `description` triggers when the user wants to build a dashboard for daas data — in English or Chinese.

#### Scenario: Triggers on dashboard phrasing
- **WHEN** the user says "给这些指标做一个看板" or "build a dashboard for these indicators"
- **THEN** the `fd-daas-dashboard-creator` skill is consulted

### Requirement: Propose structure with permission gate

The skill SHALL first propose a dashboard structure as text/markdown in the conversation, including: a human-readable dashboard **name** (e.g. "比亚迪日行情 + 5日均线"), a one-paragraph **introduction** describing what the dashboard shows and why it exists, the charts/tables with their types, the source data (`scraw_*` / `observations`), the **entity scope** (which entities/codes the dashboard covers) and the **time range** the user wants to see, and the refresh cadence (static snapshot vs cron, naming the cron if wired). It SHALL explicitly ask the user for permission before building anything and MUST NOT write files or call MCP tools that mutate state before the user accepts the name, introduction, and structure. If the user requests changes, the skill revises (including the name/intro/entity/time scope) and re-asks; if the user declines, the skill stops without building.

#### Scenario: User accepts the proposed structure
- **WHEN** the user accepts the proposed name, introduction, and dashboard structure
- **THEN** the skill proceeds to the data-validation step, then the build step

#### Scenario: User requests changes to the structure
- **WHEN** the user asks for changes to the proposed name, introduction, entity scope, time range, or chart layout
- **THEN** the skill revises the proposal and re-asks for permission, without building

#### Scenario: User declines
- **WHEN** the user declines the proposal
- **THEN** the skill stops without building

#### Scenario: Name and introduction confirmed before build
- **WHEN** the skill proposes the structure
- **THEN** the proposal includes a concrete human-readable name and a one-paragraph introduction, and neither is left blank or auto-generated without the user seeing it

### Requirement: Build the dashboard as a standalone HTML file

The skill SHALL build the dashboard as a single standalone HTML file at `dashboard/my-charts-dashboard/<slug>.html` — no Next.js route, no `dashboard/src/app/...` page, no mutation of the existing `dashboard/` app. The HTML MUST be self-contained so it opens directly via `file://` without a dev server. Charts MUST be rendered with **ECharts**, loaded from a locally vendored `dashboard/my-charts-dashboard/vendor/echarts.min.js` via a relative `<script src="vendor/echarts.min.js">` — NOT from a CDN and NOT via CSS-only bar divs. The fetched data MUST be baked into the HTML as a JSON `<script>` blob (multi-entity × time series), and the page MUST include an interactive **entity filter** (a `<select>` listing the covered entities) and a **time-range filter** (start/end date inputs) that re-render the ECharts charts client-side from the baked JSON via `chart.setOption` whenever the user changes a filter. The skill MUST surface the file path + `file://` URL once built.

#### Scenario: Standalone HTML built
- **WHEN** the build step completes
- **THEN** the skill reports the file path `dashboard/my-charts-dashboard/<slug>.html` and the `file://` URL

#### Scenario: Directory does not exist yet
- **WHEN** `dashboard/my-charts-dashboard/` does not yet exist
- **THEN** the skill creates the directory and regenerates `index.html` + `daas.md` from the `dashboards` table (empty initially) before writing the dashboard HTML

#### Scenario: ECharts vendored locally and used
- **WHEN** the skill builds the HTML
- **THEN** the page loads ECharts from `dashboard/my-charts-dashboard/vendor/echarts.min.js` via a relative path, and the skill ensures that file exists (one-time fetch into `vendor/` if missing, with a manual-fallback message if the fetch is offline)

#### Scenario: Entity and time filters re-render charts
- **WHEN** the user changes the entity `<select>` or the start/end date inputs in the built dashboard
- **THEN** every ECharts chart on the page re-renders from the baked JSON for the selected entity and time range via `chart.setOption`, without a page reload or network fetch

### Requirement: Offer to open in the default browser

After building, the skill SHALL offer to open the dashboard URL in the user's default browser. On macOS (the project's host) it MUST use `open <url>`. It MUST ask permission before launching the browser.

#### Scenario: User accepts open
- **WHEN** the user accepts the open-browser prompt
- **THEN** the skill runs `open <url>` and confirms the browser was launched

#### Scenario: User declines open
- **WHEN** the user declines the open-browser prompt
- **THEN** the skill prints the URL and does not launch the browser

### Requirement: Iterate then register the page-url

The skill SHALL offer the user a change-or-accept loop after the first build. If the user requests changes, the skill applies them, re-builds the HTML, and re-prompts. When the user accepts, the skill registers the dashboard by calling `mcp__dashboard-mcp__register_dashboard` with the slug, human-readable name, introduction, source tables, entity coverage, time range, refresh cadence, chart config, file path, and `file://` URL. `dashboard-mcp` persists the row in the `dashboards` table in `mcp/daas.db` AND regenerates `index.html` + `daas.md` from the DB. A `mcp/daas.db` row IS now written (reversing the prior "no DB row" behavior). The registration MUST be idempotent — re-accepting an already-registered dashboard upserts by slug and produces no duplicate entries in `index.html` or `daas.md`.

#### Scenario: User requests changes after build
- **WHEN** the user asks for changes after the first build
- **THEN** the skill applies the changes, re-builds the HTML file, and re-prompts for accept

#### Scenario: User accepts and the dashboard is registered in the database
- **WHEN** the user accepts the final dashboard
- **THEN** the skill calls `register_dashboard`, which writes/updates a row in the `dashboards` table and regenerates `index.html` + `daas.md`; a subsequent `get_dashboard` returns the registered name, introduction, source tables, and `file://` URL

### Requirement: Write a dashboard instruction markdown

After building the standalone HTML, the skill SHALL also write an instruction `<custom-name>-dashboard.md` companion doc containing: the dashboard slug, the source `scraw_*` / `observations` tables + columns backing each chart, the refresh cadence (static snapshot vs cron, naming the cron if wired), the `file://` URL of the built HTML, and a one-line "how to refresh" note. The HTML build and the `index.html` / `daas.md` registration (per the existing requirements) are unchanged; the instruction md is additional.

#### Scenario: Standalone instruction md written

- **WHEN** the skill runs standalone (no `workflow-name` token in `args`)
- **THEN** the instruction md is written to `daas-doc/dashboard/<custom-name>-dashboard.md` and its path is reported to the user

#### Scenario: Instruction md content

- **WHEN** the instruction md is written
- **THEN** it lists the dashboard slug, source tables, refresh cadence, and the `file://` URL of the built HTML

### Requirement: Nest under the workflow dir when invoked inside workflow-creator

When the skill's `args` contain a `workflow-name <X>` token, the skill SHALL write the instruction md to `daas-doc/<X>/<custom-name>-dashboard.md` instead of the standalone `daas-doc/dashboard/` path.

#### Scenario: Nested instruction md

- **WHEN** the skill is invoked with `args` containing `workflow-name my-flow`
- **THEN** the instruction md is written to `daas-doc/my-flow/<custom-name>-dashboard.md`

### Requirement: Validate source data before building the dashboard

After the user accepts the proposed structure and before building the HTML, the skill SHALL fetch the source data via `mcp__dashboard-mcp__query_table` (or a direct `sqlite3` one-liner fallback when `dashboard-mcp` hits its stale-DB "no such table" gotcha) and validate that the rows satisfy the dashboard's requirements: the expected columns exist, every requested entity has rows, the rows fall within the requested time range, and the row count is non-zero. The skill SHALL surface a coverage summary (entities covered, entity count, date range, row count, columns) to the user. For any shortfall — a missing entity, zero rows in the time range, or a missing column — the skill SHALL ask the user how to proceed (skip the missing entity / widen the time range / abort) before baking the data into the HTML.

#### Scenario: Data meets requirements

- **WHEN** the fetched rows cover all requested entities, fall in the requested time range, carry the expected columns, and are non-empty
- **THEN** the skill proceeds to build the HTML, baking the validated rows as the JSON `<script>` blob

#### Scenario: Data shortfalls

- **WHEN** the fetched rows are missing one or more requested entities, or have zero rows in the requested time range, or are missing an expected column
- **THEN** the skill surfaces a coverage summary naming the shortfalls and asks the user whether to skip / widen / abort, and does not build until the user decides

#### Scenario: Empty result

- **WHEN** the fetched rows are empty (zero rows total)
- **THEN** the skill aborts the build with a clear message naming the source table and the filter that produced no rows, and does not write an HTML file

