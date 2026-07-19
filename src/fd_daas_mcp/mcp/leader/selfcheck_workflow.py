"""Self-check for the crewai-data-workflow capability.

Exercises the full workflow plumbing with NO real subprocess and NO LLM call:
create specialist agent → create workflow → add steps (one depending on the
other) → run_workflow → assert run completed + 2 step results + depends_on
injection present → run_workflow_step resume path → get_workflow_run.

Forces the direct-fallback path by clearing the LLM env (so build_llm returns
the soft "no LLM" reason) and monkeypatching call_data_mcp_sync so no upstream
subprocess is spawned. Uses a temp DB (does not touch mcp/daas.db).

Usage:
    uv run --directory mcp/leader-mcp python selfcheck_workflow.py
    # or:
    .venv/bin/python selfcheck_workflow.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MCP_ROOT = _HERE.parent
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))

from dotenv import load_dotenv

load_dotenv(_MCP_ROOT / ".env")
load_dotenv(_HERE / ".env", override=True)

# Force the direct-fallback path: clear every LLM-related env var AND every
# LEADER_MODEL_* tier var so build_llm("fast") (the null-step default) returns
# the soft "no LLM configured" reason (no network call, no dangling-tier hard error).
for _k in (
    "LEADER_MODELS", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "OPENAI_API_KEY",
    "LEADER_MODEL_HIGH", "LEADER_MODEL_BALANCE", "LEADER_MODEL_FAST",
):
    os.environ.pop(_k, None)

import gateway_database as gdb
import specialist_agents as sa
import workflow_database as wdb
from workflow_tools import (
    add_workflow_step,
    build_workflow_from_goal,
    create_specialist_agent,
    create_workflow,
    delete_specialist_agent,
    get_workflow,
    get_workflow_run,
    list_agent_models,
    list_model_tiers,
    list_specialist_agents,
    run_workflow,
    run_workflow_step,
    update_specialist_agent,
)

sa.reset_models_cache()

# Stub call_data_mcp_sync so _direct_fetch never spawns a subprocess.
_CALL_LOG: list[dict] = []


def _fake_call(server: str, tool: str, arguments: str = "{}") -> dict:
    args = json.loads(arguments) if arguments else {}
    _CALL_LOG.append({"server": server, "tool": tool, "arguments": args})
    return {"server": server, "tool": tool, "result": {"stub": f"data-for-{server}"}, "arguments": args}


sa.call_data_mcp_sync = _fake_call

# Spy on _direct_fetch to capture the (injected) request per upstream.
_DIRECT_REQUESTS: dict[str, str] = {}
_orig_direct = sa._direct_fetch


def _spy_direct(upstream: str, request: str) -> dict:
    _DIRECT_REQUESTS[upstream] = request
    return _orig_direct(upstream, request)


sa._direct_fetch = _spy_direct


def _setup_temp_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    url = f"sqlite:///{tmp.name}"
    os.environ["DAAS_DATABASE_URL"] = url
    gdb.reset_gateway_db()
    gdb.GatewayDatabase(url).init_db()
    wdb.reset_workflow_db()
    wdb.WorkflowDatabase(url).init_db()
    return url


def _check(label: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return cond


def main() -> int:
    failures: list[str] = []
    url = _setup_temp_db()
    print(f"Self-check: crewai-data-workflow (temp DB: {url})")
    print("Forcing direct-fallback path (no crewai/LLM env).")

    # 0. list_agent_models works (default fallback registry)
    models = list_agent_models()
    if not _check("list_agent_models returns a default", "default" in {m["name"] for m in models["models"]}):
        failures.append("list_agent_models")

    # 0b. list_model_tiers returns all-null tiers in the no-LLM env (tier env vars popped)
    tiers = list_model_tiers()
    tiers_ok = (
        set(tiers["tiers"].keys()) == {"high", "balance", "fast"}
        and all(v is None for v in tiers["tiers"].values())
    )
    if not _check("list_model_tiers returns {high,balance,fast} all null (no-LLM env)", tiers_ok, str(tiers["tiers"])):
        failures.append("list_model_tiers")
    # list_agent_models also carries the tiers mapping
    if not _check(
        "list_agent_models carries tiers mapping",
        "tiers" in models and set(models["tiers"].keys()) == {"high", "balance", "fast"},
    ):
        failures.append("list_agent_models.tiers")

    # seed two upstreams so create_specialist_agent's upstream validation passes
    gdb.get_gateway_db().upsert_upstream(name="yfinance", command="echo", args=[])
    gdb.get_gateway_db().upsert_upstream(name="edgartools", command="echo", args=[])

    # 1. create specialist agents
    a1 = create_specialist_agent(name="yfinance-agent", upstream="yfinance", role="YF", goal="fetch yfinance")
    a2 = create_specialist_agent(name="edgar-agent", upstream="edgartools", role="EDGAR", goal="fetch edgar")
    if not _check("create_specialist_agent x2", a1.get("name") == "yfinance-agent" and a2.get("name") == "edgar-agent"):
        failures.append("create_specialist_agent")
    # reject unknown upstream
    bad = create_specialist_agent(name="bad-agent", upstream="nope", role="r", goal="g")
    if not _check("reject unknown upstream", bad.get("error", "").startswith("upstream 'nope'")):
        failures.append("reject-upstream")
    # reject duplicate name
    dup = create_specialist_agent(name="yfinance-agent", upstream="yfinance", role="r", goal="g")
    if not _check("reject duplicate agent name", "already exists" in dup.get("error", "")):
        failures.append("reject-dup")
    # list agents
    la = list_specialist_agents()
    if not _check("list_specialist_agents count==2", la["count"] == 2, str(la["count"])):
        failures.append("list_specialist_agents")

    # 2. create workflow + steps (step 2 depends_on step 1)
    wf = create_workflow(name="aapl-dd", description="due diligence")
    if not _check("create_workflow", wf.get("name") == "aapl-dd"):
        failures.append("create_workflow")
    s1 = add_workflow_step(workflow_name="aapl-dd", agent="yfinance-agent", request="AAPL 1-month price history")
    s2 = add_workflow_step(workflow_name="aapl-dd", agent="edgar-agent", request="latest 10-K for AAPL", depends_on="1")
    if not _check(
        "add_workflow_step x2 (auto sort_order)",
        s1.get("sort_order") == 1 and s2.get("sort_order") == 2,
        f"s1={s1.get('sort_order')} s2={s2.get('sort_order')}",
    ):
        failures.append("add_workflow_step")
    if not _check("step 2 depends_on=['1']", s2.get("depends_on") == ["1"]):
        failures.append("depends_on")
    # reject step with unknown agent
    bad_step = add_workflow_step(workflow_name="aapl-dd", agent="ghost", request="x")
    if not _check("reject step with unknown agent", "not found" in bad_step.get("error", "")):
        failures.append("reject-step-agent")

    # 3. run_workflow — both steps via direct fallback
    r = run_workflow(name="aapl-dd")
    steps_ok = (
        r.get("status") == "completed"
        and len(r.get("steps", [])) == 2
        and all(s["status"] == "completed" for s in r["steps"])
    )
    if not _check("run_workflow completed, 2 steps", steps_ok, f"status={r.get('status')} steps={len(r.get('steps', []))}"):
        failures.append("run_workflow")
    # fallback metadata present on each step
    fb = all(s.get("meta", {}).get("fallback") == "direct" for s in r.get("steps", []))
    if not _check("each step carries fallback=direct meta", fb):
        failures.append("fallback-meta")
    # depends_on injection: step 2's _direct_fetch request contains step 1's output
    inj = "Previous step 1 result" in _DIRECT_REQUESTS.get("edgartools", "")
    if not _check("depends_on injected step 1 output into step 2", inj):
        failures.append("depends_on-injection")
    # step output is raw fetched data (the stub), not an LLM summary
    raw = r["steps"][0]["output"].get("result", {}).get("stub") == "data-for-yfinance"
    if not _check("step output is raw upstream data", raw):
        failures.append("raw-output")

    # 4. get_workflow_run returns state + ordered step results
    gr = get_workflow_run(r["run_id"])
    gr_ok = gr.get("status") == "completed" and gr.get("workflow_name") == "aapl-dd" and len(gr.get("steps", [])) == 2
    if not _check("get_workflow_run returns run + steps", gr_ok):
        failures.append("get_workflow_run")

    # 5. run_workflow_step resume path — fresh in_progress run, runs one step
    r2 = run_workflow_step(name="aapl-dd", step_sort_order=1)
    r2_ok = r2.get("status") == "completed" and r2.get("run_id") != r["run_id"]
    if not _check("run_workflow_step runs one step (new in_progress run)", r2_ok, f"status={r2.get('status')}"):
        failures.append("run_workflow_step")
    # unknown workflow / step
    if not _check("run_workflow_step unknown workflow errors", "not found" in run_workflow_step(name="nope", step_sort_order=1).get("error", "")):
        failures.append("run_workflow_step-unknown-wf")
    if not _check("run_workflow_step unknown step errors", "not found" in run_workflow_step(name="aapl-dd", step_sort_order=99).get("error", "")):
        failures.append("run_workflow_step-unknown-step")

    # 5b. update_specialist_agent — editable fields, model=_UNSET vs None, upstream re-validate, toggle, unknown.
    #     (edgar-agent currently has model=None, enabled=True from creation.)
    u1 = update_specialist_agent(name="edgar-agent", role="New role", goal="New goal", model="high")
    u1_ok = (
        u1.get("role") == "New role"
        and u1.get("goal") == "New goal"
        and u1.get("model") == "high"
        and u1.get("upstream") == "edgartools"       # unchanged
        and u1.get("enabled") is True                 # unchanged
        and u1.get("updated_at")                      # advanced
    )
    if not _check("update sets provided fields, leaves others", u1_ok, str({k: u1.get(k) for k in ("role", "goal", "model", "upstream", "enabled")})):
        failures.append("update-fields")
    # model omitted → unchanged (still "high")
    u2 = update_specialist_agent(name="edgar-agent", role="Another role")
    if not _check("model omitted leaves override unchanged", u2.get("model") == "high", str(u2.get("model"))):
        failures.append("update-model-omitted")
    # model=None explicitly → clears the override
    u3 = update_specialist_agent(name="edgar-agent", model=None)
    if not _check("model=None clears override", u3.get("model") is None, str(u3.get("model"))):
        failures.append("update-model-clear")
    # update re-validates a changed upstream
    bad_up = update_specialist_agent(name="edgar-agent", upstream="nope")
    if not _check("update rejects unknown upstream", bad_up.get("error", "").startswith("upstream 'nope'"), str(bad_up.get("error"))):
        failures.append("update-bad-upstream")
    # update unknown agent
    bad_u = update_specialist_agent(name="ghost-agent", role="x")
    if not _check("update unknown agent errors", "not found" in bad_u.get("error", "")):
        failures.append("update-unknown")
    # toggle enabled=False, then re-enable (so downstream build_workflow_from_goal still sees it)
    u4 = update_specialist_agent(name="edgar-agent", enabled=False)
    if not _check("toggle enabled=False via update", u4.get("enabled") is False, str(u4.get("enabled"))):
        failures.append("update-toggle-off")
    update_specialist_agent(name="edgar-agent", enabled=True)

    # 5c. delete_specialist_agent — unreferenced succeeds, refused-when-referenced, unknown.
    create_specialist_agent(name="throwaway-agent", upstream="yfinance", role="t", goal="t")
    d1 = delete_specialist_agent(name="throwaway-agent")
    if not _check("delete unreferenced agent succeeds", d1.get("deleted") == "throwaway-agent", str(d1)):
        failures.append("delete-unreferenced")
    la2 = list_specialist_agents()
    if not _check("deleted agent no longer listed", "throwaway-agent" not in {a["name"] for a in la2["agents"]}):
        failures.append("delete-confirmed-gone")
    # yfinance-agent is referenced by aapl-dd step 1 → delete must refuse and name the workflow
    d2 = delete_specialist_agent(name="yfinance-agent")
    if not _check("delete refused when referenced by a step", "referenced by workflow" in d2.get("error", "") and "aapl-dd" in d2.get("error", ""), str(d2.get("error"))):
        failures.append("delete-refused-referenced")
    # delete unknown agent
    d3 = delete_specialist_agent(name="ghost-agent")
    if not _check("delete unknown agent errors", "not found" in d3.get("error", "")):
        failures.append("delete-unknown")

    # 6. build_workflow_from_goal direct fallback (no LLM) → one-step workflow + warning.
    #    Goal "yfinance data" keyword-matches the yfinance-agent (upstream/role/goal)
    #    and not the edgar-agent, so the fallback picks yfinance-agent deterministically.
    b = build_workflow_from_goal(goal="yfinance data", name="builder-test")
    b_ok = (
        b.get("name") == "builder-test"
        and len(b.get("steps", [])) == 1
        and b["steps"][0]["agent"] == "yfinance-agent"
        and any("fallback" in w for w in b.get("warnings", []))
    )
    if not _check(
        "build_workflow_from_goal fallback emits one-step workflow",
        b_ok,
        f"name={b.get('name')} steps={len(b.get('steps', []))} agent={b.get('steps', [{}])[0].get('agent') if b.get('steps') else None} warnings={b.get('warnings')}",
    ):
        failures.append("build_workflow_from_goal-fallback")

    # cleanup
    try:
        os.unlink(url.replace("sqlite:///", ""))
    except OSError:
        pass

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed: {failures}")
        return 1
    print("PASS: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
