"""Workflow + specialist-agent MCP tools for leader-mcp.

Composes the specialist agents (specialist_agents.py) into persisted, step-by-step
data-fetch workflows over the data gateway. This is the orchestration layer of
the `crewai-data-workflow` capability; the agent layer lives in
specialist_agents.py and the persistence layer in workflow_database.py.

Tools (10):
  - `list_agent_models` — configured LLMs (LEADER_MODELS / LLM_* fallback).
  - `create_specialist_agent`, `list_specialist_agents` — agent registry.
  - `create_workflow`, `add_workflow_step`, `get_workflow`, `list_workflows` —
    workflow definition.
  - `run_workflow` — run all steps sequentially (fresh run).
  - `run_workflow_step` — run one step (resume-or-create in_progress run).
  - `get_workflow_run` — run state + per-step outputs.

The runner is a plain Python loop (not a hierarchical CrewAI crew — see design
Decision 4): each step invokes its specialist agent, captures the raw
`call_data_mcp` result, applies `depends_on` injection, and honors `on_fail`.
"""
from __future__ import annotations

import json
from typing import Optional

from specialist_agents import list_agent_models, run_specialist_step
from workflow_database import get_workflow_db

# Re-export so server.py can register all 10 tools from one module.
__all__ = [
    "list_agent_models",
    "create_specialist_agent",
    "list_specialist_agents",
    "create_workflow",
    "add_workflow_step",
    "get_workflow",
    "list_workflows",
    "run_workflow",
    "run_workflow_step",
    "get_workflow_run",
]

# Max chars of a prior step's output to inject into a dependent step's request
# (keeps the LLM context bounded; the full output is still in workflow_step_results).
_DEP_INJECT_CHARS = 2000


def _err(exc: Exception) -> dict:
    return {"error": str(exc)}


def _inject_deps(request: str, step: dict, run_id: int) -> str:
    """Prepend the raw output of each `depends_on` step (from this run) to the
    request as text context. No-op when the step has no deps or no prior results
    are stored yet (e.g. running step 1 of a fresh run)."""
    deps = step.get("depends_on") or []
    if not deps:
        return request
    db = get_workflow_db()
    chunks: list[str] = []
    for dep in deps:
        try:
            dep_so = int(dep)
        except (ValueError, TypeError):
            continue
        res = db.get_step_result(run_id, dep_so)
        if res is None:
            continue
        out = res.get("output")
        if out is None:
            continue
        snippet = json.dumps(out, default=str)
        if len(snippet) > _DEP_INJECT_CHARS:
            snippet = snippet[:_DEP_INJECT_CHARS] + f"... (truncated, full len={len(snippet)})"
        chunks.append(f"Previous step {dep_so} result: {snippet}")
    if not chunks:
        return request
    return "\n".join(chunks) + f"\n\nRequest: {request}"


def _run_one_step(step: dict, run_id: int) -> dict:
    """Fetch the step's specialist agent, inject deps, run it, persist the
    result. Returns the result summary `{sort_order, agent, status, output,
    error, meta}`."""
    db = get_workflow_db()
    agent = db.get_specialist_agent(step["agent"])
    if agent is None:
        res = {
            "status": "failed",
            "output": None,
            "error": f"specialist agent '{step['agent']}' not found",
            "meta": {},
        }
    else:
        request = _inject_deps(step["request"], step, run_id)
        res = run_specialist_step(agent, request, model_override=step.get("model"))
    db.upsert_step_result(
        run_id=run_id,
        step_sort_order=step["sort_order"],
        status=res["status"],
        output=res["output"],
        error=res.get("error"),
        meta=res.get("meta"),
    )
    return {
        "sort_order": step["sort_order"],
        "agent": step["agent"],
        "status": res["status"],
        "output": res["output"],
        "error": res.get("error"),
        "meta": res.get("meta"),
    }


def _all_enabled_steps_completed(run_id: int, steps: list) -> bool:
    """True when every enabled step has a `completed` result in this run."""
    db = get_workflow_db()
    for step in steps:
        if not step.get("enabled", True):
            continue
        res = db.get_step_result(run_id, step["sort_order"])
        if res is None or res.get("status") != "completed":
            return False
    return True


# ═══════════════════════════════════════════════════════════════
# MCP tools — model registry
# ═══════════════════════════════════════════════════════════════


# list_agent_models is imported from specialist_agents (see import above).


# ═══════════════════════════════════════════════════════════════
# MCP tools — specialist agents
# ═══════════════════════════════════════════════════════════════


def create_specialist_agent(
    name: str,
    upstream: str,
    role: str,
    goal: str,
    backstory: Optional[str] = None,
    model: Optional[str] = None,
    enabled: bool = True,
) -> dict:
    """Create a CrewAI specialist agent bound to one data-fetch MCP upstream.

    The agent's `call_data_mcp` tool is curried to `upstream` at run time, so it
    can only fetch from that MCP. `model` names an entry in `LEADER_MODELS`
    (null = shared `LLM_*` fallback).

    Args:
        name: Unique agent name (letters, digits, underscore, hyphen).
        upstream: A `leader_upstreams` name (e.g. 'edgartools') — must exist.
        role: CrewAI agent role.
        goal: CrewAI agent goal.
        backstory: Optional CrewAI backstory.
        model: Optional `LEADER_MODELS` entry name; null = shared fallback.
        enabled: If False, the agent is stored but skipped by runners.
    """
    try:
        return get_workflow_db().create_specialist_agent(
            name=name, upstream=upstream, role=role, goal=goal,
            backstory=backstory, model=model, enabled=enabled,
        )
    except ValueError as exc:
        return _err(exc)


