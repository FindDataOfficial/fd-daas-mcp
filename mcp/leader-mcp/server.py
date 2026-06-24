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

from fastmcp import FastMCP

from leader_tools import (
    list_harnesses,
    search_functions,
    get_function_detail,
    list_categories,
    find_functions_by_column,
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

if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
