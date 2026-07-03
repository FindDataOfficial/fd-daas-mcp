## Why

`leader-mcp` already exposes a single CrewAI agent (`ask_data_crew`) that routes one natural-language request to one data-fetch MCP. That is a black box: one manager, one fetch, one result, no per-agent LLM, no chaining. Real data work is multi-step and multi-source — "pull AAPL price history, then pull its 10-K, then pull the same period for a peer, then summarize" — and each source has a different shape that a generalist manager routes poorly. We need several **specialist agents** (one per data-fetch MCP, each with its own LLM), composed into a **step-by-step workflow** whose intermediate results are visible and reusable between steps.

## What Changes

- Add **specialist data agents** — a registry of CrewAI agents, each bound to one data-fetch MCP upstream (e.g. a `yfinance` agent, an `edgartools` agent, an `akshare` agent). Each agent carries a curried `call_data_mcp(server=<its upstream>, ...)` so it can only fetch from its specialized MCP, plus `list_data_mcp_tools` and `search_registry_functions` for discovery within that source.
- Add **per-agent LLM control** — a `LEADER_MODELS` JSON env (mirroring `process-mcp`'s `PROCESS_MODELS`: `{name: {model, base_url?, api_key?, provider?}}`) with a shared `LLM_*` fallback. Each specialist agent and the workflow manager bind to a named model. New tool `list_agent_models`.
- Add **data workflows** — an ordered, named workflow of steps; each step binds a specialist agent + a request/instruction + optional `depends_on` (so a later step can reference an earlier step's output). Persisted in `mcp/daas.db` (new `workflows` / `workflow_steps` / `workflow_runs` / `workflow_step_results` tables in `mcp/models/`).
- Add **step-by-step execution** — `run_workflow(id)` runs steps sequentially and returns every step's result; `run_workflow_step(id, step_index)` runs one step (interactive stepping, resumable); `get_workflow_run(run_id)` returns the run state + per-step outputs.
- Expose as new MCP tools on `leader-mcp` (registered in `server.py`): `list_agent_models`, `create_specialist_agent`, `list_specialist_agents`, `create_workflow`, `add_workflow_step`, `get_workflow`, `list_workflows`, `run_workflow`, `run_workflow_step`, `get_workflow_run`.
- **Fallback**: when `crewai` is unavailable or an agent's model is unconfigured, a specialist agent step falls back to a deterministic direct `call_data_mcp` call (same primitive `ask_data_crew` already falls back to) so a workflow still runs end-to-end without an LLM. No workflow ever hard-fails purely because CrewAI is missing.
- **Cron-drivable** (stretch): a CLI branch `python server.py --run-workflow <id>` so a workflow can be wired to `cron-mcp` via `create_task` + `create_schedule`, mirroring the `process-mcp --run-rule` / `daas-mcp --fetch-item` pattern.

## Capabilities

### New Capabilities
- `crewai-data-workflow`: Specialist CrewAI data agents (one per data-fetch MCP, per-agent LLM) composed into persisted, step-by-step, resumable data-fetch workflows over `leader-mcp`'s gateway — with a deterministic fallback when CrewAI is unavailable.

### Modified Capabilities
<!-- None. The existing ask_data_crew requirement in leader-mcp-data-gateway is unchanged; this adds a parallel specialist+workflow surface that reuses call_data_mcp as its primitive. -->

## Impact

- **Code (new files in `mcp/leader-mcp/`)**: `specialist_agents.py` (agent + LLM builder, extracted from `data_crew.py`'s `_build_llm`), `workflow_tools.py` (MCP tools), `workflow_database.py` (CRUD + run state), `seed_specialist_agents.py` (seed one agent per enabled `leader_upstreams` row), `selfcheck_workflow.py` (offline self-check with stub upstream, no LLM call).
- **Code (edits)**: `server.py` (register the ~10 new tools; add `--run-workflow <id>` CLI branch); `data_crew.py` (import the shared `_build_llm` instead of duplicating it); `pyproject.toml` (document the `LEADER_MODELS` env).
- **Schema (`mcp/models/`)**: new tables `specialist_agents`, `workflows`, `workflow_steps`, `workflow_runs`, `workflow_step_results` via `Base.metadata.create_all` (no Alembic), reusing the shared `Base`.
- **Database**: `mcp/daas.db` gains the 5 tables. Runs/step results are queryable via `dashboard-mcp.query_table`.
- **API**: ~10 new MCP tools on `leader-mcp`; no breaking changes to existing gateway or registry tools.
- **Dependencies**: `crewai` + `litellm` already an optional `[crew]` extra on `leader-mcp` — reused, no new dependency.
- **Env**: new `LEADER_MODELS` JSON (optional; falls back to `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL`).
- **Systems**: `daas.db`; optional `cron-mcp` integration (stretch) for scheduled workflow runs.
