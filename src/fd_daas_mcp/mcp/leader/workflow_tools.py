"""Workflow + specialist-agent MCP tools for leader-mcp.

Composes the specialist agents (specialist_agents.py) into persisted, step-by-step
data-fetch workflows over the data gateway. This is the orchestration layer of
the `crewai-data-workflow` capability; the agent layer lives in
specialist_agents.py and the persistence layer in workflow_database.py.

Tools (14):
  - `list_agent_models` — configured LLMs (LEADER_MODELS / LLM_* fallback) + tiers.
  - `list_model_tiers` — resolved high/balance/fast tier → model mapping.
  - `create_specialist_agent`, `list_specialist_agents`, `update_specialist_agent`,
    `delete_specialist_agent` — agent registry (full CRUD).
  - `create_workflow`, `add_workflow_step`, `get_workflow`, `list_workflows` —
    workflow definition.
  - `build_workflow_from_goal` — LLM-driven workflow builder (high tier default).
  - `run_workflow` — run all steps sequentially (fresh run).
  - `run_workflow_step` — run one step (resume-or-create in_progress run).
  - `get_workflow_run` — run state + per-step outputs.

The runner is a plain Python loop (not a hierarchical CrewAI crew — see design
Decision 4): each step invokes its specialist agent, captures the raw
`call_data_mcp` result, applies `depends_on` injection, and honors `on_fail`.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from specialist_agents import (
    build_llm,
    list_agent_models,
    list_model_tiers,
    run_specialist_step,
)
from workflow_database import get_workflow_db, _UNSET

# Re-export so server.py can register all 14 tools from one module.
__all__ = [
    "list_agent_models",
    "list_model_tiers",
    "create_specialist_agent",
    "list_specialist_agents",
    "update_specialist_agent",
    "delete_specialist_agent",
    "create_workflow",
    "add_workflow_step",
    "get_workflow",
    "list_workflows",
    "build_workflow_from_goal",
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


def update_specialist_agent(
    name: str,
    role: Optional[str] = None,
    goal: Optional[str] = None,
    backstory: Optional[str] = None,
    model=_UNSET,
    enabled: Optional[bool] = None,
    upstream: Optional[str] = None,
) -> dict:
    """Update editable fields on an existing specialist agent.

    Every field is optional — omitted fields are left unchanged. `name` is
    immutable (rename = delete + create, mirroring process rules). A non-null
    `upstream` is re-validated against `leader_upstreams`; a non-null `model`
    is validated as a safe identifier. `model` is special: omit it (the
    default) to leave the stored value unchanged, or pass `null` explicitly to
    clear the override so the agent falls back to the shared `LLM_*` endpoint.

    Args:
        name: The agent to update (must already exist).
        role: New CrewAI role (optional).
        goal: New CrewAI goal (optional).
        backstory: New CrewAI backstory (optional).
        model: `LEADER_MODELS` entry name to set, `null` to clear the override,
            or omitted to leave unchanged.
        enabled: `true`/`false` to enable/disable, or omitted to leave unchanged.
        upstream: New `leader_upstreams` name to rebind the agent to (optional).
    """
    try:
        return get_workflow_db().update_specialist_agent(
            name=name, role=role, goal=goal, backstory=backstory,
            model=model, enabled=enabled, upstream=upstream,
        )
    except ValueError as exc:
        return _err(exc)


def delete_specialist_agent(name: str) -> dict:
    """Delete a specialist agent by name.

    Refuses with a clear error when any `workflow_steps.agent` row still
    references the agent (the soft ref would silently break workflows);
    delete or re-point the step first. Returns `{"deleted": name}` on success.

    Args:
        name: The agent to delete (must already exist).
    """
    try:
        return get_workflow_db().delete_specialist_agent(name=name)
    except ValueError as exc:
        return _err(exc)


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


# ═══════════════════════════════════════════════════════════════
# MCP tools — LLM-driven workflow builder
# ═══════════════════════════════════════════════════════════════


def _slugify_goal(goal: str) -> str:
    """Derive a kebab-case workflow name from a goal.

    `_validate_ident` requires `^[A-Za-z][A-Za-z0-9_\\-]*$`, so the result is
    lowercased, non-alphanumerics collapsed to hyphens, and prefixed with
    `wf-` when it does not start with a letter. Truncated to 48 chars.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", goal).strip("-").lower()
    if not slug:
        slug = "workflow"
    if not slug[0].isalpha():
        slug = f"wf-{slug}"
    return slug[:48]


