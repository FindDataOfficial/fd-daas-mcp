# fd-daas-workflow-creator Specification

## Purpose
TBD - created by archiving change add-fd-daas-skills. Update Purpose after archive.
## Requirements
### Requirement: Skill exists and triggers on workflow-creation intent

The system SHALL ship a skill at `.claude/skills/fd-daas-workflow-creator/SKILL.md` (project scope) whose `description` triggers when the user wants to summarize a completed multi-step flow and persist it as a resumable leader-mcp workflow — in English or Chinese.

#### Scenario: Triggers on workflow-summarize phrasing
- **WHEN** the user says "把刚才这套流程存成一个 workflow" or "save this flow as a workflow"
- **THEN** the `fd-daas-workflow-creator` skill is consulted

### Requirement: Summarize the flow

The skill SHALL summarize the just-executed flow into an ordered list of data-fetch steps, naming the upstream MCP + tool + arguments for each step. It MUST show the summary to the user before persisting.

#### Scenario: Summary produced and confirmed
- **WHEN** the user confirms the summarized step list
- **THEN** the skill proceeds to persist the workflow

#### Scenario: Summary is empty
- **WHEN** there is no recent flow to summarize
- **THEN** the skill reports "no recent flow to capture" and stops

### Requirement: Persist via build_workflow_from_goal when an LLM is configured

The skill SHALL prefer `mcp__leader-mcp__build_workflow_from_goal(goal, name?, description?, model="fast")` to decompose the goal into specialist-agent steps. It MUST accept an optional model-tier argument (`high` / `balance` / `fast`) defaulting to `fast` (data-fetch pipelines are not reasoning-heavy). It MUST explain to the user that this path uses an LLM and may take a moment.

#### Scenario: LLM available, default tier
- **WHEN** the leader-mcp LLM is configured and the user does not pick a tier
- **THEN** the skill calls `build_workflow_from_goal` with `model="fast"` and confirms the created workflow name + step count

#### Scenario: User picks a non-default tier
- **WHEN** the user asks for the `high` or `balance` tier
- **THEN** the skill calls `build_workflow_from_goal` with that tier

### Requirement: Fall back to manual construction when no LLM is configured

When `build_workflow_from_goal` falls back to its deterministic single-step workflow (because `crewai` is unavailable or no LLM is configured), the skill SHALL detect the fallback and offer to build the workflow manually via `mcp__leader-mcp__create_workflow` + `mcp__leader-mcp__add_workflow_step` per step, using the summarized step list. The skill MUST NOT treat the fallback as an error.

#### Scenario: LLM unavailable — fallback used
- **WHEN** `build_workflow_from_goal` returns a deterministic single-step workflow
- **THEN** the skill tells the user the LLM was unavailable, and offers to construct the workflow manually from the summarized steps

#### Scenario: Manual construction succeeds
- **WHEN** the user accepts the manual-construction offer
- **THEN** the skill calls `create_workflow` once and `add_workflow_step` per summarized step, and confirms the workflow + step count

### Requirement: Optionally run the workflow

After persisting, the skill SHALL offer to run the workflow via `mcp__leader-mcp__run_workflow` (all steps) or `run_workflow_step` (one step at a time). It MUST NOT auto-run without user consent.

#### Scenario: User accepts run
- **WHEN** the user accepts the run prompt
- **THEN** the skill calls `run_workflow` and reports the run id + per-step results

#### Scenario: User declines run
- **WHEN** the user declines the run prompt
- **THEN** the skill reports the workflow name and stops

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

