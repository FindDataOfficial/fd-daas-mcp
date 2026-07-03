# leader-mcp

Multi-harness registry + **data gateway** + **CrewAI data workflows**.

Three layers, all exposed as MCP tools on one server (`python server.py`):

1. **Registry** (`leader_tools.py`) — query the unified function registry across
   harnesses: `list_harnesses`, `search_functions`, `get_function_detail`,
   `list_categories`, `find_functions_by_column`, `list_datasources`,
   `toggle_datasource`, `save_snapshot`, `list_snapshots`, `query_snapshots`,
   `get_column_provenance`, `update_column_meta`.

2. **Data gateway** (`gateway_tools.py`) — route live data requests to the
   project's 10 data-fetch MCPs (`yfinance`, `edgartools`, `edinet`, `dartlab`,
   `cnreport`, `hkreport`, `akshare`, `ckan`, `cnstats`, `worldbank`), launched
   on demand as stdio subprocesses via `fastmcp.Client`. Their launch configs
   live in the `leader_upstreams` table (seeded from `.mcp.json` by
   `seed_upstreams.py`). Tools: `list_data_mcps`, `list_data_mcp_tools`,
   `call_data_mcp`, `ask_data_crew`, `add_data_mcp`, `remove_data_mcp`,
   `get_data_mcp`. See `openspec/specs/leader-mcp-data-gateway/`.

3. **CrewAI data workflows** (`specialist_agents.py`, `workflow_database.py`,
   `workflow_tools.py`) — the `crewai-data-workflow` capability. See below.

## crewai-data-workflow

Specialist CrewAI agents (one per data-fetch MCP, each with its own LLM)
composed into persisted, step-by-step, resumable data-fetch workflows over the
data gateway.

### Per-agent LLM control — `LEADER_MODELS`

JSON env var `{name: {model, base_url?, api_key?, provider?, vision?}}`
(mirrors `process-mcp`'s `PROCESS_MODELS`). Per-model fields fall back to the
shared `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` from the root `.env`.
Unset → a single `"default"` model from the shared `LLM_*` env, so specialist
agents work with no extra config. Bind an agent to a named model via
`create_specialist_agent(model="fast")`. List with `list_agent_models()`.

The `[crew]` extra (`crewai` + `litellm`) is required **only for the LLM path**.
When `crewai` is unavailable or a model is unconfigured, each step falls back to
a deterministic direct `call_data_mcp` call (keyword-parsed) so a workflow still
runs end-to-end without an LLM — the fallback is recorded in the step's `meta`.

### Tools (10)

| Tool | Purpose |
|------|---------|
| `list_agent_models` | Configured LLMs (api keys never serialized). |
| `create_specialist_agent` | Bind a CrewAI agent to one upstream (+ optional model). |
| `list_specialist_agents` | List agents (surfaces `upstream_missing`). |
| `create_workflow` | Named, ordered workflow. |
| `add_workflow_step` | Add a step (agent + request + optional `depends_on` + `on_fail`). |
| `get_workflow` | Workflow + ordered steps. |
| `list_workflows` | All workflows. |
| `run_workflow` | Run all steps sequentially (fresh run); returns every step's output. |
| `run_workflow_step` | Run one step (resume-or-create `in_progress` run). |
| `get_workflow_run` | Run state + per-step results. |

A step's `output` is the **raw** upstream payload (the `call_data_mcp` result),
not an LLM summary. `depends_on` injects a prior step's raw output as text
context into the next step's request.

### Tables (in `mcp/models/`, via `Base.metadata.create_all`)

`specialist_agents`, `workflows`, `workflow_steps`, `workflow_runs`,
`workflow_step_results`. `workflow→step` and `run→result` are real FKs with
`ON DELETE CASCADE`; `agents.upstream` and `steps.agent` are soft refs (validated
at write time, no FK). Step `output_json` is capped at 1 MB (truncated with a
`_truncated` flag when larger).

### CLI / cron

```bash
# run a workflow in-process (no stdio server) — schedulable via cron-mcp
uv run --directory mcp/leader-mcp python server.py --run-workflow <name>
```

### Seed + self-check

```bash
# upsert one default specialist agent per enabled leader_upstreams row
uv run --directory mcp/leader-mcp python seed_specialist_agents.py        # write
uv run --directory mcp/leader-mcp python seed_specialist_agents.py --dry-run
uv run --directory mcp/leader-mcp python seed_specialist_agents.py --unseed

# offline self-check (temp DB, no crewai/LLM, stub gateway)
uv run --directory mcp/leader-mcp python selfcheck_workflow.py
```
