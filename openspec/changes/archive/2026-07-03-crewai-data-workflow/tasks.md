## 1. Shared schema (`mcp/models/`)

- [x] 1.1 Add 5 SQLAlchemy models to `mcp/models/` (shared `Base`): `SpecialistAgent` (`name` unique, `upstream`, `role`, `goal`, `backstory`, `model` nullable, `enabled`, `created_at`), `Workflow` (`name` unique, `description`, `created_at`), `WorkflowStep` (`workflow_id` FK CASCADE, `sort_order`, `agent`, `request`, `depends_on` nullable, `on_fail` default `"continue"`, `model` nullable), `WorkflowRun` (`workflow_id` FK CASCADE, `started_at`, `finished_at`, `status`), `WorkflowStepResult` (`run_id` FK CASCADE, `step_sort_order`, `status`, `output_json`, `error`, `ran_at`, unique `(run_id, step_sort_order)`).
- [x] 1.2 Verify `Base.metadata.create_all` creates all 5 tables on `leader-mcp` start (idempotent, no Alembic); confirm `PRAGMA foreign_keys=ON` so the FK CASCADEs fire.
- [x] 1.3 Reinstall the schema package (`pip install -e mcp/models`) so `leader-mcp` can `from models import SpecialistAgent, Workflow, WorkflowStep, WorkflowRun, WorkflowStepResult`.

## 2. LLM + specialist agent module (`mcp/leader-mcp/specialist_agents.py`)