def _unique_workflow_name(db, name: str) -> str:
    """Append `-2`, `-3`, … to `name` until it does not collide with an existing workflow."""
    existing = {w["name"] for w in db.list_workflows()}
    if name not in existing:
        return name
    i = 2
    while f"{name}-{i}" in existing:
        i += 1
    return f"{name}-{i}"


def _parse_steps(raw: str) -> list[dict]:
    """Extract a JSON array of step objects from LLM output text.

    Tolerates ```json fences and surrounding prose. Each step is normalized to
    `{agent, request, depends_on (str|None), on_fail}`. Returns `[]` on failure.
    """
    if not raw:
        return []
    # strip ```json ... ``` fences
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.S)
    candidate = m.group(1) if m else None
    if candidate is None:
        # fall back to the outermost [ ... ] span
        lo, hi = raw.find("["), raw.rfind("]")
        if lo != -1 and hi != -1 and hi > lo:
            candidate = raw[lo:hi + 1]
    if candidate is None:
        return []
    try:
        arr = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    steps: list[dict] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        agent = item.get("agent")
        if not isinstance(agent, str) or not agent:
            continue
        request = item.get("request")
        if not isinstance(request, str) or not request:
            continue
        dep = item.get("depends_on")
        if dep is None or dep == "":
            dep = None
        elif isinstance(dep, list):
            dep = ",".join(str(d) for d in dep) if dep else None
        else:
            dep = str(dep)
        on_fail = item.get("on_fail", "continue")
        if on_fail not in ("continue", "stop"):
            on_fail = "continue"
        steps.append({"agent": agent, "request": request, "depends_on": dep, "on_fail": on_fail})
    return steps


def _builder_fallback(
    db, goal: str, name: str, description: Optional[str],
    enabled_agents: list[dict], warnings: list[str], reason: str,
) -> dict:
    """Deterministic single-step fallback for `build_workflow_from_goal`.

    Picks the first enabled specialist agent whose upstream/role/goal
    keyword-matches `goal` (else the first enabled agent), persists a one-step
    workflow with the original goal as the request, and records the fallback in
    `warnings`. Never raises.
    """
    q_tokens = [t for t in re.split(r"\W+", goal.lower()) if len(t) > 2]
    chosen = None
    for a in enabled_agents:
        hay = f"{a.get('upstream','')} {a.get('role','')} {a.get('goal','')}".lower()
        if any(tok in hay for tok in q_tokens):
            chosen = a
            break
    if chosen is None:
        chosen = enabled_agents[0]
    name = _unique_workflow_name(db, name)
    try:
        db.create_workflow(name=name, description=description)
    except ValueError as exc:
        return {"error": str(exc)}
    db.add_workflow_step(
        workflow_name=name, agent=chosen["name"], request=goal,
        depends_on=None, on_fail="continue", sort_order=1,
    )
    wf = db.get_workflow(name)
    warnings.append(f"fallback: direct ({reason})")
    wf["warnings"] = warnings
    return wf


