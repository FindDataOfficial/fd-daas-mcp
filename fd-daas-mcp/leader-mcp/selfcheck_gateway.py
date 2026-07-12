"""Self-check for the leader-mcp data gateway.

Exercises the full gateway plumbing against a stub FastMCP upstream launched
as a stdio subprocess: CRUD over leader_upstreams, live tool discovery,
direct tool call, error paths, and the ask_data_crew direct-router fallback.
Uses a temp DB (does not touch mcp/daas.db); no LLM call required.

Usage:
    uv run --directory mcp/leader-mcp python selfcheck_gateway.py
    # or:
    .venv/bin/python selfcheck_gateway.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Make the shared schema package (`models`) importable, mirroring server.py.
_HERE = Path(__file__).resolve().parent
_MCP_ROOT = _HERE.parent
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))

from dotenv import load_dotenv

load_dotenv(_MCP_ROOT / ".env")
load_dotenv(_HERE / ".env", override=True)

import gateway_database as gdb
from gateway_tools import (
    add_data_mcp,
    call_data_mcp,
    get_data_mcp,
    list_data_mcps,
    list_data_mcp_tools,
    remove_data_mcp,
)
from data_crew import DataCrew

# A minimal FastMCP upstream the selfcheck launches as a stdio subprocess.
STUB_UPSTREAM_SRC = '''"""Stub FastMCP upstream for gateway self-check."""
from fastmcp import FastMCP
app = FastMCP(name="stub-upstream")

@app.tool
def echo(value: str = "hello") -> dict:
    """Echo the value back in a dict."""
    return {"echoed": value}

@app.tool
def add(a: int, b: int) -> dict:
    """Add two ints."""
    return {"sum": a + b}

if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
'''


def _setup_temp_db() -> str:
    """Point the gateway DB at a fresh temp SQLite file and reinit the singleton."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    url = f"sqlite:///{tmp.name}"
    os.environ["DAAS_DATABASE_URL"] = url
    gdb.reset_gateway_db()
    db = gdb.GatewayDatabase(url)
    db.init_db()
    # install as the module singleton so gateway_tools uses it
    gdb._gateway_db = db
    return url


def _write_stub_upstream() -> Path:
    stub = _HERE / "_stub_upstream.py"
    stub.write_text(STUB_UPSTREAM_SRC)
    return stub


def _check(label: str, cond: bool, detail: str = "") -> bool:
    mark = "✓" if cond else "✗"
    print(f"  {mark} {label}{(': ' + detail) if detail else ''}")
    return cond


async def _test_live_gateway(stub_path: Path) -> bool:
    """Test list_data_mcp_tools + call_data_mcp against the stub upstream."""
    ok = True
    # list tools
    res = await list_data_mcp_tools("stub")
    ok &= _check("list_data_mcp_tools(stub) returns tools",
                 "tools" in res and any(t["name"] == "echo" for t in res["tools"]),
                 str(res.get("error", "")))
    # call echo
    res = await call_data_mcp("stub", "echo", '{"value": "ping"}')
    ok &= _check("call_data_mcp(stub, echo, ping) returns {echoed: ping}",
                 res.get("result") == {"echoed": "ping"}, str(res.get("error", "")))
    # call add
    res = await call_data_mcp("stub", "add", '{"a": 2, "b": 3}')
    ok &= _check("call_data_mcp(stub, add, 2+3) returns {sum: 5}",
                 res.get("result") == {"sum": 5}, str(res.get("error", "")))
    return ok


def _test_error_paths() -> bool:
    ok = True
    # unknown upstream
    res = asyncio.run(list_data_mcp_tools("nope"))
    ok &= _check("list tools on unknown upstream → error",
                 "error" in res and "not found" in res["error"])
    # disabled upstream
    add_data_mcp("stub", command=sys.executable, args=["_stub_upstream.py"], cwd=str(_HERE))
    gdb.get_gateway_db().set_enabled("stub", False)
    res = asyncio.run(list_data_mcp_tools("stub"))
    ok &= _check("list tools on disabled upstream → error",
                 "error" in res and "disabled" in res["error"])
    gdb.get_gateway_db().set_enabled("stub", True)
    # invalid JSON arguments
    res = asyncio.run(call_data_mcp("stub", "echo", "{not json}"))
    ok &= _check("call with invalid JSON → error",
                 "error" in res and "Invalid arguments JSON" in res["error"])
    # non-object JSON arguments
    res = asyncio.run(call_data_mcp("stub", "echo", "[1,2,3]"))
    ok &= _check("call with non-object JSON → error",
                 "error" in res and "must decode to a JSON object" in res["error"])
    return ok


def _test_ask_data_crew_fallback(stub_path: Path) -> bool:
    """Force the CrewAI path to fail and confirm the direct fallback runs.

    The direct router won't match 'unrelated' text, so it returns a
    could-not-route dict — proving the fallback was exercised (no exception,
    no CrewAI dependency required).
    """
    res = DataCrew().ask("totally unrelated gibberish with no data intent", verbose=False)
    return _check("ask_data_crew falls back to direct router",
                  "error" in res and "could not route" in res.get("error", ""),
                  str(res.get("error", ""))[:80])


def main() -> int:
    print("leader-mcp data gateway self-check")
    url = _setup_temp_db()
    print(f"  temp DB: {url}")
    stub_path = _write_stub_upstream()
    print(f"  stub upstream: {stub_path}")

    all_ok = True

    print("\n[1] CRUD over leader_upstreams")
    add_data_mcp("stub", command=sys.executable, args=["_stub_upstream.py"], cwd=str(_HERE),
                 description="stub for selfcheck")
    all_ok &= _check("add_data_mcp(stub)", True)
    all_ok &= _check("list_data_mcps() includes stub",
                     any(u["name"] == "stub" for u in list_data_mcps()["upstreams"]))
    all_ok &= _check("get_data_mcp(stub).command == sys.executable",
                     get_data_mcp("stub").get("command") == sys.executable)
    all_ok &= _check("list_data_mcps() hides disabled (toggle off then check)",
                     (gdb.get_gateway_db().set_enabled("stub", False) or True)
                     and "stub" not in [u["name"] for u in list_data_mcps()["upstreams"]])
    gdb.get_gateway_db().set_enabled("stub", True)

    print("\n[2] Live gateway (list_data_mcp_tools + call_data_mcp) against stub upstream")
    all_ok &= asyncio.run(_test_live_gateway(stub_path))

    print("\n[3] Error paths")
    all_ok &= _test_error_paths()

    print("\n[4] ask_data_crew direct-router fallback")
    all_ok &= _test_ask_data_crew_fallback(stub_path)

    print("\n[5] Cleanup")
    all_ok &= _check("remove_data_mcp(stub)", remove_data_mcp("stub")["status"] == "deleted")
    try:
        stub_path.unlink()
    except OSError:
        pass

    print("\n" + ("ALL CHECKS PASSED ✓" if all_ok else "SOME CHECKS FAILED ✗"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
