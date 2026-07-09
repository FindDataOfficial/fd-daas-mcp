## ADDED Requirements

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
