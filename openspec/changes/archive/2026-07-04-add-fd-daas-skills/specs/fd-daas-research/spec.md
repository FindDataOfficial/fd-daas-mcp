## ADDED Requirements

### Requirement: Skill exists and triggers on research-orchestration intent

The system SHALL ship a skill at `.claude/skills/fd-daas-research/SKILL.md` (project scope) whose `description` triggers when the user gives a natural-language research demand that needs both an indicator pipeline and a dashboard — in English or Chinese.

#### Scenario: Triggers on research-demand phrasing
- **WHEN** the user says "帮我研究一下比亚迪，做指标和看板" or "research TSLA: build indicators and a dashboard"
- **THEN** the `fd-daas-research` skill is consulted

### Requirement: Analyze demand into a plan

The skill SHALL analyze the user's demand and produce an analysis plan that names: the entities involved, the indicators needed (which series, which ops, which windows), and the dashboard shape. It MUST show the plan to the user and get confirmation before delegating.

#### Scenario: Plan produced and confirmed
- **WHEN** the user confirms the analysis plan
- **THEN** the skill proceeds to delegate to `fd-daas-indicators-creator`

#### Scenario: Demand needs no indicators
- **WHEN** the analysis shows the demand is dashboard-only (no new indicators needed)
- **THEN** the skill skips `fd-daas-indicators-creator` and delegates only to `fd-daas-dashboard-creator`, telling the user why

### Requirement: Delegate to fd-daas-indicators-creator

The skill SHALL delegate the indicator + table + cron work to the `fd-daas-indicators-creator` skill. It MUST pass the entities and indicators from the plan as context, so the indicators-creator skill does not re-ask.

#### Scenario: Indicators-creator delegates cleanly
- **WHEN** the plan is confirmed
- **THEN** the skill invokes `fd-daas-indicators-creator` with the plan's entities + indicators, and waits for it to finish

### Requirement: Delegate to fd-daas-dashboard-creator

After the indicators exist, the skill SHALL delegate to `fd-daas-dashboard-creator` to build the dashboard over the newly created indicators/tables. It MUST pass the indicator names + `scraw_<slug>` tables as context.

#### Scenario: Dashboard-creator delegates cleanly
- **WHEN** `fd-daas-indicators-creator` finishes
- **THEN** the skill invokes `fd-daas-dashboard-creator` with the indicator + table names, and waits for it to finish

#### Scenario: Earlier step already done
- **WHEN** the indicators or dashboard already exist from a prior run
- **THEN** the skill skips the already-done delegation and tells the user, mirroring the indicators-creator skip rule
