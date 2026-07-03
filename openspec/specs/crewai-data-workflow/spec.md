# crewai-data-workflow Specification

## Purpose
TBD - created by syncing change crewai-data-workflow. Update Purpose after archive.
## Requirements
### Requirement: Specialist data agent registry

The system SHALL persist a registry of specialist CrewAI agents in a `specialist_agents` table in `mcp/daas.db` (created via `Base.metadata.create_all`, no Alembic). Each row SHALL bind exactly one agent to one data-fetch MCP upstream: columns `name` (unique), `upstream` (the `leader_upstreams.name` this agent fetches from — soft reference, no FK), `role`, `goal`, `backstory`, `model` (named model from `LEADER_MODELS`, nullable = shared `LLM_*` fallback), `enabled`, `created_at`. MCP tools `create_specialist_agent(name, upstream, role, goal, backstory, model=None)` and `list_specialist_agents()` SHALL provide CRUD-style access. `create_specialist_agent` SHALL reject an `upstream` that is not present in `leader_upstreams` (enabled or disabled) with a clear error and SHALL reject duplicate `name`. A seed script `seed_specialist_agents.py` SHALL upsert one default specialist agent per enabled `leader_upstreams` row (idempotent on `name`), so that after seeding every enabled data-fetch MCP has a usable agent.

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

#### Scenario: Seed one agent per enabled upstream
- **WHEN** `seed_specialist_agents.py` is run and `leader_upstreams` contains enabled rows for `yfinance`, `edgartools`, `akshare`
- **THEN** `specialist_agents` contains one row per enabled upstream (names like `yfinance-agent`, `edgartools-agent`, `akshare-agent`)
- **AND** re-running the script updates existing rows rather than inserting duplicates

### Requirement: Specialist agent tool scoping

A specialist agent's CrewAI tools SHALL be scoped to its bound `upstream`: the agent SHALL be given a curried `call_data_mcp` that fixes `server=<its upstream>` so it can only fetch from its specialized MCP, plus `list_data_mcp_tools(server=<its upstream>)` and (for registry-based upstreams `yfinance`/`akshare`) `search_registry_functions` scoped to that harness. The agent SHALL NOT be able to invoke `call_data_mcp` with a different `server`.

#### Scenario: Specialist agent fetches from its bound upstream
- **WHEN** the `edgartools` specialist agent runs a step requesting "company facts for AAPL"
- **THEN** the agent's `call_data_mcp` tool invokes `call_data_mcp(server="edgartools", tool="get_company", arguments='{"ticker_or_cik":"AAPL"}')` under the hood
- **AND** the agent has no tool capable of calling `server="yfinance"` or any other upstream

#### Scenario: Registry-based specialist uses the dispatch tool
- **WHEN** the `yfinance` specialist agent runs a step requesting "AAPL 1-month price history"
- **THEN** the agent calls `call_data_mcp(server="yfinance", tool="call_yfinance_function", arguments='{"name":"ticker_history","params_json":"{\\"symbol\\":\\"AAPL\\",\\"period\\":\\"1mo\\"}"}')`
- **AND** the `search_registry_functions` tool available to the agent is scoped to `harness="yfinance"`

### Requirement: Per-agent LLM control