- [x] 2.1 Extract `_build_llm` from `data_crew.py` into `specialist_agents.py` as a shared `build_llm(model_name: str | None) -> LLM | None` that resolves a named entry from `LEADER_MODELS` JSON (`{name: {model, base_url?, api_key?, provider?}}`) and falls back to `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL`. Add `load_models()` + `list_agent_models()` (mirror `process-mcp`'s `PROCESS_MODELS` parsing, cached).
- [x] 2.2 Update `data_crew.py` to import `build_llm` from `specialist_agents.py` instead of its own `_build_llm` (no behavior change to `ask_data_crew`).
- [x] 2.3 Implement `build_specialist_tools(agent_row)` — returns a CrewAI-safe tool list curried to `agent_row.upstream`: `_call_data_mcp(tool, arguments)` (closes over `server=agent_row.upstream`, calls `call_data_mcp_sync`), `_list_tools()` (wraps `list_data_mcp_tools_sync(agent_row.upstream)`), and for registry-based upstreams (`yfinance`/`akshare`) a `_search_registry(query)` scoped to that harness. Tools use non-`Optional` type hints (CrewAI pydantic constraint that `data_crew.py` already hit).
- [x] 2.4 Implement `run_specialist_step(agent_row, request, model_override=None) -> dict` — builds the one-agent CrewAI `Crew` (`Process.sequential`), kicks it off, returns the stashed raw `call_data_mcp` result (the `_last_result` trick). Records `fallback` metadata when CrewAI is unavailable or the model is unconfigured (returns `{"error": "model '...' not configured"}` without a network call when no LLM can be built).
- [x] 2.5 Implement `_direct_fetch(upstream, request) -> dict` — the deterministic fallback parser (extracted from `DataCrew._ask_direct`): keyword→`(tool, arguments)` mapping for the upstream, terminating in `call_data_mcp_sync`. Used by `run_specialist_step` when CrewAI is missing.

## 3. Workflow persistence + CRUD (`mcp/leader-mcp/workflow_database.py`)

- [x] 3.1 Implement `workflow_database.py` (singleton `Database`, mirrors `gateway_database.py`): CRUD for specialist agents (`create_specialist_agent`, `list_specialist_agents` with `upstream_missing` flag), workflows (`create_workflow`, `get_workflow` with ordered steps, `list_workflows`), and steps (`add_workflow_step` with auto `sort_order`, validates `agent` exists in `specialist_agents`, validates `upstream` exists in `leader_upstreams` at agent-creation time).
- [x] 3.2 Implement run state: `start_run(workflow_id, fresh=False)` (reuse an `in_progress` run unless `fresh`), `finish_run(run_id, status)`, `upsert_step_result(run_id, sort_order, status, output_json, error, meta)`, `get_run(run_id)` (returns run + ordered step results), `list_step_results(run_id)`.
- [x] 3.3 Cap `output_json` storage at 1 MB; truncate-with-flag (`{"_truncated": true, "len": N}`) when exceeded. Validate identifiers against `^[A-Za-z_][A-Za-z0-9_]*$` where dynamic.

## 4. Workflow runner (`mcp/leader-mcp/workflow_tools.py`)

- [x] 4.1 Implement `run_workflow(name) -> dict` — fresh run, iterate enabled `workflow_steps` in `sort_order`, invoke `run_specialist_step` per step, apply `depends_on` injection (prepend prior step's raw output as text context to the request), honor `on_fail` (`continue` vs `stop`), persist each `workflow_step_result`, transition run `running`→`completed`/`failed`. Return `{run_id, status, steps:[...]}`. Never raise out of CrewAI-missing.
- [x] 4.2 Implement `run_workflow_step(name, step_sort_order) -> dict` — resume-or-create `in_progress` run (Decision 7), execute only that one step, persist its result, leave run `in_progress` (unless it is the last step and succeeds → `completed`). Return `{run_id, step_sort_order, status, output}`.
- [x] 4.3 Implement `get_workflow_run(run_id) -> dict` — returns `{run_id, workflow_name, status, started_at, finished_at, steps:[{sort_order, status, output, error, meta}, ...]}`.
- [x] 4.4 Wire all workflow + agent + model tools (`list_agent_models`, `create_specialist_agent`, `list_specialist_agents`, `create_workflow`, `add_workflow_step`, `get_workflow`, `list_workflows`, `run_workflow`, `run_workflow_step`, `get_workflow_run`) as module-level functions with proper type hints + docstrings (FastMCP infers schemas).

## 5. Server registration + CLI branch (`mcp/leader-mcp/server.py`)

- [x] 5.1 `app.add_tool(...)` all 10 new tools from `workflow_tools.py` (next to the existing gateway tools). Keep imports relative (run from within `mcp/leader-mcp/`).
- [x] 5.2 Add `--run-workflow <name>` CLI branch: when argv[1] == `--run-workflow`, run `run_workflow(name)` in-process (no stdio server), print the JSON run summary to stdout, exit 0 on success / non-zero on error (e.g. unknown workflow). Mirror the `process-mcp --run-rule` / `daas-mcp --fetch-item` pattern.
- [x] 5.3 Resolve relative `DAAS_DATABASE_URL` against the repo root inside the `--run-workflow` path (mirror `process-mcp`) so `uv run --directory mcp/leader-mcp python server.py --run-workflow <name>` works.
- [x] 5.4 Fix `server.py` dotenv to load the repo-root `.env` (`parents[2]`, matching `process-mcp` / `daas-mcp` / `cnreport-mcp`) instead of the non-existent `mcp/.env` — required so the specialist-agent LLM path sees `LLM_*` when run as an MCP server. Keep `mcp/` on `sys.path` for `import models`.

## 6. Seed + self-check

- [x] 6.1 `seed_specialist_agents.py` — upsert one default specialist agent per enabled `leader_upstreams` row (name `<upstream>-agent`, role/goal/backstory templated per upstream shape, `model=None` = shared fallback). Idempotent on `name`; flags `--dry-run`, `--unseed`. Safe to run via `uv run --directory mcp/leader-mcp python seed_specialist_agents.py`.
- [x] 6.2 `selfcheck_workflow.py` — temp DB, stub upstream (no real subprocess), force the direct-fallback path (no `crewai`/no LLM). Exercise: `create_specialist_agent` → `create_workflow` → `add_workflow_step` (2 steps, second `depends_on="1"`) → `run_workflow` → assert run `completed` + 2 step results + `depends_on` injection present → `run_workflow_step` resume path → `get_workflow_run`. Print a pass/fail summary; exit non-zero on failure. `uv run --directory mcp/leader-mcp python selfcheck_workflow.py`.

## 7. Docs + env

- [x] 7.1 Document the `LEADER_MODELS` env var and the 10 new tools in `mcp/leader-mcp/` (README or a docstring block in `workflow_tools.py`); note the `[crew]` extra is required only for the LLM path (fallback works without it).
- [x] 7.2 Update root `CLAUDE.md` under the `mcp/leader-mcp/` section: list the new `crewai-data-workflow` capability, the 5 new tables, the `--run-workflow` CLI branch, the `LEADER_MODELS` env, and the seed/self-check commands (mirror the existing per-MCP doc style).
- [x] 7.3 Add `.env.example` entries for `LEADER_MODELS` (commented example JSON) under `mcp/leader-mcp/`.

## 8. Validation

- [x] 8.1 Run `uv run --directory mcp/leader-mcp python selfcheck_workflow.py` — passes.
- [x] 8.2 Run `uv run --directory mcp/leader-mcp python seed_specialist_agents.py --dry-run` — lists one agent per enabled upstream, writes nothing.
- [x] 8.3 Manual smoke (CrewAI installed + `LLM_*` set): create a 2-step workflow (`yfinance-agent` → `edgartools-agent`, step 2 `depends_on="1"`), `run_workflow`, confirm both step outputs are raw fetched data and the run is `completed`. *(Ran via a temp smoke script: both steps completed with `meta={}` (LLM path, no fallback); step 2's strengthened prompt discovered `ticker_or_cik` via `list_tools` and returned 20 real EDGAR filings for Apple.)*
- [x] 8.4 Manual smoke (no `crewai`): same workflow, `run_workflow`, confirm it still completes via the direct fallback and step results carry `{"fallback":"direct",...}` metadata. *(Covered by `selfcheck_workflow.py`, which clears the LLM env and asserts the run completes with `fallback=direct` meta on each step.)*
- [x] 8.5 `openspec validate crewai-data-workflow --strict` passes (spec scenarios well-formed, all `applyRequires` artifacts done).