def list_specialist_agents() -> dict:
    """List all specialist agents. Each entry carries an `upstream_missing`
    flag when the bound `leader_upstreams` row no longer exists."""
    agents = get_workflow_db().list_specialist_agents()
    return {"count": len(agents), "agents": agents}


# ═══════════════════════════════════════════════════════════════
# MCP tools — workflows
# ═══════════════════════════════════════════════════════════════


def create_workflow(name: str, description: Optional[str] = None) -> dict:
    """Create a named, ordered workflow of data-fetch steps.

    Args:
        name: Unique workflow name (letters, digits, underscore, hyphen).
        description: Optional human-readable description.
    """
    try:
        return get_workflow_db().create_workflow(name=name, description=description)
    except ValueError as exc:
        return _err(exc)


def add_workflow_step(
    workflow_name: str,
    agent: str,
    request: str,
    depends_on: Optional[str] = None,
    on_fail: str = "continue",
    model: Optional[str] = None,
    sort_order: Optional[int] = None,
) -> dict:
    """Add a step to a workflow.

    Args:
        workflow_name: The workflow to add to.
        agent: A specialist agent name (must exist).
        request: The natural-language data request for this step.
        depends_on: Comma-separated prior step sort_orders whose raw output is
                    injected into this step's request (e.g. "1" or "1,2").
        on_fail: 'continue' (default) or 'stop' — whether the run continues
                  past a failed step.
        model: Optional per-step LLM override (LEADER_MODELS name).
        sort_order: Optional explicit position; auto-assigned (max+1) if omitted.
    """
    try:
        return get_workflow_db().add_workflow_step(
            workflow_name=workflow_name, agent=agent, request=request,
            depends_on=depends_on, on_fail=on_fail, model=model, sort_order=sort_order,
        )
    except ValueError as exc:
        return _err(exc)


def get_workflow(name: str) -> dict:
    """Get a workflow + its ordered steps."""
    wf = get_workflow_db().get_workflow(name)
    if wf is None:
        return {"error": f"workflow '{name}' not found"}
    return wf


def list_workflows() -> dict:
    """List all workflows (name, description, step_count, created_at)."""
    wfs = get_workflow_db().list_workflows()
    return {"count": len(wfs), "workflows": wfs}


# ═══════════════════════════════════════════════════════════════
# MCP tools — execution
# ═══════════════════════════════════════════════════════════════


def run_workflow(name: str) -> dict:
    """Run every enabled step of a workflow sequentially (fresh run).

    Each step invokes its specialist agent (CrewAI when available + configured,
    else the deterministic direct fallback), captures the raw fetched data,
    applies `depends_on` injection, and honors `on_fail`. Returns the run id,
    final status (`completed` if no step failed, else `failed`), and per-step
    results. Never raises out of CrewAI-missing — the direct fallback keeps
    data flowing.

    Args:
        name: The workflow to run.
    """
    db = get_workflow_db()
    wf = db.get_workflow(name)
    if wf is None:
        return {"error": f"workflow '{name}' not found"}

    run = db.start_run(wf["id"], fresh=True, status="running")
    run_id = run["id"]
    steps_out: list[dict] = []
    any_failed = False

    for step in wf["steps"]:
        if not step.get("enabled", True):
            continue
        res = _run_one_step(step, run_id)
        steps_out.append(res)
        if res["status"] == "failed":
            any_failed = True
            if step.get("on_fail", "continue") == "stop":
                break

    final_status = "failed" if any_failed else "completed"
    db.finish_run(run_id, final_status)
    return {
        "run_id": run_id,
        "workflow_name": name,
        "status": final_status,
        "steps": steps_out,
    }


def run_workflow_step(name: str, step_sort_order: int) -> dict:
    """Run one step of a workflow (interactive stepping).

    Resumes an existing `in_progress` run for this workflow if one exists,
    otherwise starts a new `in_progress` run. Executes only the named step,
    persists its result, and leaves the run `in_progress` (so a later
    `run_workflow_step` on the next sort_order continues the same run) —
    unless this was the last enabled step and it completed, in which case
    the run transitions to `completed`.

    Args:
        name: The workflow name.
        step_sort_order: The step's sort_order to run.
    """
    db = get_workflow_db()
    wf = db.get_workflow(name)
    if wf is None:
        return {"error": f"workflow '{name}' not found"}

    step = next((s for s in wf["steps"] if s["sort_order"] == step_sort_order), None)
    if step is None:
        return {"error": f"step sort_order {step_sort_order} not found in workflow '{name}'"}

    run = db.start_run(wf["id"], fresh=False, status="in_progress")
    run_id = run["id"]
    res = _run_one_step(step, run_id)

    # Transition to completed only when this step completed AND every enabled
    # step now has a completed result. Otherwise leave in_progress for resuming.
    if res["status"] == "completed" and _all_enabled_steps_completed(run_id, wf["steps"]):
        db.finish_run(run_id, "completed")
    return {
        "run_id": run_id,
        "step_sort_order": step_sort_order,
        "status": res["status"],
        "output": res["output"],
        "error": res.get("error"),
        "meta": res.get("meta"),
    }


def get_workflow_run(run_id: int) -> dict:
    """Get a run's state + ordered per-step results.

    Args:
        run_id: The run id (from run_workflow / run_workflow_step).
    """
    run = get_workflow_db().get_run(run_id)
    if run is None:
        return {"error": f"run {run_id} not found"}
    return run
