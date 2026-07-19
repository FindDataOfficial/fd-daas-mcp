"""
MCP Server for composite-mcp — curate a composite MCP from selected tools
across multiple upstream MCP servers, plus chained tools.

Serves ONE composite selected by the COMPOSITE env var. Management tools
are always present so any composite can be curated at runtime; selection
changes apply on next process start.

Entry: python3 server.py  (FastMCP, stdio transport)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import FastMCP

from composite_database import get_composite_db
from composite_tools import (
    add_chained_tool,
    add_tool,
    add_upstream,
    create,
    list,  # noqa: A004 (intentional: registers as composite_list)
    list_available_tools,
    list_chained_tools,
    list_tools,
    list_upstreams,
    make_chain_tool,
    make_proxy_tool,
    remove_chained_tool,
    remove_tool,
    remove_upstream,
)
from ui_tools import register as register_ui_tools

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

logger = logging.getLogger("composite-mcp")

app = FastMCP(name="composite-mcp")

# ── management tools (always present) ─────────────────────────
app.add_tool(list)
app.add_tool(create)
app.add_tool(list_upstreams)
app.add_tool(add_upstream)
app.add_tool(remove_upstream)
app.add_tool(list_available_tools)
app.add_tool(add_tool)
app.add_tool(remove_tool)
app.add_tool(list_tools)
app.add_tool(add_chained_tool)
app.add_tool(remove_chained_tool)
app.add_tool(list_chained_tools)

# ── demo MCP-Apps UI tools (always present) ──────────────────
# render_stock_summary + the ui:// resource template it links to. Lets the
# dashboard /chat page render a tool-returned UI via @mcp-ui/client AppRenderer.
register_ui_tools(app)


def build_served_tools(app: FastMCP, composite_name: str | None = None) -> None:
    """Register lazy proxied tools + chained tools for a composite.

    composite_name defaults to the COMPOSITE env var. No-op (management-only)
    if unset or the composite doesn't exist.

    Proxied tools are registered as lazy `FunctionTool` stubs (see
    `make_proxy_tool`): the upstream is spawned ONLY when the stub is called,
    never at list time. This avoids a nested stdio spawn when leader-mcp lists
    composite-mcp's tools — the previous `create_proxy` + `app.mount` approach
    eagerly spawned the upstream at list time and failed with "Connection
    closed" inside the leader-mcp server context.
    """
    if composite_name is None:
        composite_name = os.environ.get("COMPOSITE")
    if not composite_name:
        logger.info("No COMPOSITE env set; serving management tools only.")
        return

    spec = get_composite_db().load_composite(composite_name)
    if spec is None:
        logger.warning("Composite %r not found; serving management tools only.", composite_name)
        return

    upstreams_by_key = {u["key"]: u for u in spec["upstreams"]}

    # register each selected proxied tool as a lazy stub. Listing these stubs
    # is DB-driven (name + description); the upstream is spawned on call only.
    for t in spec["tools"]:
        upstream = upstreams_by_key.get(t["upstream_key"])
        if upstream is None:
            logger.warning("tool selection references unknown upstream %r; skipping", t["upstream_key"])
            continue
        app.add_tool(make_proxy_tool(t["upstream_key"], t["tool_name"], upstream))
        logger.info(
            "registered proxied tool %r (%s.%s)",
            f"{t['upstream_key']}_{t['tool_name']}", t["upstream_key"], t["tool_name"],
        )

    for c in spec["chains"]:
        tool = make_chain_tool(c["name"], c["steps"], upstreams_by_key, c["description"])
        app.add_tool(tool)
        logger.info("registered chain %r (%d steps)", c["name"], len(c["steps"]))


build_served_tools(app)


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