The system SHALL support a `LEADER_MODELS` JSON env var of shape `{name: {model, base_url?, api_key?, provider?}}` (mirroring `process-mcp`'s `PROCESS_MODELS`), parsed and cached at first use. When `LEADER_MODELS` is unset, the system SHALL fall back to a single model built from `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` (the shared OpenAI-compatible endpoint). Each specialist agent's `model` field SHALL resolve to a named entry in `LEADER_MODELS` (or the shared fallback when null). A `list_agent_models()` MCP tool SHALL return the configured models with `name`, `model`, `provider`, and `vision` flag. An agent step whose `model` is unconfigured (named but not in `LEADER_MODELS`, and no `LLM_*` fallback) SHALL return a clear `{"error": ...}` from that step WITHOUT making a network call and WITHOUT crashing the workflow.

#### Scenario: List configured models
- **WHEN** `LEADER_MODELS={"fast":{"model":"gpt-4o-mini"},"strong":{"model":"o3","provider":"openai"}}` is set and `list_agent_models()` is called
- **THEN** the tool returns both `fast` and `strong` with their `model` and `provider` fields

#### Scenario: Agent uses shared fallback when model is null
- **WHEN** a specialist agent has `model=None` and `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` are set in the environment
- **THEN** the agent's CrewAI `LLM` is built from the shared `LLM_*` env (OpenAI-compatible, `model=f"openai/{LLM_MODEL}"`)

#### Scenario: Unconfigured model does not crash the workflow
- **WHEN** a step's specialist agent has `model="ghost"` and `ghost` is not in `LEADER_MODELS` and no `LLM_*` fallback is set
- **THEN** that step returns `{"error": "model 'ghost' not configured"}` without any network call
- **AND** the workflow run records that step as `failed` and continues (or stops, per the step's `on_fail` policy) without raising

### Requirement: Data workflow definition

The system SHALL persist data workflows in two tables in `mcp/daas.db` (via `Base.metadata.create_all`, no Alembic): `workflows` (`name` unique, `description`, `created_at`) and `workflow_steps` (`workflow_id` FK CASCADE, `sort_order`, `agent` = `specialist_agents.name` soft ref, `request` text, `depends_on` nullable comma-separated list of prior step sort_orders, `on_fail` ∈ `{"continue","stop"}` default `"continue"`, `model` nullable override). MCP tools `create_workflow(name, description)`, `add_workflow_step(workflow_name, agent, request, depends_on=None, on_fail="continue", model=None, sort_order=None)`, `get_workflow(name)` (returns the workflow + ordered steps), and `list_workflows()` SHALL manage them. `add_workflow_step` SHALL reject an `agent` that is not in `specialist_agents` with a clear error. `sort_order` SHALL auto-assign to `max+1` when omitted.

#### Scenario: Create a workflow and add ordered steps
- **WHEN** `create_workflow(name="aapl-due-diligence", description="...")` then `add_workflow_step(workflow_name="aapl-due-diligence", agent="yfinance-agent", request="AAPL 1-month price history")` then `add_workflow_step(workflow_name="aapl-due-diligence", agent="edgar-agent", request="latest 10-K for AAPL")` are called
- **THEN** `get_workflow("aapl-due-diligence")` returns both steps with `sort_order` 1 and 2 respectively, each bound to its named specialist agent

#### Scenario: Reject step with unknown agent
- **WHEN** `add_workflow_step(workflow_name="w", agent="ghost-agent", request="...")` is called and `ghost-agent` is not in `specialist_agents`
- **THEN** the system returns `{"error": "specialist agent 'ghost-agent' not found"}` and writes no step row

#### Scenario: depends_on links a later step to an earlier step
- **WHEN** step 2 is added with `depends_on="1"`
- **THEN** `get_workflow` returns step 2 with `depends_on=["1"]` so the runner can inject step 1's result into step 2's context

### Requirement: Step-by-step workflow execution

The system SHALL run a workflow two ways. `run_workflow(name)` SHALL execute all enabled steps in `sort_order` sequence and return a run record with every step's output. `run_workflow_step(name, step_sort_order)` SHALL execute exactly one step (interactive stepping) and return that step's output plus the run id, leaving the run `in_progress` so a later `run_workflow_step` on the next sort_order resumes the same run. Each run SHALL be persisted in a `workflow_runs` table (`workflow_id` FK CASCADE, `started_at`, `finished_at`, `status` ∈ `{"running","completed","failed","in_progress"}`) and each step's result in a `workflow_step_results` table (`run_id` FK CASCADE, `step_sort_order`, `status`, `output_json`, `error`, `ran_at`; unique on `(run_id, step_sort_order)` → idempotent upsert on re-run of a step). `get_workflow_run(run_id)` SHALL return the run status plus the ordered per-step results. A step's output SHALL be the raw result returned by the specialist agent's `call_data_mcp` invocation (the upstream's data), not a free-form LLM summary, unless the agent's goal explicitly asks the LLM to transform it.

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

### Requirement: Deterministic fallback when CrewAI unavailable

When `crewai` cannot be imported (ImportError) or a specialist agent's configured LLM cannot be built (missing model config), a step SHALL fall back to a deterministic direct path: the runner SHALL parse the step's `request` for a `(tool, arguments)` pair (or, for registry-based upstreams, a function name + params) and call `call_data_mcp(server=<agent.upstream>, tool, arguments)` directly — the same primitive `ask_data_crew`'s direct router uses — so the workflow still produces data without an LLM. The fallback SHALL be recorded in the step result's `status`/`error` metadata (e.g. `{"fallback": "direct", "reason": "crewai unavailable"}`) so it is never silent. The workflow SHALL NOT raise out of `run_workflow` / `run_workflow_step` purely because CrewAI is missing.

#### Scenario: CrewAI unavailable — step falls back to direct call
- **WHEN** `crewai` raises `ImportError` on a step requesting "AAPL 1-month price history" on the `yfinance` specialist agent
- **THEN** the runner parses the request to `tool="call_yfinance_function"`, `arguments={"name":"ticker_history","params_json":"{\"symbol\":\"AAPL\",\"period\":\"1mo\"}"}`
- **AND** calls `call_data_mcp(server="yfinance", ...)` directly and persists the fetched data as the step's `output_json`
- **AND** the step result records `{"fallback":"direct","reason":"crewai unavailable"}` in its metadata

#### Scenario: Workflow completes end-to-end without an LLM
- **WHEN** `run_workflow(name="w")` is called and `crewai` is not importable
- **THEN** every step runs via the direct fallback and the run reaches `status="completed"` (assuming each step's request is parseable)
- **AND** no exception propagates to the caller

### Requirement: Cron-drivable workflow CLI branch

`leader-mcp`'s `server.py` SHALL accept a `--run-workflow <name>` CLI argument that runs a workflow in-process (no stdio MCP server), writes the run + step results to `mcp/daas.db`, prints a JSON summary of the run to stdout, and exits. This mirrors the `process-mcp --run-rule` and `daas-mcp --fetch-item` cron pattern so a workflow can be scheduled via `cron-mcp`'s `create_task` + `create_schedule` with command `uv run --directory mcp/leader-mcp python server.py --run-workflow <name>`.

#### Scenario: Run a workflow via the CLI branch
- **WHEN** `uv run --directory mcp/leader-mcp python server.py --run-workflow aapl-due-diligence` is run
- **THEN** the workflow executes in-process (no stdio server starts)
- **AND** a `workflow_runs` row + per-step `workflow_step_results` rows are written to `mcp/daas.db`
- **AND** a JSON summary `{run_id, workflow_name, status, steps:[...]}` is printed to stdout and the process exits 0 on success

#### Scenario: Unknown workflow via the CLI branch
- **WHEN** `server.py --run-workflow nope` is run and `nope` is not in `workflows`
- **THEN** the process prints `{"error": "workflow 'nope' not found"}` to stdout and exits non-zero
