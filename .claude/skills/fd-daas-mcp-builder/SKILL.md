---
name: fd-daas-mcp-builder
description: >
  Build a complete standalone MCP server from a DAAS source adapter. Use this
  skill whenever the user asks to build, create, or generate an MCP server for
  a data source (CKAN, World Bank, CNStats, or any other DAAS adapter). Also
  use when the user says "add a new mcp for X source", "build mcp for Y", or
  "generate a ckan-mcp / worldbank-mcp / cnstats-mcp". This skill reads the
  source adapter from daas-agent-harness, generates server.py with 5 tools,
  pyproject.toml, .env/.env.example, mcp.yaml, uv syncs, and registers in
  .mcp.json — everything needed for a working stdio MCP server.
---

# FD-DAAS-MCP Builder

Generate a complete, working MCP server from a DAAS source adapter.

Reads an existing adapter in `daas-agent-harness/cli_anything/daas/sources/<source>_source.py`,
extracts all metadata (source name, label, description, functions, columns, categories,
dependencies), then generates a full MCP server directory in `mcp/<source>-mcp/`.

## What gets generated

| File | Purpose |
|------|---------|
| `mcp/<source>-mcp/server.py` | FastMCP entry point — 5 tools (search, detail, list, categories, call) |
| `mcp/<source>-mcp/pyproject.toml` | uv-managed deps |
| `mcp/<source>-mcp/.env` | DB URL + source-specific config + proxy |
| `mcp/<source>-mcp/.env.example` | Same, with comments |
| `mcp/<source>-mcp/mcp.yaml` | MCP server config for Claude Code |
| `mcp/<source>-mcp/.venv/` | uv-created virtual environment (via `uv sync`) |
| `mcp/<source>-mcp/uv.lock` | Lock file (via `uv sync`) |

## Prerequisites

The target harness must already exist with:
- `daas-agent-harness/cli_anything/daas/sources/<source>_source.py` — source adapter
- `daas-agent-harness/cli_anything/daas/core/models.py` — SQLAlchemy models (Source, Function, FunctionColumn)
- `mcp/daas.db` — populated with source functions and columns (run `mcp/populate_daas.py` first)

## Workflow

### Step 1: Read the source adapter

Read `daas-agent-harness/cli_anything/daas/sources/<source>_source.py`. Extract:

1. **source name** — the string from the adapter's `name` property (e.g., `"ckan"`, `"cnstats"`, `"worldbank"`)
2. **source label** — the string from the adapter's `label` property (e.g., `"CKAN Open Data"`)
3. **source description** — from `description` property
4. **function list** — the `*_FUNCTIONS` or `*_INDICATORS` constant at module level. Each entry has `name`, `label`, `description`, `category`, `parameters`, `columns`
5. **dependencies** — from `is_available()`: what `import` does it check? That's the Python package name
6. **install hint** — the pip command from `is_available()` error messages
7. **portal URL / extra config** — from the adapter's `url` property and `__init__` defaults

### Step 2: Derive template variables

From the extracted data, compute:

| Variable | Derivation | Example |
|----------|-----------|---------|
| `SOURCE` | Adapter `.name` | `ckan`, `worldbank`, `cnstats` |
| `SOURCE_LABEL` | Adapter `.label` | `CKAN Open Data` |
| `ENV_PREFIX` | `SOURCE.upper()` | `CKAN`, `WORLDBANK`, `CNSTATS` |
| `EXTRA_DEPS` | Package names from `is_available()` | `"ckanapi>=4.7"` |
| `INSTALL_HINT` | From adapter error messages | `"Install: pip install ckanapi"` |
| `SEARCH_HINT` | Description of what the source covers | e.g., `Covers 20+ key indicators: GDP, population, unemployment...` |
| `EXAMPLE_FUNCTION` | First function name from the constant | `ckan_package_search` |
| `CALL_TOOL_DESCRIPTION` | What the call tool does | `Execute a CKAN function and return results as JSON.` |
| `SUPPORTED_FUNCTIONS` | Comma-separated list of function names | `ckan_package_search, ckan_package_show, ...` |
| `PARAMS_EXAMPLE` | From first function's parameters | `Example: '{"q": "air quality", "rows": 5}'` |
| `SOURCE_SPECIFIC_CONFIG` | Extra env vars from adapter config | `CKAN_PORTAL_URL=https://data.gov/api/3/` |
| `EXTRA_ENV` | Extra mcp.yaml env entries | `CKAN_PORTAL_URL: https://data.gov/api/3/` |

