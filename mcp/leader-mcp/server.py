"""
MCP Server for the Leader multi-harness registry + data gateway.

Exposes the database query tools (list_harnesses, search_functions,
get_function_detail, list_categories, find_functions_by_column) as MCP
tools that Claude Code can invoke directly, PLUS the data gateway tools
(list_data_mcps, list_data_mcp_tools, call_data_mcp, ask_data_crew) that
route live data requests to the project's data-fetch MCPs via fastmcp.Client,
PLUS the crewai-data-workflow tools (specialist agents + step-by-step
workflows over those agents, with per-agent LLM control).

Usage:
    python server.py                         # stdio transport (default for Claude Code)
    python server.py --run-workflow <name>   # run a workflow in-process (cron path)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # mcp/ — on sys.path so `import models` works
# parents[2] reaches the repo root from mcp/leader-mcp/server.py (parent.parent
# is mcp/, parent.parent.parent is cli-anything/). The shared .env (LLM_*,
# DAAS_DATABASE_URL) lives at the repo root — matching process-mcp / daas-mcp /
# cnreport-mcp. Required so the crewai-data-workflow specialist-agent LLM path
# sees LLM_* when run as an MCP server.
REPO_ROOT = Path(__file__).resolve().parents[2]  # cli-anything/
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

# Make the shared schema package (`models`) importable. mcp/models/ ships as
# the `mcp-models` package but its editable install maps the import name
# inconsistently across venvs, so we put mcp/ on sys.path explicitly. This
# also matches the project's test convention.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
from gateway_tools import (
    list_data_mcps,
    list_data_mcp_tools,
    call_data_mcp,
    ask_data_crew,
    add_data_mcp,
    remove_data_mcp,
    get_data_mcp,
)
from workflow_tools import (
    list_agent_models,
    create_specialist_agent,
    list_specialist_agents,
    create_workflow,
    add_workflow_step,
    get_workflow,
    list_workflows,
    run_workflow,
    run_workflow_step,
    get_workflow_run,
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

# Data gateway tools — route live data requests to the data-fetch MCPs.
app.add_tool(list_data_mcps)
app.add_tool(list_data_mcp_tools)
app.add_tool(call_data_mcp)
app.add_tool(ask_data_crew)
app.add_tool(add_data_mcp)
app.add_tool(remove_data_mcp)
app.add_tool(get_data_mcp)

# crewai-data-workflow tools — specialist agents + step-by-step workflows.
# (LLM registry + agent registry + workflow definition + execution.)
app.add_tool(list_agent_models)
app.add_tool(create_specialist_agent)
app.add_tool(list_specialist_agents)
app.add_tool(create_workflow)
app.add_tool(add_workflow_step)
app.add_tool(get_workflow)
app.add_tool(list_workflows)
app.add_tool(run_workflow)
app.add_tool(run_workflow_step)
app.add_tool(get_workflow_run)


def _run_workflow_cli(name: str) -> int:
    """Run a workflow in-process (no stdio server), print the JSON run summary,
    and return an exit code. Mirrors `process-mcp --run-rule` / `daas-mcp
    --fetch-item` so a workflow can be scheduled via cron-mcp.

    Relative DAAS_DATABASE_URL is resolved against the repo root by
    workflow_database._resolve_database_url, so this works under
    `uv run --directory mcp/leader-mcp`.
    """
    result = run_workflow(name)
    print(json.dumps(result, default=str, indent=2))
    return 1 if isinstance(result, dict) and "error" in result else 0


if __name__ == "__main__":
    # CLI branches (cron path) — must be checked before starting the stdio server.
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-workflow":
        sys.exit(_run_workflow_cli(sys.argv[2]))
    if len(sys.argv) >= 2 and sys.argv[1] in ("--run-workflow",):
        print(json.dumps({"error": "usage: server.py --run-workflow <name>"}))
        sys.exit(2)
    app.run(transport="stdio", show_banner=False)
