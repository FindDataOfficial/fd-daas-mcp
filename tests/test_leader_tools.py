"""leader_tools tests: gateway upstream CRUD, specialist-agent CRUD (with the
dangling-upstream flag + delete-refused-when-referenced guard), and workflow
create/add-step/get.

Calls the leader tool handlers directly (gateway_tools + workflow_tools). The
CrewAI crew path and live upstream subprocess calls (`gateway_database.build_client`)
are never invoked - only the SQLite-backed management CRUD. No LLM call, no
network, no subprocess.

Key coupling mirrored in the tests: `create_specialist_agent` validates
`upstream` against `leader_upstreams` (so a gateway upstream is added first),
and `add_workflow_step` validates `agent` against `specialist_agents` (so an
agent is created first). `delete_specialist_agent` refuses when a workflow step
still references the agent.

Convention: upstreams/agents/workflows this module creates are prefixed
`zz_test_` and torn down by `_cleanup_leader()` in every test.
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

_LEADER_MCP = Path(__file__).resolve().parents[1] / "src" / "fd_daas_mcp" / "mcp" / "leader"
sys.path.insert(0, str(_LEADER_MCP))
from workflow_database import get_workflow_db  # noqa: E402
import gateway_tools  # noqa: E402
import workflow_tools  # noqa: E402


def _cleanup_leader() -> None:
    eng = get_workflow_db().engine  # triggers init_db (creates tables) if needed
    with eng.begin() as conn:
        # Children first (FK cascade would handle some, but be explicit + ordered).
        conn.execute(text(
            "DELETE FROM workflow_step_results WHERE run_id IN ("
            "  SELECT id FROM workflow_runs WHERE workflow_id IN ("
            "    SELECT id FROM workflows WHERE name LIKE 'zz_test_%'))"
        ))
        conn.execute(text(
            "DELETE FROM workflow_runs WHERE workflow_id IN ("
            "  SELECT id FROM workflows WHERE name LIKE 'zz_test_%')"
        ))
        conn.execute(text(
            "DELETE FROM workflow_steps WHERE workflow_id IN ("
            "  SELECT id FROM workflows WHERE name LIKE 'zz_test_%')"
        ))
        conn.execute(text("DELETE FROM workflow_steps WHERE agent LIKE 'zz_test_%'"))
        conn.execute(text("DELETE FROM workflows WHERE name LIKE 'zz_test_%'"))
        conn.execute(text("DELETE FROM specialist_agents WHERE name LIKE 'zz_test_%'"))
        conn.execute(text("DELETE FROM leader_upstreams WHERE name LIKE 'zz_test_%'"))


def test_gateway_upstream_add_get_list_remove():
    _cleanup_leader()
    res = gateway_tools.add_data_mcp(name="zz_test_up", command="echo", description="d")
    assert res["status"] == "upserted", res
    assert res["upstream"]["name"] == "zz_test_up"
    assert res["upstream"]["transport"] == "stdio"

    got = gateway_tools.get_data_mcp("zz_test_up")
    assert got["name"] == "zz_test_up"
    assert "error" in gateway_tools.get_data_mcp("does-not-exist")

    listed = gateway_tools.list_data_mcps()
    assert "zz_test_up" in [u["name"] for u in listed["upstreams"]]
    assert listed["count"] >= 1

    dele = gateway_tools.remove_data_mcp("zz_test_up")
    assert dele["status"] == "deleted"
    # Second remove is not_found (idempotent-ish).
    assert gateway_tools.remove_data_mcp("zz_test_up")["status"] == "not_found"
    assert "error" in gateway_tools.get_data_mcp("zz_test_up")
    _cleanup_leader()


def test_specialist_agent_create_list_update_delete_and_dangling():
    _cleanup_leader()
    gateway_tools.add_data_mcp(name="zz_test_up2", command="echo")

    agent = workflow_tools.create_specialist_agent(
        name="zz_test_agent", upstream="zz_test_up2", role="r", goal="g"
    )
    assert not agent.get("error"), agent
    assert agent["name"] == "zz_test_agent"
    assert agent["upstream"] == "zz_test_up2"
    assert agent["upstream_missing"] is False

    # Upstream must exist; a bad upstream is rejected.
    bad = workflow_tools.create_specialist_agent(
        name="zz_test_agent_bad", upstream="no_such_upstream", role="r", goal="g"
    )
    assert "error" in bad and "upstream" in bad["error"], bad
    # Duplicate name is rejected.
    assert "error" in workflow_tools.create_specialist_agent(
        name="zz_test_agent", upstream="zz_test_up2", role="r", goal="g"
    )

    listed = workflow_tools.list_specialist_agents()
    assert "zz_test_agent" in [a["name"] for a in listed["agents"]]
    assert next(a for a in listed["agents"] if a["name"] == "zz_test_agent")[
        "upstream_missing"
    ] is False

    upd = workflow_tools.update_specialist_agent(name="zz_test_agent", goal="g2")
    assert upd["goal"] == "g2"

    # Dangling: remove the upstream; the agent remains but is flagged.
    gateway_tools.remove_data_mcp("zz_test_up2")
    listed2 = workflow_tools.list_specialist_agents()
    a2 = next(a for a in listed2["agents"] if a["name"] == "zz_test_agent")
    assert a2["upstream_missing"] is True

    dele = workflow_tools.delete_specialist_agent("zz_test_agent")
    assert dele.get("deleted") == "zz_test_agent"
    assert "error" in workflow_tools.delete_specialist_agent("zz_test_agent")
    _cleanup_leader()


def test_workflow_create_add_step_get():
    _cleanup_leader()
    gateway_tools.add_data_mcp(name="zz_test_up3", command="echo")
    workflow_tools.create_specialist_agent(
        name="zz_test_agent3", upstream="zz_test_up3", role="r", goal="g"
    )

    wf = workflow_tools.create_workflow(name="zz_test_wf", description="d")
    assert not wf.get("error"), wf
    assert wf["name"] == "zz_test_wf"
    # Duplicate workflow name is rejected.
    assert "error" in workflow_tools.create_workflow(name="zz_test_wf")

    step = workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", agent="zz_test_agent3", request="get price"
    )
    assert not step.get("error"), step
    assert step["agent"] == "zz_test_agent3"
    assert step["sort_order"] == 1

    # Second step auto-advances sort_order.
    step2 = workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", agent="zz_test_agent3", request="get volume"
    )
    assert step2["sort_order"] == 2

    # Bad agent / bad workflow are rejected.
    assert "error" in workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", agent="no_such_agent", request="x"
    )
    assert "error" in workflow_tools.add_workflow_step(
        workflow_name="no_such_wf", agent="zz_test_agent3", request="x"
    )

    got = workflow_tools.get_workflow("zz_test_wf")
    assert got["name"] == "zz_test_wf"
    assert len(got["steps"]) == 2
    assert [s["sort_order"] for s in got["steps"]] == [1, 2]
    assert "error" in workflow_tools.get_workflow("no_such_wf")

    # delete_specialist_agent refuses while a step references it (soft-ref guard).
    refused = workflow_tools.delete_specialist_agent("zz_test_agent3")
    assert "error" in refused and "referenced" in refused["error"], refused
    _cleanup_leader()
