"""
MCP Server for DAAS — multi-source data access.

Exposes tools that Claude Code can invoke directly:
  list_sources       — list all data sources
  search_functions   — search the DAAS registry
  get_function_detail — get function details (params, columns, description)
  list_categories    — list all categories with counts
  fetch_data         — execute a data function and return results as JSON
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from fastmcp import FastMCP

app = FastMCP(name="daas-mcp")

# Ensure the harness package is importable
_HARNESS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daas-agent-harness")
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)

# Register tools
from daas_tools import (
    list_sources,
    search_functions,
    get_function_detail,
    list_categories,
    fetch_data,
)

app.tool(list_sources)
app.tool(search_functions)
app.tool(get_function_detail)
app.tool(list_categories)
app.tool(fetch_data)

if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
