# leader-mcp

Multi-harness registry + **single-entry MCP gateway** + **CrewAI data workflows**.

`leader-mcp` is the sole client-facing entry in `.mcp.json`. Every other MCP in
the project is reached through it. Three layers, all exposed as MCP tools on
one server (`python server.py`):

1. **Registry** (`leader_tools.py`) — query the unified function registry across
   harnesses: `list_harnesses`, `search_functions`, `get_function_detail`,
   `list_categories`, `find_functions_by_column`, `list_datasources`,
   `toggle_datasource`, `save_snapshot`, `list_snapshots`, `query_snapshots`,
   `get_column_provenance`, `update_column_meta`.

2. **MCP gateway** (`gateway_tools.py`) — route calls to ANY other MCP in the
   project (the 10 data-fetch MCPs `yfinance`, `edgartools`, `edinet`, `dartlab`,
   `cnreport`, `hkreport`, `akshare`, `ckan`, `cnstats`, `worldbank`, PLUS the
   non-data MCPs `cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`,
   `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`), launched on
   demand as stdio subprocesses via `fastmcp.Client`. Launch configs live in the
   `leader_upstreams` table (seeded from `.mcp.json` by `seed_upstreams.py`).

   **Generic tools** (category-agnostic — use these for new callers):
   `list_mcps`, `list_mcp_tools`, `call_mcp`, `add_mcp`, `remove_mcp`, `get_mcp`.

   **Back-compat aliases** (same implementation, kept for `ask_data_crew` and
   the crewai-data-workflow): `list_data_mcps`, `list_data_mcp_tools`,
   `call_data_mcp`, `add_data_mcp`, `remove_data_mcp`, `get_data_mcp`.

   **CrewAI router**: `ask_data_crew` (natural-language data fetch; data-fetch
   upstreams only). See `openspec/specs/leader-mcp-data-gateway/`.

   Reach any upstream from a client (Trae / Claude Code):
   ```
   call_mcp(server="cron-mcp", tool="list_jobs", arguments="{}")
   call_mcp(server="alerts-mcp", tool="list_series", arguments="{}")
   ```

3. **CrewAI data workflows** (`specialist_agents.py`, `workflow_database.py`,
   `workflow_tools.py`) — the `crewai-data-workflow` capability. See below.

## crewai-data-workflow

Specialist CrewAI agents (one per data-fetch MCP, each with its own LLM)
composed into persisted, step-by-step, resumable data-fetch workflows over the
data gateway.

### Per-agent LLM control — `LEADER_MODELS`

JSON env var `{name: {model, base_url?, api_key?, provider?, vision?}}`
(mirrors daas-mcp's `PROCESS_MODELS`). Per-model fields fall back to the
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

## Single-entry-point operations

`leader-mcp` is the only entry in `.mcp.json`. All other MCPs are reached via
`call_mcp(server=..., tool=..., arguments=...)`. Their launch configs live in
`leader_upstreams`, seeded from `.mcp.json` by `seed_upstreams.py`.

### Seed / re-seed upstreams

Run this whenever `.mcp.json` changes (new MCP added, command edited, etc.) —
it upserts every non-`leader-mcp` entry into `leader_upstreams`:

```bash
# leader-mcp's venv (matches .mcp.json)
mcp/leader-mcp/.venv/bin/python mcp/leader-mcp/seed_upstreams.py --dry-run   # preview
mcp/leader-mcp/.venv/bin/python mcp/leader-mcp/seed_upstreams.py             # write

# rollback: delete all seeded rows + print the .mcp.json snippet to restore
mcp/leader-mcp/.venv/bin/python mcp/leader-mcp/seed_upstreams.py --unseed
```

The 10 data-fetch MCPs keep their short names (`yfinance`, `edgartools`, …) so
`ask_data_crew` and the crewai-data-workflow keep resolving. All other MCPs use
their full `.mcp.json` key as the upstream `name` (`cron-mcp`, `alerts-mcp`, …).

### Recursion constraint

`composite-mcp` is itself a gateway. Nesting `leader-mcp → composite-mcp →
<upstream>` works today because composite-mcp's upstreams are disjoint from
leader-mcp's. **`composite-mcp`'s upstreams MUST NOT include `leader-mcp`** —
that would create an infinite spawn loop. No code guard enforces this; it is an
audited invariant. A loop would manifest as a spawn-time hang (not silent
corruption) and be caught immediately.

### Dashboard note

The Next.js dashboard (`dashboard/src/lib/mcp-client.ts`) spawns MCPs by
directory path via `getServerConfig(server)`, NOT from `.mcp.json`. So the
dashboard's direct spawns (e.g. `/chat` → `composite-mcp`, process pages →
`daas-mcp`) are unaffected by the single-entry-point change — `.mcp.json`
governs IDE clients (Trae / Claude Code) only.
