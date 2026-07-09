## ADDED Requirements

### Requirement: Skill exists and triggers on dashboard-creation intent

The system SHALL ship a skill at `.claude/skills/fd-daas-dashboard-creator/SKILL.md` (project scope) whose `description` triggers when the user wants to build a dashboard for daas data — in English or Chinese.

#### Scenario: Triggers on dashboard phrasing
- **WHEN** the user says "给这些指标做一个看板" or "build a dashboard for these indicators"
- **THEN** the `fd-daas-dashboard-creator` skill is consulted

### Requirement: Propose structure with permission gate

The skill SHALL first propose a dashboard structure (charts, tables, source data, refresh cadence) as text/markdown in the conversation and explicitly ask the user for permission before building anything. It MUST NOT write files or call MCP tools that mutate state before the user accepts.

#### Scenario: User accepts the proposed structure
- **WHEN** the user accepts the proposed dashboard structure
- **THEN** the skill proceeds to the build step

#### Scenario: User requests changes to the structure
- **WHEN** the user asks for changes to the proposed structure
- **THEN** the skill revises the proposal and re-asks for permission, without building

#### Scenario: User declines
- **WHEN** the user declines the proposal
- **THEN** the skill stops without building

### Requirement: Build the dashboard as a standalone HTML file

The skill SHALL build the dashboard as a single standalone HTML file at `dashboard/my-charts-dashboard/<slug>.html` — no Next.js route, no `dashboard/src/app/...` page, no mutation of the existing `dashboard/` app. The HTML MUST be self-contained (inline the fetched data + a chart lib via CDN, or static tables) so it opens directly in a browser without a dev server. It MUST surface the file path + `file://` URL once built.

#### Scenario: Standalone HTML built
- **WHEN** the build step completes
- **THEN** the skill reports the file path `dashboard/my-charts-dashboard/<slug>.html` and the `file://` URL

#### Scenario: Directory does not exist yet
- **WHEN** `dashboard/my-charts-dashboard/` does not yet exist
- **THEN** the skill creates the directory and seeds empty `index.html` + `daas.md` files before writing the dashboard HTML

### Requirement: Offer to open in the default browser

After building, the skill SHALL offer to open the dashboard URL in the user's default browser. On macOS (the project's host) it MUST use `open <url>`. It MUST ask permission before launching the browser.

#### Scenario: User accepts open
- **WHEN** the user accepts the open-browser prompt
- **THEN** the skill runs `open <url>` and confirms the browser was launched

#### Scenario: User declines open
- **WHEN** the user declines the open-browser prompt
- **THEN** the skill prints the URL and does not launch the browser

### Requirement: Iterate then register the page-url

The skill SHALL offer the user a change-or-accept loop after the first build. If the user requests changes, the skill applies them and re-prompts. When the user accepts, the skill registers the dashboard's page-url in two places: `dashboard/my-charts-dashboard/index.html` (the charts index that links to every `<slug>.html`) and `dashboard/my-charts-dashboard/daas.md` (a markdown list of all dashboard page-urls). No `mcp/daas.db` row is written. The registration MUST be idempotent — re-accepting an already-registered dashboard does not duplicate the entry.

#### Scenario: User requests changes after build
- **WHEN** the user asks for changes after the first build
- **THEN** the skill applies the changes, re-builds the HTML file, and re-prompts for accept

#### Scenario: User accepts and page-url is registered
- **WHEN** the user accepts the final dashboard
- **THEN** the skill appends the page-url to `dashboard/my-charts-dashboard/index.html` and `dashboard/my-charts-dashboard/daas.md` (idempotent — no duplicate entries on re-accept)