def build_workflow_from_goal(
    goal: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    model: Optional[str] = "high",
) -> dict:
    """Build a workflow from a natural-language goal using an LLM.

    Decomposes `goal` into an ordered list of specialist-agent steps, persists
    them via the existing `create_workflow` + `add_workflow_step` path, and
    returns the created workflow (same shape as `get_workflow`) plus a
    `warnings` list. Defaults to the `high` tier; a caller MAY pass `model=
    "balance"`, `"fast"`, a concrete `LEADER_MODELS` name, or `null` (which
    resolves to the `fast` tier).

    When `crewai` is unavailable or the model cannot be built, falls back to a
    deterministic single-step workflow — never raises.

    Args:
        goal: Natural-language description of what the workflow should accomplish.
        name: Optional workflow name (kebab-case). Derived from `goal` if omitted.
        description: Optional human-readable description.
        model: LLM to plan with — tier alias, concrete `LEADER_MODELS` name, or null.
    """
    db = get_workflow_db()
    warnings: list[str] = []

    if not goal or not goal.strip():
        return {"error": "goal must be a non-empty string"}

    base_name = _slugify_goal(goal) if name is None else name
    name = _unique_workflow_name(db, base_name)

    agents = db.list_specialist_agents()
    enabled_agents = [a for a in agents if a.get("enabled", True)]
    if not enabled_agents:
        return {"error": "no enabled specialist agents; run seed_specialist_agents.py"}

    # `null` model → fast tier (matches run_workflow step semantics)
    model_name = model if model is not None else "fast"
    llm, error, reason = build_llm(model_name)

    if llm is None:
        # hard error (dangling tier / missing model) → no plan, but still emit a
        # single-step fallback so the caller gets a runnable workflow. Soft
        # "no LLM" also lands here. Surface the reason in warnings.
        return _builder_fallback(
            db, goal, name, description, enabled_agents, warnings,
            error or reason or "no LLM",
        )

    try:
        from crewai import Agent, Crew, Process, Task  # type: ignore
    except ImportError:
        return _builder_fallback(
            db, goal, name, description, enabled_agents, warnings, "crewai unavailable",
        )

    agent_names = [a["name"] for a in enabled_agents]
    agent_catalog = "\n".join(
        f"- {a['name']} (upstream={a.get('upstream','')}, role={a.get('role','')}, goal={a.get('goal','')})"
        for a in enabled_agents
    )

    planner = Agent(
        role="workflow planner",
        goal="Decompose the user's data goal into an ordered list of specialist-agent steps.",
        backstory=(
            "You plan data-fetch workflows by selecting the right specialist agents "
            "and ordering their steps. You always emit strict JSON."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )

    def _plan_task(extra: str = "") -> Task:
        return Task(
            description=(
                f"User goal: {goal}\n\n"
                f"Available specialist agents:\n{agent_catalog}\n\n"
                f"Decompose the goal into 1-5 ordered steps. Each step MUST use one of "
                f"the listed agent names. Output STRICT JSON only — an array of objects "
                f'with keys "agent" (one of: {", ".join(agent_names)}), "request" '
                f'(the natural-language data request), "depends_on" (comma-separated '
                f'prior step numbers as a string, or null), "on_fail" ("continue" or '
                f'"stop"). No prose, no markdown fences.'
                + (f"\n\n{extra}" if extra else "")
            ),
            expected_output="A JSON array of step objects.",
            agent=planner,
        )

    raw_output = ""
    try:
        result = Crew(agents=[planner], tasks=[_plan_task()], process=Process.sequential, verbose=False).kickoff()
        raw_output = str(result)
    except Exception as exc:  # noqa: BLE001 — any crew failure → fallback
        return _builder_fallback(
            db, goal, name, description, enabled_agents, warnings,
            f"crew error: {type(exc).__name__}: {exc}",
        )

    steps = _parse_steps(raw_output)
    if not steps:
        return _builder_fallback(
            db, goal, name, description, enabled_agents, warnings,
            "could not parse LLM step output",
        )

    # Validate agent names; re-prompt once if any are invalid.
    valid_names = set(agent_names)
    invalid = [s for s in steps if s["agent"] not in valid_names]
    if invalid:
        bad = ", ".join(s["agent"] for s in invalid)
        try:
            r2 = Crew(
                agents=[planner],
                tasks=[_plan_task(
                    f"Your previous output referenced unknown agents: {bad}. "
                    f"Re-emit the FULL step list as STRICT JSON using only valid agents."
                )],
                process=Process.sequential, verbose=False,
            ).kickoff()
            steps = _parse_steps(str(r2)) or steps
        except Exception:  # noqa: BLE001 — keep original steps; invalid ones dropped below
            pass

    # Persist the workflow + valid steps.
    try:
        db.create_workflow(name=name, description=description)
    except ValueError as exc:
        return {"error": str(exc)}

    sort_order = 0
    for s in steps:
        if s["agent"] not in valid_names:
            warnings.append(f"dropped step referencing unknown agent '{s['agent']}'")
            continue
        sort_order += 1
        try:
            db.add_workflow_step(
                workflow_name=name, agent=s["agent"], request=s["request"],
                depends_on=s["depends_on"], on_fail=s["on_fail"], sort_order=sort_order,
            )
        except ValueError as exc:
            warnings.append(f"dropped step (agent='{s['agent']}'): {exc}")

    if sort_order == 0:
        # all steps invalid → replace the empty workflow with a single-step fallback
        warnings.append("all LLM steps referenced unknown agents; falling back")
        return _builder_fallback(
            db, goal, base_name, description, enabled_agents, warnings, "no valid steps after validation",
        )

    wf = db.get_workflow(name)
    wf["warnings"] = warnings
    return wf
