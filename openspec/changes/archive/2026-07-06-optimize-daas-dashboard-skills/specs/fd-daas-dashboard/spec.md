## ADDED Requirements

### Requirement: Skill exists and triggers on dashboard-use intent

The system SHALL ship a skill at `.claude/skills/fd-daas-dashboard/SKILL.md` (project scope) whose `description` triggers when the user wants to find, open, reuse, or learn about an existing standalone HTML dashboard — in English or Chinese. It SHALL NOT trigger for building a new dashboard (that is `fd-daas-dashboard-creator`).

#### Scenario: Triggers on dashboard-use phrasing

- **WHEN** the user says "打开之前那个看板" or "show me the BYD dashboard" or "我们有哪些看板" or "what data backs the leaders dashboard"
- **THEN** the `fd-daas-dashboard` skill is consulted

#### Scenario: Does not trigger on build intent

- **WHEN** the user says "给这些指标做一个看板" or "build a dashboard for these indicators"
- **THEN** the `fd-daas-dashboard` skill is NOT consulted; `fd-daas-dashboard-creator` is the relevant skill

### Requirement: List and search dashboards from the database

The skill SHALL discover dashboards via `mcp__dashboard-mcp__list_dashboards` (returns every dashboard's name + slug + intro + file_url) and `mcp__dashboard-mcp__search_dashboards` (keyword match against name + intro + source_tables). It MUST surface the name + intro of each match to the user so they can pick.

#### Scenario: List all dashboards

- **WHEN** the user asks "我们有哪些看板" (what dashboards do we have)
- **THEN** the skill calls `list_dashboards` and presents each dashboard's name + intro + slug

#### Scenario: Search by keyword

- **WHEN** the user asks "有比亚迪相关的看板吗" (any BYD-related dashboard)
- **THEN** the skill calls `search_dashboards` with a BYD keyword and presents only matching dashboards (name + intro), or says "no matching dashboard" if none

### Requirement: Show a dashboard's full metadata

When the user names a dashboard, the skill SHALL call `mcp__dashboard-mcp__get_dashboard` by slug and surface the full metadata: the introduction, the source `scraw_*` / `observations` tables backing it, the entity coverage, the time range, the refresh cadence, and the `file://` URL.

#### Scenario: Get dashboard by slug

- **WHEN** the user asks "leaders 这个看板里是什么数据"
- **THEN** the skill calls `get_dashboard` with the resolved slug and reports the intro, source tables, entity coverage, time range, and refresh cadence

### Requirement: Open a dashboard in the default browser

The skill SHALL offer to open a dashboard's `file_url` in the user's default browser. On macOS (the project host) it MUST use `open <file_url>`. It MUST ask permission before launching the browser.

#### Scenario: User accepts open

- **WHEN** the user accepts the open-browser prompt
- **THEN** the skill runs `open <file_url>` and confirms the browser was launched

#### Scenario: User declines open

- **WHEN** the user declines the open-browser prompt
- **THEN** the skill prints the `file://` URL and does not launch the browser

### Requirement: Query the data backing a dashboard

The skill SHALL let the user inspect the rows behind a dashboard by calling `mcp__dashboard-mcp__query_table` against the dashboard's recorded `source_tables` (with `database="daas"`). This lets the user verify or explore the underlying data without opening the HTML.

#### Scenario: Query backing data

- **WHEN** the user asks "这个看板的数据长什么样" (what does this dashboard's data look like)
- **THEN** the skill calls `query_table` on the dashboard's first source table (limit ~20) and shows the rows, naming the source table

### Requirement: Does not build dashboards or mutate the registry

The skill is read-only with respect to the `dashboards` table. If the user asks to build, edit, or delete a dashboard, the skill SHALL redirect them to `fd-daas-dashboard-creator` (build/edit) or the `dashboard-mcp` delete tool (delete) rather than performing the mutation itself.

#### Scenario: User asks to build

- **WHEN** the user says "做一个新看板" (build a new dashboard)
- **THEN** the skill tells the user to invoke `fd-daas-dashboard-creator` and does not attempt to build
