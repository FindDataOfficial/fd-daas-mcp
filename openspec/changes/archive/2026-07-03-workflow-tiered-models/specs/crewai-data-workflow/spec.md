## MODIFIED Requirements

### Requirement: Specialist data agent registry

The system SHALL persist a registry of specialist CrewAI agents in a `specialist_agents` table in `mcp/daas.db` (created via `Base.metadata.create_all`, no Alembic). Each row SHALL bind exactly one agent to one data-fetch MCP upstream: columns `name` (unique), `upstream` (the `leader_upstreams.name` this agent fetches from — soft reference, no FK), `role`, `goal`, `backstory`, `model` (a tier alias `high`/`balance`/`fast`, OR a named entry from `LEADER_MODELS`, OR `null` = shared `LLM_*` fallback), `enabled`, `created_at`. MCP tools `create_specialist_agent(name, upstream, role, goal, backstory, model=None)` and `list_specialist_agents()` SHALL provide CRUD-style access. `create_specialist_agent` SHALL reject an `upstream` that is not present in `leader_upstreams` (enabled or disabled) with a clear error and SHALL reject duplicate `name`. A seed script `seed_specialist_agents.py` SHALL upsert one default specialist agent per enabled `leader_upstreams` row (idempotent on `name`), so that after seeding every enabled data-fetch MCP has a usable agent. The seeded default agent's `model` SHALL be the `fast` tier alias (not `null`), so seeded agents default to the fast model for data-fetch steps; re-running the seed script SHALL preserve any user-set per-agent `model` (including a different tier alias or concrete name).

#### Scenario: Create a specialist agent for an enabled upstream
- **WHEN** `create_specialist_agent(name="edgar-agent", upstream="edgartools", role="SEC EDGAR specialist", goal="Fetch EDGAR filings and company facts", backstory="...", model="fast")` is called and `edgartools` exists in `leader_upstreams`
- **THEN** a row exists in `specialist_agents` with `upstream="edgartools"`, `model="fast"`, `enabled=1`
- **AND** `list_specialist_agents()` returns an entry for `edgar-agent`

#### Scenario: Reject unknown upstream
- **WHEN** `create_specialist_agent(name="x", upstream="nope", ...)` is called and `nope` is not in `leader_upstreams`
- **THEN** the system returns `{"error": "upstream 'nope' not found in leader_upstreams"}` and writes no row

#### Scenario: Reject duplicate name
- **WHEN** `create_specialist_agent(name="edgar-agent", ...)` is called and `edgar-agent` already exists
- **THEN** the system returns `{"error": "specialist agent 'edgar-agent' already exists"}` and does not overwrite the existing row

#### Scenario: Seed one agent per enabled upstream with the fast tier default
- **WHEN** `seed_specialist_agents.py` is run and `leader_upstreams` contains enabled rows for `yfinance`, `edgartools`, `akshare`
- **THEN** `specialist_agents` contains one row per enabled upstream (names like `yfinance-agent`, `edgartools-agent`, `akshare-agent`)
- **AND** each seeded row has `model="fast"`
- **AND** re-running the script updates existing rows rather than inserting duplicates
- **AND** if a user has set an agent's `model` to a different value (e.g. `"high"` or a concrete name), re-running the seed preserves that value

### Requirement: Per-agent LLM control

