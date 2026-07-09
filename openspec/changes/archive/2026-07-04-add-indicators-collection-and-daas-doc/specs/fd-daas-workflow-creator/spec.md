## ADDED Requirements

### Requirement: Derive a workflow-name and create its daas-doc folder

The skill SHALL derive a kebab-case `<workflow-name>` from the summarized goal (slugify, truncate to ~40 chars). If the goal is empty or `daas-doc/<workflow-name>/` already exists, the skill SHALL fall back to `workflow-<YYYYMMDD>-<HHMMSS>`. The skill SHALL create `daas-doc/<workflow-name>/` before writing `plan.md`. The agent computes the timestamp in-skill (the skill layer is not subject to the `Workflow` JS sandbox's `Date.now` restriction).

#### Scenario: Workflow-name derived from goal

- **WHEN** the user's goal is "Fetch 比亚迪 daily OHLCV and compute a 5-day SMA"
- **THEN** the skill derives a workflow-name like `fetch-byd-daily-ohlcv-and-compute` and creates `daas-doc/<workflow-name>/`

#### Scenario: Timestamp fallback on collision

- **WHEN** `daas-doc/<workflow-name>/` already exists
- **THEN** the skill falls back to `workflow-<YYYYMMDD>-<HHMMSS>` for the workflow-name

### Requirement: Write plan.md under daas-doc

The skill SHALL write `daas-doc/<workflow-name>/plan.md` capturing: the workflow-name, the composed goal, the persisted leader-mcp workflow name + step list (upstream MCP, tool, arguments per step), the chosen tier, and the created date. Writing `plan.md` is additional to (not a replacement for) persisting the workflow in leader-mcp via `mcp__leader-mcp__build_workflow_from_goal` / manual construction — the persist path is unchanged.

#### Scenario: plan.md written after persist

- **WHEN** the workflow is persisted in leader-mcp (LLM path or manual fallback)
- **THEN** `daas-doc/<workflow-name>/plan.md` is written with the goal, step list, tier, and workflow name, and its path is reported to the user

### Requirement: Pass workflow-name as nesting context to child skills

When the skill invokes a child creator skill (`fd-daas-dashboard-creator` or `fd-daas-indicators-collection-creator`) via the `Skill` tool during a workflow run, it SHALL include a `workflow-name <X>` token in the child's `args` string so the child writes its doc under `daas-doc/<X>/` instead of its standalone default.

#### Scenario: Nesting token passed to dashboard-creator

- **WHEN** the skill delegates to `fd-daas-dashboard-creator` during a workflow run
- **THEN** the child's `args` contains `workflow-name <X>` and the child writes its instruction md under `daas-doc/<X>/`
