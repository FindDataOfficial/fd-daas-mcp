## ADDED Requirements

### Requirement: LLM-driven workflow builder

A `build_workflow_from_goal(goal, name=None, description=None, model="high")` MCP tool SHALL turn a natural-language `goal` into a persisted workflow of specialist-agent steps. The tool SHALL build a CrewAI LLM from the `model` parameter (default `high` tier), prompt the LLM with the `goal` plus the list of registered specialist agents (name + upstream + role + goal), and ask it to emit an ordered list of steps each of shape `{agent, request, depends_on?, on_fail?}`. The tool SHALL then persist the workflow via the existing `create_workflow(name, description)` + `add_workflow_step(...)` path — reusing the existing validation (reject unknown agents, auto-assign `sort_order`) — and SHALL return the created workflow in the same shape as `get_workflow(name)`. When `name` is omitted the tool SHALL derive a kebab-case name from the goal. The tool SHALL default `model="high"`; a caller MAY pass `model="balance"`, `model="fast"`, a concrete `LEADER_MODELS` name, or `null` (which resolves to the `fast` tier, matching `run_workflow` step semantics).

#### Scenario: Build a workflow from a natural-language goal
- **WHEN** `build_workflow_from_goal(goal="analyze AAPL: price history then latest 10-K", name="aapl-analysis")` is called and the `high` tier resolves to a configured LLM
- **THEN** a workflow named `aapl-analysis` is created with 2+ ordered steps, each bound to a registered specialist agent (e.g. `yfinance-agent` then `edgartools-agent`)
- **AND** the second step has `depends_on="1"` linking it to the first
- **AND** the tool returns the workflow with its steps (same shape as `get_workflow`)

#### Scenario: Default model is the high tier
- **WHEN** `build_workflow_from_goal(goal="...", name="w")` is called with no `model` argument
- **THEN** the planning LLM is built from the `high` tier (`LEADER_MODEL_HIGH`)

#### Scenario: Derived name when name omitted
- **WHEN** `build_workflow_from_goal(goal="Analyze AAPL price + filings")` is called without `name`
- **THEN** the workflow is persisted with a kebab-case name derived from the goal (e.g. `analyze-aapl-price-filings`) and that name is returned

### Requirement: Builder validates agent names and drops invalid steps

Before persisting, `build_workflow_from_goal` SHALL validate that each emitted step's `agent` exists in `specialist_agents`. If any step references an unknown agent, the tool SHALL re-prompt the LLM once with the validation error and the valid agent list. After the re-prompt, any still-invalid step SHALL be dropped from the workflow with a warning recorded in the returned workflow's `warnings` field; the remaining valid steps SHALL be persisted. The tool SHALL NEVER raise out of an invalid agent name.

#### Scenario: Invalid agent name is dropped after one re-prompt
- **WHEN** the LLM emits a step with `agent="ghost-agent"` not in `specialist_agents`
- **THEN** the tool re-prompts the LLM once with the error and the valid agent list
- **AND** if the step is still invalid after the re-prompt, it is dropped and the returned workflow carries `warnings: ["dropped step referencing unknown agent 'ghost-agent'"]`
- **AND** the remaining valid steps are persisted

### Requirement: Builder deterministic fallback when CrewAI unavailable

When `crewai` cannot be imported or the resolved `model` cannot be built into a CrewAI LLM (hard config error or soft unconfigured), `build_workflow_from_goal` SHALL fall back to a deterministic direct router that emits a single best-effort step: it SHALL pick the first enabled specialist agent whose `upstream` or `role` keyword-matches the `goal`, or the first enabled specialist agent if none match, and persist a one-step workflow with that agent and the original `goal` as the `request`. The fallback SHALL be recorded in the returned workflow's `warnings` field (e.g. `{"fallback": "direct", "reason": "crewai unavailable"}`). The tool SHALL NOT raise out of CrewAI-missing.

#### Scenario: CrewAI unavailable — builder emits a single best-effort step
- **WHEN** `build_workflow_from_goal(goal="get AAPL price history", name="w")` is called and `crewai` raises `ImportError`
- **THEN** the tool persists a one-step workflow using the `yfinance-agent` (whose upstream `yfinance` keyword-matches "price history")
- **AND** the returned workflow carries `warnings: ["fallback: direct (crewai unavailable)"]`

#### Scenario: High tier unconfigured — builder falls back rather than raising
- **WHEN** `build_workflow_from_goal(goal="...")` is called and `LEADER_MODEL_HIGH` is unset AND no `LLM_*` fallback is configured
- **THEN** the tool emits a single best-effort step via the direct router and returns the workflow with a fallback warning, rather than returning an error
