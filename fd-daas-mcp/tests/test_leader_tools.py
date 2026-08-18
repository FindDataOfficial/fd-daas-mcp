"""leader_tools tests: gateway upstream CRUD and workflow create/add-step/get
under the fd-open-data-mcp data-fetch model.

Calls the leader tool handlers directly (gateway_tools + workflow_tools). The
LLM crew path and live upstream subprocess calls (`gateway_database.build_client`)
are never invoked - only the SQLite-backed management CRUD. No LLM call, no
network, no subprocess.

Key coupling mirrored in the tests: `add_workflow_step` now takes `tool` +
`arguments` (a `fd-open-data-mcp` tool call) instead of `agent` + `request`;
the `agent` column is a `fd-open-data-mcp` sentinel. There is no specialist-
agent layer (removed when the 11 per-source data-fetch MCPs were replaced by
the single `fd-open-data-mcp` upstream).

Convention: upstreams/workflows this module creates are prefixed `zz_test_`
and torn down by `_cleanup_leader()` in every test.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text

_LEADER_MCP = Path(__file__).resolve().parents[1] / "leader-mcp"
sys.path.insert(0, str(_LEADER_MCP))
from workflow_database import get_workflow_db  # noqa: E402
from gateway_database import get_gateway_db  # noqa: E402
import gateway_tools  # noqa: E402
import gateway_client_pool.client_pool as _client_pool_mod  # noqa: E402
from gateway_client_pool.client_pool import ClientPool  # noqa: E402
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
        conn.execute(text("DELETE FROM workflows WHERE name LIKE 'zz_test_%'"))
        conn.execute(text("DELETE FROM gateway_upstreams WHERE name LIKE 'zz_test_%'"))


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


def test_workflow_create_add_step_get():
    _cleanup_leader()
    wf = workflow_tools.create_workflow(name="zz_test_wf", description="d")
    assert not wf.get("error"), wf
    assert wf["name"] == "zz_test_wf"
    # Duplicate workflow name is rejected.
    assert "error" in workflow_tools.create_workflow(name="zz_test_wf")

    step = workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", tool="list_concepts",
        arguments='{"entity_type": "stock"}',
    )
    assert not step.get("error"), step
    assert step["tool"] == "list_concepts"
    assert step["agent"] == "fd-open-data-mcp"  # sentinel
    assert step["arguments"] == {"entity_type": "stock"}
    assert step["sort_order"] == 1

    # Second step auto-advances sort_order.
    step2 = workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", tool="read",
        arguments='{"concept_id": 1, "entity_type": "stock", "entity_id": 10, "dates": ["2026-01-01"]}',
        depends_on="1",
    )
    assert step2["sort_order"] == 2
    assert step2["depends_on"] == ["1"]

    # Empty tool / bad workflow / invalid JSON arguments are rejected.
    assert "error" in workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", tool="", arguments="{}"
    )
    assert "error" in workflow_tools.add_workflow_step(
        workflow_name="no_such_wf", tool="read", arguments="{}"
    )
    assert "error" in workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", tool="read", arguments="{not json}"
    )
    # Non-object JSON arguments are rejected.
    assert "error" in workflow_tools.add_workflow_step(
        workflow_name="zz_test_wf", tool="read", arguments="[1, 2, 3]"
    )

    got = workflow_tools.get_workflow("zz_test_wf")
    assert got["name"] == "zz_test_wf"
    assert len(got["steps"]) == 2
    assert [s["sort_order"] for s in got["steps"]] == [1, 2]
    assert [s["tool"] for s in got["steps"]] == ["list_concepts", "read"]
    assert "error" in workflow_tools.get_workflow("no_such_wf")
    _cleanup_leader()


# ═══════════════════════════════════════════════════════════════
# Task 1.8 — gateway health probe + client-pool fallback (mocked)
# ═══════════════════════════════════════════════════════════════
# These tests mock `_ping_http` (no network) and the client-pool's
# `_build_client_from_row` (no subprocess / live server), verifying
# all five transport-flip branches in `gateway_health()` plus the
# http→stdio fallback path in `ClientPool.get_client()`. No network,
# no subprocess, no live fd-open-data-mcp server dependency.
from unittest.mock import patch  # noqa: E402

from gateway_database import get_gateway_db  # noqa: E402


def _seed_upstream(name, transport, url=None, command=None, enabled=True):
    """Seed a zz_test_ gateway_upstreams row in the throwaway test DB."""
    db = get_gateway_db()
    return db.upsert_upstream(
        name=name, transport=transport, url=url, command=command,
        args=[], enabled=enabled, description="zz_test",
    )


# ── fake HTTP reachability for `gateway_health` ───────────────────

async def _ping_ok(url, timeout=5.0):
    return True, f"OK ({url})"

async def _ping_fail(url, timeout=5.0):
    return False, "ConnectionError: simulated unreachable"


def test_gateway_health_http_healthy():
    """http + ping succeeds → healthy, transport unchanged."""
    _cleanup_leader()
    _seed_upstream("zz_test_http", "http", url="http://127.0.0.1:8300", command="/bin/true")
    with patch.object(gateway_tools, "_ping_http", _ping_ok):
        result = asyncio.run(gateway_tools.gateway_health())
    ups = {u["name"]: u for u in result["upstreams"]}
    u = ups["zz_test_http"]
    assert u["action"] == "healthy"
    assert u["transport_after"] == "http"
    assert u["reachable"] is True
    assert get_gateway_db().get_upstream("zz_test_http")["transport"] == "http"
    _cleanup_leader()


def test_gateway_health_http_down_flips_to_stdio():
    """http + ping fails + stdio command present → flip to stdio."""
    _cleanup_leader()
    _seed_upstream("zz_test_http_down", "http", url="http://127.0.0.1:59999", command="/bin/true")
    with patch.object(gateway_tools, "_ping_http", _ping_fail):
        result = asyncio.run(gateway_tools.gateway_health())
    ups = {u["name"]: u for u in result["upstreams"]}
    u = ups["zz_test_http_down"]
    assert u["action"] == "flipped-to-stdio (http unreachable, stdio fallback armed)"
    assert u["transport_after"] == "stdio"
    assert u["reachable"] is False
    assert get_gateway_db().get_upstream("zz_test_http_down")["transport"] == "stdio"
    _cleanup_leader()


def test_gateway_health_http_down_no_command_degraded():
    """http + ping fails + no stdio command → degraded, no flip."""
    _cleanup_leader()
    _seed_upstream("zz_test_http_nocmd", "http", url="http://127.0.0.1:59999", command=None)
    with patch.object(gateway_tools, "_ping_http", _ping_fail):
        result = asyncio.run(gateway_tools.gateway_health())
    ups = {u["name"]: u for u in result["upstreams"]}
    u = ups["zz_test_http_nocmd"]
    assert u["action"] == "degraded (http down, no stdio fallback)"
    assert u["transport_after"] == "http"
    assert u["reachable"] is False
    assert get_gateway_db().get_upstream("zz_test_http_nocmd")["transport"] == "http"
    _cleanup_leader()


def test_gateway_health_stdio_with_url_recovers_to_http():
    """stdio (with url set) + ping succeeds → flip back to http."""
    _cleanup_leader()
    _seed_upstream("zz_test_stdio_url", "stdio", url="http://127.0.0.1:8300", command="/bin/true")
    with patch.object(gateway_tools, "_ping_http", _ping_ok):
        result = asyncio.run(gateway_tools.gateway_health())
    ups = {u["name"]: u for u in result["upstreams"]}
    u = ups["zz_test_stdio_url"]
    assert u["action"] == "flipped-to-http (endpoint recovered)"
    assert u["transport_after"] == "http"
    assert u["reachable"] is True
    assert get_gateway_db().get_upstream("zz_test_stdio_url")["transport"] == "http"
    _cleanup_leader()


def test_gateway_health_stdio_with_url_still_down():
    """stdio (with url set) + ping fails → stays stdio (degraded)."""
    _cleanup_leader()
    _seed_upstream("zz_test_stdio_down", "stdio", url="http://127.0.0.1:59999", command="/bin/true")
    with patch.object(gateway_tools, "_ping_http", _ping_fail):
        result = asyncio.run(gateway_tools.gateway_health())
    ups = {u["name"]: u for u in result["upstreams"]}
    u = ups["zz_test_stdio_down"]
    assert u["action"] == "degraded (stdio mode, http still down)"
    assert u["transport_after"] == "stdio"
    assert u["reachable"] is False
    assert get_gateway_db().get_upstream("zz_test_stdio_down")["transport"] == "stdio"
    _cleanup_leader()


def test_gateway_health_stdio_only_skipped():
    """stdio-only (no url) → skipped, nothing probed."""
    _cleanup_leader()
    _seed_upstream("zz_test_stdio_only", "stdio", url=None, command="/bin/true")
    with patch.object(gateway_tools, "_ping_http", _ping_fail):
        result = asyncio.run(gateway_tools.gateway_health())
    ups = {u["name"]: u for u in result["upstreams"]}
    u = ups["zz_test_stdio_only"]
    assert u["action"] == "skipped (stdio-only upstream, no url to probe)"
    assert u["transport_after"] == "stdio"
    assert u["reachable"] is None
    assert get_gateway_db().get_upstream("zz_test_stdio_only")["transport"] == "stdio"
    _cleanup_leader()


# ── client-pool http→stdio fallback (mocked _build_client_from_row) ──

class _FakeClient:
    """Stand-in for fastmcp.Client — __aenter__ fails the first N times,
    then succeeds. Used so the pool fallback path is exercised without a
    live HTTP endpoint or a spawned subprocess."""
    def __init__(self, enter_failures: int = 0):
        self._enter_failures = enter_failures
        self._entered = 0

    async def __aenter__(self):
        self._entered += 1
        if self._entered <= self._enter_failures:
            raise ConnectionError(f"simulated transport failure #{self._entered}")
        return self

    async def __aexit__(self, *exc):
        return False


def test_client_pool_http_to_stdio_fallback():
    """http __aenter__ fails + stdio command present → pool flips the row
    to stdio, rebuilds, and retries; the stdio client succeeds."""
    _cleanup_leader()
    _seed_upstream(
        "zz_test_pool", "http",
        url="http://127.0.0.1:59999",   # unreachable
        command="/bin/true",            # stdio fallback armed
    )
    built: list[str] = []

    def _fake_build(row):
        built.append(row.get("transport"))
        if row.get("transport") == "http":
            return _FakeClient(enter_failures=1)   # http fails to enter
        return _FakeClient(enter_failures=0)       # stdio (after flip) succeeds

    pool = ClientPool()  # fresh instance — no singleton state to reset
    with patch.object(_client_pool_mod, "_build_client_from_row", _fake_build):
        client = asyncio.run(pool.get_client("zz_test_pool"))

    # http build failed → flipped to stdio → rebuilt stdio → succeeded
    assert built == ["http", "stdio"], built
    assert isinstance(client, _FakeClient)
    assert get_gateway_db().get_upstream("zz_test_pool")["transport"] == "stdio"
    _cleanup_leader()


def test_client_pool_http_fail_no_command_raises():
    """http __aenter__ fails + no stdio command → pool re-raises (no
    fallback available). Row transport is NOT flipped."""
    _cleanup_leader()
    _seed_upstream(
        "zz_test_pool_nocmd", "http",
        url="http://127.0.0.1:59999",
        command=None,   # NO stdio fallback
    )

    def _fake_build(row):
        return _FakeClient(enter_failures=1)   # always fails to enter

    pool = ClientPool()
    raised = False
    with patch.object(_client_pool_mod, "_build_client_from_row", _fake_build):
        try:
            asyncio.run(pool.get_client("zz_test_pool_nocmd"))
        except ConnectionError:
            raised = True

    assert raised, "expected ConnectionError when http fails and no stdio fallback"
    assert get_gateway_db().get_upstream("zz_test_pool_nocmd")["transport"] == "http"
    _cleanup_leader()
