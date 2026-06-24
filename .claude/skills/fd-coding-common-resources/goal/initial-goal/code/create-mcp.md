# MCP Generator — YAML-Driven MCP Server Code Generator

## Description
Build a Python tool that reads a YAML configuration defining MCP server capabilities (tools, resources, prompts) and generates a complete, runnable Python MCP server. The generator mirrors this project's existing YAML-driven pattern — the YAML config is the single source of truth, and the generator produces production-ready FastMCP server code from it.

## Steps

1. **Design the MCP config YAML schema** — Define the YAML structure for declaring tools (name, description, parameters schema), resources (URI patterns, handlers), and prompts (templates, argument types). Create a reference template at `template/config/template.mcp.yaml`.

2. **Implement the config loader** — Build a Python module that loads and validates MCP YAML configs (schema validation, defaults resolution, error reporting). Follow the pattern established in `dashboard/config.py`.

3. **Implement the code generator** — Build the core generator that takes a validated MCP config and produces a runnable `server.py` using the FastMCP framework. The generated code should include: imports, server init, tool/resource/prompt registrations with proper type hints, and a `main()` entry point.

4. **Build the CLI** — Create a `generate-mcp` CLI command (similar to `config-dashboard`) that takes a YAML config path and outputs the server code. Support flags: `--output-dir`, `--dry-run`, `--validate-only`.

5. **Create starter configs and examples** — Provide 2-3 example MCP configs (e.g., a file-system MCP, a weather MCP, a database-query MCP) plus their generated outputs to demonstrate the workflow.

6. **Write tests** — Unit tests for config validation, generator output correctness, and CLI behavior. Use the same pytest + tempfile pattern as the dashboard tests.

7. **Document usage** — Add a README section or a `goal/final-goal/mcp-generator.yaml` documenting the workflow: write YAML → generate → run.

## Success Criteria
- A YAML file like `my-mcp.yaml` defining 3 tools + 1 resource + 1 prompt produces a runnable `server.py`
- Generated server passes `mcp dev` (FastMCP's dev tool) without errors
- `generate-mcp --validate-only` catches schema errors with clear messages
- All tests pass with `pytest`
- At least 2 working example configs with generated servers

## Constraints
- Generated code must use **FastMCP** (the Python MCP framework), not raw MCP SDK
- Config schema should feel familiar to the existing `template.agents.yaml` / `template.workflows.yaml` style
- The generator itself is a CLI tool, not a web UI
- No external dependencies beyond what FastMCP already requires
