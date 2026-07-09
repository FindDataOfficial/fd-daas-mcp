"""Gateway tools for leader-mcp — route live data requests to the project's
data-fetch MCPs via fastmcp.Client.

Two layers:

1. Async cores (`_list_tools_core`, `_call_tool_core`) — open a per-call
   fastmcp.Client over a stdio transport built from a `leader_upstreams`
   row, do the call, tear down. Shared by the FastMCP tools and the
   sync wrappers used by the CrewAI DataCrew.

2. FastMCP tools — `list_data_mcps`, `list_data_mcp_tools`, `call_data_mcp`,
   `ask_data_crew`, plus management CRUD (`add_data_mcp`, `remove_data_mcp`,
   `get_data_mcp`). Registered in server.py.

The data-fetch MCPs are launched on demand as stdio subprocesses; their
launch config lives in `leader_upstreams` (seeded from `.mcp.json`), so they
can be removed from `.mcp.json` itself.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from gateway_database import build_client, get_gateway_db


# ═══════════════════════════════════════════════════════════════
# serialization helper
# ═══════════════════════════════════════════════════════════════


def _ensure_jsonable(value: Any) -> Any:
    """Best-effort coerce an upstream tool result into JSON-serializable form.

    Upstream MCPs return varied types (dicts, pydantic models, DataFrames,
    strings). Prefer the structured `.data` field when present; this helper
    handles the common non-JSON-native types so the gateway always returns
    clean JSON.
    """
    if value is None:
        return None
    # passthrough native JSON types
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dict, list)):
        return value
    # pydantic v2
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:  # noqa: BLE001
            pass
    # pydantic v1
    if hasattr(value, "dict") and callable(getattr(value, "dict", None)):
        try:
            return value.dict()
        except Exception:  # noqa: BLE001
            pass
    # pandas DataFrame / Series
    try:
        import pandas as pd  # type: ignore
        if isinstance(value, pd.DataFrame):
            return {
                "type": "dataframe",
                "shape": list(value.shape),
                "columns": list(value.columns),
                "data": value.where(value.notna(), None).to_dict(orient="records"),
            }
        if isinstance(value, pd.Series):
            return {
                "type": "series",
                "length": len(value),
                "data": value.where(value.notna(), None).to_dict(),
            }
    except ImportError:
        pass
    # fallback: stringify
    return str(value)


def _extract_result_data(result: Any) -> Any:
    """Pull a JSON-serializable payload out of a fastmcp CallToolResult."""
    # Structured output (preferred)
    data = getattr(result, "data", None)
    if data is not None:
        return _ensure_jsonable(data)
    # Text content fallback
    content = getattr(result, "content", None) or []
    texts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is not None:
            texts.append(text)
    if not texts:
        return None
    return texts[0] if len(texts) == 1 else texts


# ═══════════════════════════════════════════════════════════════
# async cores — shared by FastMCP tools and sync CrewAI wrappers
# ═══════════════════════════════════════════════════════════════


async def _list_tools_core(server: str) -> dict:
    db = get_gateway_db()
    row = db.get_upstream(server)
    if row is None:
        return {"error": f"upstream '{server}' not found"}
    if not row["enabled"]:
        return {"error": f"upstream '{server}' is disabled"}
    try:
        async with build_client(row) as client:
            tools = await client.list_tools()
    except Exception as exc:  # noqa: BLE001 — surface any spawn/transport error
        return {"error": f"failed to list tools on '{server}': {type(exc).__name__}: {exc}"}
    items = []
    for t in tools:
        item = {"name": getattr(t, "name", None), "description": getattr(t, "description", "") or ""}
        params = getattr(t, "parameters", None)
        if params:
            item["parameters"] = params
        items.append(item)
    return {"server": server, "count": len(items), "tools": items}


async def _call_tool_core(server: str, tool: str, arguments: dict) -> dict:
    db = get_gateway_db()
    row = db.get_upstream(server)
    if row is None:
        return {"error": f"upstream '{server}' not found"}
    if not row["enabled"]:
        return {"error": f"upstream '{server}' is disabled"}
    try:
        async with build_client(row) as client:
            result = await client.call_tool(tool, arguments)
    except Exception as exc:  # noqa: BLE001 — surface any call/transport error
        return {"error": f"call '{server}.{tool}' failed: {type(exc).__name__}: {exc}"}
    # fastmcp marks tool-level errors on the result
    if getattr(result, "is_error", False):
        return {"error": f"upstream '{server}' tool '{tool}' returned an error", "result": _extract_result_data(result)}
    return {"server": server, "tool": tool, "result": _extract_result_data(result)}


# ═══════════════════════════════════════════════════════════════
# FastMCP tools — gateway
# ═══════════════════════════════════════════════════════════════


def list_data_mcps(include_disabled: bool = False) -> dict:
    """List the data-fetch MCP upstreams leader-mcp can route to.

    Each entry is a row from the `leader_upstreams` table (name, transport,
    enabled, description). Disabled upstreams are hidden unless
    `include_disabled=True`.

    Args:
        include_disabled: If True, also return disabled upstreams.
    """
    rows = get_gateway_db().list_upstreams(include_disabled=include_disabled)
    return {
        "count": len(rows),
        "upstreams": [
            {
                "name": r["name"],
                "transport": r["transport"],
                "enabled": r["enabled"],
                "description": r["description"],
            }
            for r in rows
        ],
    }


async def list_data_mcp_tools(server: str) -> dict:
    """List the tools exposed by a data-fetch MCP upstream (live).

    Connects to the named upstream via a fastmcp.Client over stdio, calls
    `list_tools()`, and returns each tool's name + description (+
    parameters when available). The subprocess is torn down after the call.

    Args:
        server: The upstream name (e.g. 'yfinance').
    """
    return await _list_tools_core(server)


async def call_data_mcp(server: str, tool: str, arguments: str = "{}") -> dict:
    """Call a tool on a data-fetch MCP upstream and return its result.

    Connects to the named upstream via a fastmcp.Client over stdio, invokes
    the named tool with the JSON-deserialized `arguments`, and returns the
    upstream's result. The subprocess is torn down after the call (success
    or error).

    Args:
        server: The upstream name (e.g. 'yfinance').
        tool: The tool name on that upstream (e.g. 'ticker_history').
        arguments: JSON object string of argument name→value pairs.
                   Example: '{"symbol": "AAPL", "period": "1mo"}'
    """
    try:
        args_dict = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid arguments JSON: {exc}"}
    if not isinstance(args_dict, dict):
        return {"error": f"arguments must decode to a JSON object, got {type(args_dict).__name__}"}
    return await _call_tool_core(server, tool, args_dict)


def ask_data_crew(question: str) -> dict:
    """Ask the CrewAI DataCrew to fetch data from the data-fetch MCPs.

    Routes a natural-language data request to the right upstream tool using
    a CrewAI crew (Manager + DataFetcher). When CrewAI is unavailable, falls
    back to a deterministic direct router. Both paths terminate in
    `call_data_mcp` and return the upstream's raw result.

    Args:
        question: Natural-language data request, e.g.
                  'get AAPL 1-month price history'.
    """
    from data_crew import DataCrew  # lazy import to avoid hard crewai dep at module load
    return DataCrew().ask(question, verbose=False)


# ═══════════════════════════════════════════════════════════════
# FastMCP tools — management (CRUD over leader_upstreams)
# ═══════════════════════════════════════════════════════════════


def add_data_mcp(
    name: str,
    transport: str = "stdio",
    command: Optional[str] = None,
    args: Optional[list] = None,
    env: Optional[dict] = None,
    cwd: Optional[str] = None,
    enabled: bool = True,
    description: Optional[str] = None,
) -> dict:
    """Add or update a data-fetch MCP upstream (idempotent upsert by name).

    Args:
        name: Unique upstream name (used as the `server` argument by gateway tools).
        transport: 'stdio' (default) or 'http'.
        command: stdio executable (e.g. 'uv' or a fastmcp binary).
        args: stdio argv list (e.g. ['run','--directory','...','python','server.py']).
        env: optional stdio env overrides (merged with the current env).
        cwd: stdio working directory.
        enabled: If False, the upstream is stored but hidden from gateway tools.
        description: Optional human-readable description.
    """
    row = get_gateway_db().upsert_upstream(
        name=name,
        transport=transport,
        command=command,
        args=args,
        env=env,
        cwd=cwd,
        enabled=enabled,
        description=description,
    )
    return {"status": "upserted", "upstream": row}


def remove_data_mcp(name: str) -> dict:
    """Remove a data-fetch MCP upstream from the registry.

    Args:
        name: The upstream name to delete.
    """
    deleted = get_gateway_db().delete_upstream(name)
    return {"status": "deleted" if deleted else "not_found", "name": name}


def get_data_mcp(name: str) -> dict:
    """Get one data-fetch MCP upstream's full launch config.

    Args:
        name: The upstream name.
    """
    row = get_gateway_db().get_upstream(name)
    if row is None:
        return {"error": f"upstream '{name}' not found"}
    return row


# ═══════════════════════════════════════════════════════════════
# Generic aliases — category-agnostic names over the same implementation.
# `leader-mcp` is the single client-facing entry point; these tools route
# to ANY upstream in leader_upstreams (data-fetch or otherwise). The
# `*_data_mcp` tools above remain as back-compat aliases.
# ═══════════════════════════════════════════════════════════════


def list_mcps(include_disabled: bool = False) -> dict:
    """List all MCP upstreams leader-mcp can route to (generic alias for list_data_mcps).

    Args:
        include_disabled: If True, also return disabled upstreams.
    """
    return list_data_mcps(include_disabled=include_disabled)


async def list_mcp_tools(server: str) -> dict:
    """List the tools exposed by an MCP upstream (generic alias for list_data_mcp_tools).

    Args:
        server: The upstream name (e.g. 'yfinance' or 'cron-mcp').
    """
    return await list_data_mcp_tools(server)


async def call_mcp(server: str, tool: str, arguments: str = "{}") -> dict:
    """Call a tool on an MCP upstream and return its result (generic alias for call_data_mcp).

    Args:
        server: The upstream name (e.g. 'yfinance' or 'cron-mcp').
        tool: The tool name on that upstream.
        arguments: JSON object string of argument name→value pairs.
    """
    return await call_data_mcp(server, tool, arguments)


def add_mcp(
    name: str,
    transport: str = "stdio",
    command: Optional[str] = None,
    args: Optional[list] = None,
    env: Optional[dict] = None,
    cwd: Optional[str] = None,
    enabled: bool = True,
    description: Optional[str] = None,
) -> dict:
    """Add or update an MCP upstream (generic alias for add_data_mcp).

    Args:
        name: Unique upstream name (used as the `server` argument by gateway tools).
        transport: 'stdio' (default) or 'http'.
        command: stdio executable (e.g. 'uv' or a fastmcp binary).
        args: stdio argv list.
        env: optional stdio env overrides (merged with the current env).
        cwd: stdio working directory.
        enabled: If False, the upstream is stored but hidden from gateway tools.
        description: Optional human-readable description.
    """
    return add_data_mcp(
        name=name,
        transport=transport,
        command=command,
        args=args,
        env=env,
        cwd=cwd,
        enabled=enabled,
        description=description,
    )


def remove_mcp(name: str) -> dict:
    """Remove an MCP upstream from the registry (generic alias for remove_data_mcp).

    Args:
        name: The upstream name to delete.
    """
    return remove_data_mcp(name)


def get_mcp(name: str) -> dict:
    """Get one MCP upstream's full launch config (generic alias for get_data_mcp).

    Args:
        name: The upstream name.
    """
    return get_data_mcp(name)


# ═══════════════════════════════════════════════════════════════
# sync wrappers — for the CrewAI DataCrew (which runs sync tools)
# ═══════════════════════════════════════════════════════════════


def list_data_mcp_tools_sync(server: str) -> dict:
    """Sync wrapper around `list_data_mcp_tools` for CrewAI tools.

    Runs the async core in a fresh event loop. Safe to call from a sync
    CrewAI tool because CrewAI executes tools in a worker thread with no
    running loop.
    """
    return asyncio.run(_list_tools_core(server))


def call_data_mcp_sync(server: str, tool: str, arguments: str = "{}") -> dict:
    """Sync wrapper around `call_data_mcp` for CrewAI tools."""
    try:
        args_dict = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid arguments JSON: {exc}"}
    if not isinstance(args_dict, dict):
        return {"error": f"arguments must decode to a JSON object, got {type(args_dict).__name__}"}
    return asyncio.run(_call_tool_core(server, tool, args_dict))
