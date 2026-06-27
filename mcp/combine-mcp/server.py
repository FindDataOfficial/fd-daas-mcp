"""
MCP Server for combine-mcp — curate a composite MCP from selected tools
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
from typing import Sequence

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server import create_proxy
from fastmcp.server.transforms import Transform

from combine_database import build_transport, get_combine_db
from combine_tools import (
    add_chained_tool,
    add_tool,
    add_upstream,
    create_composite,
    list_available_tools,
    list_chained_tools,
    list_composite_tools,
    list_composites,
    list_upstreams,
    make_chain_tool,
    remove_chained_tool,
    remove_tool,
    remove_upstream,
)

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

logger = logging.getLogger("combine-mcp")

app = FastMCP(name="combine-mcp")

# ── management tools (always present) ─────────────────────────
app.add_tool(list_composites)
app.add_tool(create_composite)
app.add_tool(list_upstreams)
app.add_tool(add_upstream)
app.add_tool(remove_upstream)
app.add_tool(list_available_tools)
app.add_tool(add_tool)
app.add_tool(remove_tool)
app.add_tool(list_composite_tools)
app.add_tool(add_chained_tool)
app.add_tool(remove_chained_tool)
app.add_tool(list_chained_tools)


class FilterTools(Transform):
    """Lazy name-based filter: keep only tools in `keep`.

    Avoids enumerating the upstream at startup (no spawn, no asyncio.run).
    Nonexistent selected tools simply never appear.
    # ponytail: lazy filter; no startup enumeration.
    """

    def __init__(self, keep: set[str]):
        self.keep = keep

    async def list_tools(self, tools: Sequence) -> Sequence:
        return [t for t in tools if t.name in self.keep]

    async def get_tool(self, name, call_next, *, version=None):
        if name not in self.keep:
            return None
        return await call_next(name)


def build_served_tools(app: FastMCP, composite_name: str | None = None) -> None:
    """Mount filtered proxies + register chained tools for a composite.

    composite_name defaults to the COMPOSITE env var. No-op (management-only)
    if unset or the composite doesn't exist.
    """
    if composite_name is None:
        composite_name = os.environ.get("COMPOSITE")
    if not composite_name:
        logger.info("No COMPOSITE env set; serving management tools only.")
        return

    spec = get_combine_db().load_composite(composite_name)
    if spec is None:
        logger.warning("Composite %r not found; serving management tools only.", composite_name)
        return

    upstreams_by_key = {u["key"]: u for u in spec["upstreams"]}

    # group selected tools by upstream key
    selected_by_upstream: dict[str, set[str]] = {}
    for t in spec["tools"]:
        selected_by_upstream.setdefault(t["upstream_key"], set()).add(t["tool_name"])

    for key, selected in selected_by_upstream.items():
        upstream = upstreams_by_key.get(key)
        if upstream is None:
            logger.warning("tool selection references unknown upstream %r; skipping", key)
            continue
        proxy = create_proxy(build_transport(upstream), name=f"{composite_name}-{key}-proxy")
        proxy.add_transform(FilterTools(selected))
        app.mount(proxy, namespace=key)
        logger.info("mounted upstream %r (%d selected tools)", key, len(selected))

    for c in spec["chains"]:
        tool = make_chain_tool(c["name"], c["steps"], upstreams_by_key, c["description"])
        app.add_tool(tool)
        logger.info("registered chain %r (%d steps)", c["name"], len(c["steps"]))


build_served_tools(app)


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