**Dependency mapping** (from known adapters):
- `import ckanapi` → `"ckanapi>=4.7"`
- `import akshare` → `"akshare>=1.17.0"`
- `import requests` → `"requests>=2.28"` (already built-in, optional)
- `import wbgapi` → `"wbgapi"` (but worldbank uses raw requests, so `"requests>=2.28"`)

### Step 3: Generate files from templates

Read each template in `references/`, fill in variables, write to `mcp/<source>-mcp/`:

1. **server.py** — from `references/server-template.py`
2. **pyproject.toml** — from `references/pyproject-template.toml`
3. **.env** and **.env.example** — from `references/env-template`
4. **mcp.yaml** — from `references/mcp-template.yaml`

### Step 4: uv sync

```bash
cd mcp/<source>-mcp && uv sync
```

This creates `.venv/` and `uv.lock`.

### Step 5: Populate daas.db

```bash
cd mcp && python3 populate_daas.py
```

This ensures the new source's functions and columns exist in `mcp/daas.db`.

### Step 6: Register in .mcp.json

Add an entry to `.mcp.json` under `mcpServers`:

```json
"<source>-mcp": {
  "type": "stdio",
  "command": "uv",
  "args": [
    "run",
    "--directory",
    "/Users/chengsishi/code/cli-anything/mcp/<source>-mcp",
    "fastmcp",
    "run",
    "server.py",
    "--no-banner"
  ],
  "env": {
    "DAAS_DATABASE_URL": "sqlite:///../daas.db"
  }
}
```

If extra env vars are needed (like `CKAN_PORTAL_URL`), add them to the `env` block.

### Step 7: Verify

Test the server starts and all 5 tools are registered:

```bash
cd mcp/<source>-mcp && DAAS_DATABASE_URL=sqlite:///../daas.db uv run python -c "
from server import app
import asyncio
async def main():
    tools = await app.list_tools()
    names = [t.name for t in tools]
    assert 'search_functions' in names, 'missing search_functions'
    assert 'get_function_info' in names, 'missing get_function_info'
    assert 'list_categories' in names, 'missing list_categories'
    assert 'list_functions' in names, 'missing list_functions'
    assert 'call_<source>_function' in names, 'missing call_<source>_function'
    print(f'OK: {len(names)} tools registered')
    for t in tools:
        print(f'  {t.name}')
asyncio.run(main())
"
```

Test each tool against daas.db returns real data:

```bash
cd mcp/<source>-mcp && DAAS_DATABASE_URL=sqlite:///../daas.db uv run python -c "
from server import app
import asyncio, json
async def main():
    r = await app.call_tool('list_categories', {})
    d = json.loads(r.content[0].text)
    print(f'categories: {d[\"total_categories\"]}, functions: ...')
    r = await app.call_tool('list_functions', {'limit': 5})
    d = json.loads(r.content[0].text)
    print(f'list_functions: {d[\"count\"]} total')
asyncio.run(main())
"
```

## When to use this vs fd-daas-mcp-creator

- **fd-daas-mcp-builder** (this skill): Builds a complete MCP *server* from a DAAS source adapter. Output is `mcp/<source>-mcp/` with server.py, FastMCP tools, .venv, mcp.yaml.
- **fd-daas-mcp-creator**: Adds SQLAlchemy data layer to a CLI-Anything *harness* (models, database, migration). Output is `cli_anything/<name>/core/` with models.py, database.py, etc.

They're complementary: use fd-daas-mcp-creator to add DB backing to a harness, then fd-daas-mcp-builder to generate the MCP server.

## Reference files

- `references/server-template.py` — Full server.py template with `{{PLACEHOLDER}}` variables
- `references/pyproject-template.toml` — pyproject.toml template
- `references/env-template` — .env template
- `references/mcp-template.yaml` — mcp.yaml template

Read them before generating — they contain the exact patterns to follow.