The system SHALL support a `LEADER_MODELS` JSON env var of shape `{name: {model, base_url?, api_key?, provider?, vision?}}` (mirroring `process-mcp`'s `PROCESS_MODELS`), parsed and cached at first use. When `LEADER_MODELS` is unset, the system SHALL fall back to a single model built from `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` (the shared OpenAI-compatible endpoint). Each specialist agent's `model` field SHALL resolve to a tier alias (`high`/`balance`/`fast`), a named entry in `LEADER_MODELS`, or the shared fallback when `null`. Tier aliases SHALL resolve via the model tier registry (`LEADER_MODEL_HIGH` / `_BALANCE` / `_FAST`) to a concrete `LEADER_MODELS` entry inside the `build_llm` chokepoint. A `list_agent_models()` MCP tool SHALL return the configured models with `name`, `model`, `provider`, and `vision` flag, PLUS a `tiers` object mapping each tier alias to its resolved `{entry, model, provider, vision}` (or `null` when unset, or `{entry, error}` when dangling). An agent step whose `model` is unconfigured (a named entry or tier alias that cannot be resolved, and no `LLM_*` fallback) SHALL return a clear `{"error": ...}` from that step WITHOUT making a network call and WITHOUT crashing the workflow.

#### Scenario: List configured models with tier mapping
- **WHEN** `LEADER_MODELS={"fast":{"model":"gpt-4o-mini"},"strong":{"model":"o3","provider":"openai"}}` is set, `LEADER_MODEL_FAST=fast` is set, and `list_agent_models()` is called
- **THEN** the tool returns both `fast` and `strong` with their `model` and `provider` fields
- **AND** the tool returns a `tiers` object that includes `fast: {entry:"fast", model:"gpt-4o-mini", ...}` and `high: null` (unset)

#### Scenario: Agent uses shared fallback when model is null
- **WHEN** a specialist agent has `model=None` and `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` are set in the environment
- **THEN** the agent's CrewAI `LLM` is built from the shared `LLM_*` env (OpenAI-compatible, `model=f"openai/{LLM_MODEL}"`)

#### Scenario: Agent model set to a tier alias resolves to the tier's concrete model
- **WHEN** a specialist agent has `model="high"` and `LEADER_MODEL_HIGH=glm` and `LEADER_MODELS` contains a `glm` entry
- **THEN** the agent's CrewAI `LLM` is built from the `glm` entry (same as if `model="glm"` had been passed directly)

#### Scenario: Unconfigured model does not crash the workflow
- **WHEN** a step's specialist agent has `model="ghost"` and `ghost` is not in `LEADER_MODELS` and is not a tier alias and no `LLM_*` fallback is set
- **THEN** that step returns `{"error": "model 'ghost' not configured"}` without any network call
- **AND** the workflow run records that step as `failed` and continues (or stops, per the step's `on_fail` policy) without raising

#### Scenario: Dangling tier alias surfaces as a step error
- **WHEN** a step's specialist agent has `model="fast"` and `LEADER_MODEL_FAST=ghost` and `ghost` is not in `LEADER_MODELS`
- **THEN** that step returns `{"error": "tier 'fast' → 'ghost' not in LEADER_MODELS"}` without any network call
- **AND** the run records that step as `failed` and proceeds per its `on_fail` policy

### Requirement: Step-by-step workflow execution

The system SHALL run a workflow two ways. `run_workflow(name)` SHALL execute all enabled steps in `sort_order` sequence and return a run record with every step's output. `run_workflow_step(name, step_sort_order)` SHALL execute exactly one step (interactive stepping) and return that step's output plus the run id, leaving the run `in_progress` so a later `run_workflow_step` on the next sort_order resumes the same run. Each run SHALL be persisted in a `workflow_runs` table (`workflow_id` FK CASCADE, `started_at`, `finished_at`, `status` ∈ `{"running","completed","failed","in_progress"}`) and each step's result in a `workflow_step_results` table (`run_id` FK CASCADE, `step_sort_order`, `status`, `output_json`, `error`, `ran_at`; unique on `(run_id, step_sort_order)` → idempotent upsert on re-run of a step). `get_workflow_run(run_id)` SHALL return the run status plus the ordered per-step results. A step's output SHALL be the raw result returned by the specialist agent's `call_data_mcp` invocation (the upstream's data), not a free-form LLM summary, unless the agent's goal explicitly asks the LLM to transform it. When a step's `model` is `null`, the runner SHALL default it to the `fast` tier alias at execution time (NOT the shared `LLM_*` fallback), so that data-fetch steps use the fast model by default; a step with an explicit `model` (tier alias or concrete name) SHALL use that value unchanged.

#### Scenario: run_workflow executes all steps sequentially
- **WHEN** `run_workflow(name="aapl-due-diligence")` is called for a workflow with 2 enabled steps
- **THEN** a `workflow_runs` row is created with `status="running"` then transitioned to `"completed"` on success
- **AND** a `workflow_step_results` row exists per step with `status="completed"` and `output_json` holding the fetched data
- **AND** the tool returns `{run_id, status:"completed", steps:[{sort_order, status, output}, ...]}`

#### Scenario: run_workflow_step executes one step and leaves the run resumable
- **WHEN** `run_workflow_step(name="aapl-due-diligence", step_sort_order=1)` is called
- **THEN** a `workflow_runs` row is created (or reused if an `in_progress` run for this workflow exists) with `status="in_progress"`
- **AND** only step 1 executes; its result is persisted in `workflow_step_results`
- **AND** the tool returns `{run_id, step_sort_order:1, status, output}` so the caller can later call `run_workflow_step(name, step_sort_order=2)` to continue

#### Scenario: get_workflow_run returns run state and per-step outputs
- **WHEN** `get_workflow_run(run_id=<id>)` is called for a completed run
- **THEN** the tool returns `{run_id, workflow_name, status, started_at, finished_at, steps:[{sort_order, status, output, error}, ...]}`

#### Scenario: depends_on injects an earlier step's output
- **WHEN** step 2 has `depends_on="1"` and step 1 produced output `O1`
- **THEN** the runner SHALL inject `O1` into step 2's request context (e.g. prepend "Previous step 1 result: <O1>" to step 2's request) before invoking step 2's specialist agent

#### Scenario: on_fail=stop halts the run on a failed step
- **WHEN** step 1 has `on_fail="stop"` and step 1 fails
- **THEN** the run's `status` becomes `"failed"`, step 2 is NOT executed, and `run_workflow` returns the run with step 1's error

#### Scenario: Null model step defaults to the fast tier
- **WHEN** `run_workflow_step(name="w", step_sort_order=1)` is called for a step whose `model` is `null` and `LEADER_MODEL_FAST=flash` is configured
- **THEN** the step's LLM is built from the `flash` entry (the `fast` tier), NOT from the shared `LLM_MODEL` fallback
- **AND** if `LEADER_MODEL_FAST` is unset, the step falls back to the shared `LLM_*` env (preserving the previous soft-fallback behavior)
