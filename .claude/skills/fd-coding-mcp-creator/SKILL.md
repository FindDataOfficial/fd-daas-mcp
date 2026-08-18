---
name: fd-coding-mcp-creator
description: >
  Scaffold a user-facing MCP composite: interview the user about which tools they
  need, write a composite manifest (upstreams + selected tools + embedded
  workflows + system prompt), register it in daas.db, and selfcheck that it serves.
  Use whenever the user wants to build/curate/compose their own MCP surface from
  existing upstreams — phrases like "make me an MCP that only exposes X tools",
  "compose a custom MCP", "curate an MCP from fd-open-data-mcp + fd-daas-mcp",
  "build a composite MCP", "give me an MCP with just these workflows", "组合一个
  MCP", "自定义 MCP". Do NOT use for onboarding a raw Python data library (that's
  fd-coding-daas-datasource-builder) or for authoring a single workflow manifest
  alone (that's workflow_register directly).
---

# fd-coding-mcp-creator

Compose a user-facing MCP **composite** — a curated surface that selects a handful
of tools from one or more upstream MCP servers, optionally embeds registered
workflow manifests, and carries a system prompt. The composite is registered in
daas.db and served in-proc by the consolidated fd-daas-mcp server (set
`COMPOSITE=<name>` and start `bin/fd-daas-mcp-server`).

This skill curates what already exists into a focused surface — it does NOT create
new tools or upstreams from scratch. To onboard a brand-new data library, use
`fd-coding-daas-datasource-builder`. To author a multi-step workflow manifest, use
`workflow_register` directly.

## When to use

- "给我做一个只暴露这几个工具的 MCP" / "compose a custom MCP from these tools"
- "curate an MCP surface with just the data-fetch + indicators workflows"
- "build a composite MCP with a system prompt that scopes the agent to macro data"

## The manifest format

A composite manifest (written by `composite_create_manifest`) is:

```json
{
  "name": "macro-analyst",
  "description": "macro data fetch + indicators, scoped to sovereign/central-bank series",
  "upstreams": [
    {"key": "data", "transport": "http", "url": "http://127.0.0.1:8300"}
  ],
  "tools": [
    {"upstream": "data", "tool": "read"}
  ],
  "workflows": ["data-fetch", "indicators"],
  "prompt": "You are a macro-data analyst. Only fetch sovereign and central-bank series..."
}
```

- `upstreams` — MCP servers the composite proxies. `key` is the mount namespace (served tools become `<key>_<tool>`). `transport` = `http` (needs `url`) or `stdio` (needs `command`/`args`/`env`/`cwd`). The canonical upstream is `fd-open-data-mcp` over HTTP at `http://127.0.0.1:8300`.
- `tools` — list of `{upstream: <key>, tool: <name>}`. Discover available tools on an upstream with `composite_list_available_tools(composite, upstream_key, query)`.
- `workflows` — names of registered workflow manifests (rows in the `workflows` table, registered via `workflow_register`). Each surfaces as a lazy tool that runs the workflow engine on call. Check `workflow_list()` for what's registered.
- `prompt` — system prompt applied to the composite's FastMCP surface (`app.instructions`).

## Workflow

### Step 1 — Interview

Ask the user (offer sensible defaults so they can just confirm):

1. **Purpose** — what should this MCP do? (e.g. "macro analyst", "A-share fundamentals")
2. **Upstreams** — usually just `fd-open-data-mcp` (HTTP @ :8300, key `data`). Add more only if the user names a specific server.
3. **Tools** — which tools from each upstream. Discover with `composite_list_available_tools` if unsure. Default: the handful the purpose implies (e.g. `read`, `search_concepts`).
4. **Workflows** — registered workflow names to embed. Check `workflow_list()`. Common: `data-fetch`, `indicators`, `research`.
5. **System prompt** — a short scope for the serving agent. Keep it brief.

### Step 2 — Draft the manifest

Assemble the JSON above from the interview answers. Use `data` as the upstream key by convention.

### Step 3 — Register

Call the MCP tool:

```
composite_create_manifest(
    name="macro-analyst",
    upstreams=[{"key": "data", "transport": "http", "url": "http://127.0.0.1:8300"}],
    tools=[{"upstream": "data", "tool": "read"}],
    workflows=["data-fetch", "indicators"],
    prompt="You are a macro-data analyst...",
    description="macro data fetch + indicators",
)
```

Updates later: `composite_update_manifest(name, ...)` — note `upstreams`/`tools`
REPLACE the existing sets wholesale when given. List: `composite_list_manifests()`.
Delete: `composite_delete_manifest(name)`.

### Step 4 — Selfcheck

Verify the composite serves its tools + prompt (run from repo root):

```bash
fd-daas-mcp/.venv/bin/python -c "
import os, asyncio, sys
os.environ['COMPOSITE'] = 'macro-analyst'
sys.path.insert(0, 'fd-daas-mcp/composite-mcp')
from fastmcp import FastMCP
import server
app = FastMCP(name='probe')
server.build_served_tools(app)
tools = asyncio.run(app.list_tools())
print('tools:', [t.name for t in tools])
print('prompt set:', bool(app.instructions))
"
```

Confirm: every `tool` surfaces (as `<key>_<tool>`), every `workflow` name surfaces,
and `prompt set: True`. Then tell the user the composite name, the served tool list,
and how to run it: `COMPOSITE=<name> fd-daas-mcp/bin/fd-daas-mcp-server`.

## Principles

- **Curate, don't create.** A composite selects existing tools/workflows; it never invents new ones. If a needed tool doesn't exist, stop and point the user at `fd-coding-daas-datasource-builder` or `workflow_register`.
- **One upstream by default.** `fd-open-data-mcp` covers all data fetch. Add upstreams only when the user names a specific server.
- **Prompt is scope, not script.** A short system prompt that bounds the agent beats a long playbook.
- **Selfcheck before handing off.** The user trusts a composite verified to serve.
