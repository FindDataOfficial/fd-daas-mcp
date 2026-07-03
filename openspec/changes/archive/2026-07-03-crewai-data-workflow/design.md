## Context

`leader-mcp` is the project's single client-facing gateway for live data. It owns:
- `call_data_mcp(server, tool, arguments)` — the deterministic primitive that spawns a data-fetch MCP via `fastmcp.Client` and calls one tool (in `gateway_tools.py`).
- `ask_data_crew(question)` — one CrewAI "Data Access Manager" agent that routes a natural-language request to one upstream and fetches one result, with a deterministic direct router fallback (in `data_crew.py`). The spec for this is `leader-mcp-data-gateway` > "CrewAI agent manages data access".

The project's LLM env is a single shared OpenAI-compatible endpoint: `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL`. `process-mcp` already generalizes this into a multi-model registry via `PROCESS_MODELS` JSON (`{name: {model, vision?, base_url?, api_key?}}`) — a pattern we will mirror. `crewai` + `litellm` are already an optional `[crew]` extra on `leader-mcp`.

The gap: there is no way to (a) run *several* specialized agents — one per data source — each on its own LLM, nor (b) compose them into a *multi-step workflow* whose intermediate results are visible and reusable. `ask_data_crew` is a one-shot single-agent black box.

Stakeholders: this change lives entirely in `leader-mcp` (per the user's "access the data in leader-mcp"). It reuses `call_data_mcp` as its fetch primitive and reuses `mcp/models` + `mcp/daas.db` for persistence, matching the project's unified-schema convention.

## Goals / Non-Goals

**Goals:**
- A registry of **specialist CrewAI agents**, each bound to exactly one data-fetch MCP upstream, with tool access curried to that upstream.
- **Per-agent LLM control** via a `LEADER_MODELS` multi-model env (with shared `LLM_*` fallback), so different agents can use different models.
- **Persisted, step-by-step workflows** over those agents: define once, run all-at-once or one-step-at-a-time, with per-step results captured and chainable via `depends_on`.
- **Graceful degradation**: a workflow runs end-to-end even when `crewai` is not installed or a model is unconfigured, by falling back to the existing direct `call_data_mcp` path.
- **Cron-drivable**: a `--run-workflow <name>` CLI branch so workflows can be scheduled by `cron-mcp`.

**Non-Goals:**
- Replacing `ask_data_crew`. It stays as-is for one-shot NL fetches; this adds a parallel specialist+workflow surface.
- Structured dataflow between steps. `depends_on` injects a prior step's raw output as text context into the next step's request — it is not a typed column/row pipeline (that is the job of `daas-mcp` pipeline collections + `process-mcp`).
- Persisting fetched data into the daas `observations`/`sources` registry. Step outputs live in `workflow_step_results` and are queryable via `dashboard-mcp.query_table`; that is sufficient for this change.
- A hierarchical CrewAI "manager agent" that delegates. The workflow runner is a plain Python loop; only the specialist agents are LLM agents (see Decision 4).

## Decisions

### Decision 1: Extend `leader-mcp`, do not create a new MCP server
The user's ask is explicitly "use crewai agent to access the data **in leader-mcp**". `leader-mcp` already owns the data gateway (`call_data_mcp`) and the existing CrewAI crew (`data_crew.py`), and already carries the optional `[crew]` extra. Adding the new tools + tables here keeps one client-facing gateway and reuses the existing fetch primitive + LLM env.
- **Alternative considered**: a new `workflow-mcp/` server. Rejected — it would have to re-implement or re-import `call_data_mcp` and the LLM builder, and would split the "data gateway" surface across two servers. Not worth the boundary.

### Decision 2: Specialist agent = CrewAI `Agent` with a curried `call_data_mcp`
Each specialist agent's tool list is built per-agent at run time: a thin wrapper closes over `server=<agent.upstream>` and calls the existing `call_data_mcp_sync(server, tool, arguments)`. This guarantees an agent can only fetch from its bound upstream (satisfies the "special agent for special mcp" requirement) without duplicating the gateway logic.
- **Alternative considered**: give every agent the general `call_data_mcp` and rely on the agent's prompt to stay on its upstream. Rejected — an LLM will happily call another `server` if it thinks that serves the goal; currying is a hard guarantee.

### Decision 3: Per-agent LLM via `LEADER_MODELS`, mirroring `PROCESS_MODELS`
A `LEADER_MODELS` JSON env `{name: {model, base_url?, api_key?, provider?}}` is parsed + cached. Each agent's `model` field names an entry; null → shared `LLM_*` fallback. The `_build_llm` helper is extracted from `data_crew.py` into a shared module (`specialist_agents.py`) so both `DataCrew` and the specialist agents use one resolver.
- **Alternative considered**: reuse `PROCESS_MODELS` directly. Rejected — process-mcp's models are tuned for extraction (vision flag, chunking); leader-mcp's are for reasoning/routing. Keeping the registries separate avoids coupling two MCPs' model choices, even though the shape is identical.
- **Alternative considered**: one model per workflow, not per agent. Rejected — the user explicitly wants to "control the llm used in agent", which means per-agent granularity (e.g. a cheap model for the yfinance agent, a strong model for the edgar agent that has to read filings).

### Decision 4: Workflow runner is a plain Python loop, not a hierarchical CrewAI crew
`run_workflow` iterates `workflow_steps` in `sort_order`, invokes each step's specialist agent (a one-agent CrewAI `Crew` per step), captures the step's `call_data_mcp` result, applies `depends_on` injection, and honors `on_fail`. The "workflow" is the loop; the LLM agents are the specialists.
- **Alternative considered**: one hierarchical CrewAI `Crew(process=hierarchical)` with a manager agent delegating to specialist agents. Rejected — CrewAI's hierarchical mode forbids the manager from holding tools, and our specialist agents *are* the tool-holders; composing N tool-holding agents under a non-tool manager fights the framework. A Python loop gives us deterministic ordering, resumability (`run_workflow_step`), and `on_fail` control that a CrewAI crew would not expose.

### Decision 5: Step result = the raw `call_data_mcp` payload, not an LLM summary
A step's `output_json` is the upstream's raw fetched data (what `call_data_mcp` returns), captured via the stashed-result trick `data_crew.py` already uses (`self._last_result`). The LLM's job is to *route and call*; it does not summarize unless the agent's `goal` explicitly says to transform. This keeps workflows composable and inspectable.
- **Alternative considered**: let each agent return free-form text. Rejected — downstream steps and `dashboard-mcp` queries need structured data, not prose.

### Decision 6: Persistence — 5 new tables in `mcp/models/`, `Base.metadata.create_all`
`specialist_agents`, `workflows`, `workflow_steps`, `workflow_runs`, `workflow_step_results` — all in the shared `Base`, created idempotently. Soft refs (no FK) from `specialist_agents.upstream` → `leader_upstreams.name` and from `workflow_steps.agent` → `specialist_agents.name`, because upstreams/agents are managed by different tools and a hard FK would block rename/disable flows. `workflow_steps` → `workflows` and `workflow_step_results` → `workflow_runs` are real FKs with `ON DELETE CASCADE`.
- **Alternative considered**: store workflows as JSON in one row. Rejected — per-step query/inspect (and `dashboard-mcp.query_table`) want normalized rows; the project's own `pipeline_collections` uses normalized tables for the same reason.

### Decision 7: `run_workflow_step` reuse rule — one `in_progress` run per workflow
`run_workflow_step(name, sort_order)` creates a new `workflow_runs` row only if no `in_progress` run exists for that workflow; otherwise it resumes the existing run. This makes interactive stepping natural ("run step 1", inspect, "run step 2", …) without the caller tracking a run id. `run_workflow(name)` always starts a fresh run.

### Decision 8: Fallback reuses `data_crew.py`'s direct-router parsing
When `crewai` is missing or a model is unconfigured, a step calls a shared `_direct_fetch(upstream, request)` helper (extracted from `DataCrew._ask_direct`'s keyword→`(tool, arguments)` mapping) and terminates in `call_data_mcp_sync`. The fallback is recorded in the step result's metadata so it is never silent, and the workflow never raises purely because CrewAI is absent.

## Risks / Trade-offs

- **[LLM cost/latency per step]** → Each step is a full CrewAI agent kickoff; a 5-step workflow is 5 LLM round-trips. Mitigation: per-agent model choice (Decision 3) lets cheap models handle cheap steps; the direct fallback (Decision 8) skips the LLM entirely when CrewAI is absent. Document expected cost in the seed/README.
- **[Large step outputs in SQLite]** → `output_json` could be large (e.g. a year of daily prices). Mitigation: cap `output_json` at a sane size (e.g. 1 MB) and truncate-with-flag if exceeded; full data is re-fetchable via `call_data_mcp`. State the cap in the spec scenario.
- **[Soft-ref drift]** → Renaming a `leader_upstreams` row orphans the bound specialist agent (no FK). Mitigation: `create_specialist_agent` validates the upstream exists at creation; `list_specialist_agents` surfaces a `upstream_missing` flag when the bound upstream no longer exists.
- **[CrewAI Python-version pin]** → `crewai` needs Python < 3.14 (chromadb/pydantic-v1). Mitigation: the fallback path keeps workflows functional on any Python; CrewAI is opt-in via `[crew]` exactly as today.
- **[`depends_on` is textual injection, not typed dataflow]** → A later step receives the prior step's raw output as prepended context, not as structured kwargs. Mitigation: documented as a Non-Goal; typed pipelines remain the domain of `daas-mcp` pipeline collections.
- **[Resumable-run ambiguity]** → Two callers calling `run_workflow_step` concurrently on the same workflow would race on the `in_progress` run. Mitigation: acceptable for the interactive, single-user MCP use case; document that concurrent stepping is unsupported.

## Migration Plan

1. **Schema** — add the 5 tables to `mcp/models/` and let `Base.metadata.create_all` create them on next `leader-mcp` start (idempotent; no data to migrate, no Alembic).
2. **Code** — add `specialist_agents.py`, `workflow_tools.py`, `workflow_database.py`; register the ~10 new tools in `server.py`; add the `--run-workflow` CLI branch; refactor `_build_llm` out of `data_crew.py` into `specialist_agents.py` (import it back into `data_crew.py`).
3. **Seed** — `uv run --directory mcp/leader-mcp python seed_specialist_agents.py` upserts one default specialist agent per enabled `leader_upstreams` row (idempotent; `--dry-run` / `--unseed`).
4. **Self-check** — `uv run --directory mcp/leader-mcp python selfcheck_workflow.py` exercises create-agent → create-workflow → add-step → run-workflow with a stub upstream and no LLM (forces the direct fallback path).
5. **Rollback** — remove the new tool registrations from `server.py`, drop the 5 tables (`DROP TABLE workflow_step_results; DROP TABLE workflow_runs; DROP TABLE workflow_steps; DROP TABLE workflows; DROP TABLE specialist_agents;`). No existing table or tool is modified, so rollback is clean.

## Open Questions

- **Default `on_fail` policy**: spec defaults to `"continue"` so a workflow gathers as much data as possible. Is that preferred over `"stop"` for the seeded default agents? (Lean: `continue` — a data-gathering workflow usually wants partial results; a step's `error` is still recorded.)
- **Should `run_workflow` support a `model` override for the whole run** (run every step with a strong model for a one-off)? The spec allows per-step `model` override already; a run-level override is syntactic sugar. Defer until requested.
- **Should step outputs optionally be indexed into `process-mcp` / Elasticsearch for cross-workflow search?** Out of scope here; flagged as a future capability.
