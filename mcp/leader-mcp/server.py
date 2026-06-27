"""
MCP Server for the Leader multi-harness registry.

Exposes the database query tools (list_harnesses, search_functions,
get_function_detail, list_categories, find_functions_by_column) as MCP
tools that Claude Code can invoke directly.

Usage:
    python server.py                         # stdio transport (default for Claude Code)
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from fastmcp import FastMCP

from leader_tools import (
    list_harnesses,
    search_functions,
    get_function_detail,
    list_categories,
    find_functions_by_column,
    list_datasources,
    toggle_datasource,
    save_snapshot,
    list_snapshots,
    query_snapshots,
    get_column_provenance,
    update_column_meta,
)

app = FastMCP(
    name="leader-mcp",
)

# Register each tool function directly — FastMCP infers parameter schemas
# from type annotations and docstrings.
app.add_tool(list_harnesses)
app.add_tool(search_functions)
app.add_tool(get_function_detail)
app.add_tool(list_categories)
app.add_tool(find_functions_by_column)
app.add_tool(list_datasources)
app.add_tool(toggle_datasource)
app.add_tool(save_snapshot)
app.add_tool(list_snapshots)
app.add_tool(query_snapshots)
app.add_tool(get_column_provenance)
app.add_tool(update_column_meta)

if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
