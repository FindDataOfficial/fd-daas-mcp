# Compose an MCP

A **composite** is a curated MCP surface: pick a handful of tools from one or
more upstream MCP servers, optionally embed registered workflow manifests,
attach a system prompt, and serve the whole thing as one named MCP. Composites
are stored in `daas.db` and served in-proc by the consolidated `fd-daas-mcp`
server.

This page is the authoring flow: manifest format → tool selection → workflow
embedding → prompt → run. For the per-tool reference see
[Tool Groups](groups.md). For a guided scaffold, use the
`fd-coding-mcp-creator` skill.

## The manifest format

A composite manifest (written by `composite_create_manifest`) is a JSON object:

```json
{
  "name": "macro-analyst",
  "description": "macro data fetch + indicators, scoped to sovereign series",
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

| Field | Purpose |
| --- | --- |
| `name` | Unique composite name; used as `COMPOSITE=<name>` to serve it. |
| `description` | Optional human-readable label. |
| `upstreams` | MCP servers the composite proxies. `key` is the mount namespace (served tools become `<key>_<tool>`). `transport` = `http` (needs `url`) or `stdio` (needs `command`/`args`/`env`/`cwd`). The canonical upstream is `fd-open-data-mcp` over HTTP at `http://127.0.0.1:8300`. |
| `tools` | List of `{upstream: <key>, tool: <name>}`. Each is proxied and served as `<key>_<tool>`. |
| `workflows` | Names of registered workflow manifests (rows in the `workflows` table, registered via `workflow_register`). Each surfaces as a lazy tool that runs the workflow engine on call. |
| `prompt` | System prompt applied to the composite's FastMCP surface. |

## Authoring flow

### 1. Pick upstreams

Almost always just `fd-open-data-mcp` (HTTP @ :8300, key `data`). It covers all
data fetch. Add a second upstream only when you need a server the data layer
doesn't already front.

### 2. Select tools

List what an upstream exposes, then pick the few you want:

```
composite_list_available_tools(composite="macro-analyst", upstream_key="data")
composite_add_tool(composite="macro-analyst", upstream_key="data", tool_name="read")
```

Or, in manifest mode, pass the whole set at once:

```
composite_create_manifest(
    name="macro-analyst",
    upstreams=[{"key": "data", "transport": "http", "url": "http://127.0.0.1:8300"}],
    tools=[{"upstream": "data", "tool": "read"}],
)
```

### 3. Embed workflows

Embed a registered workflow so callers can trigger a multi-step fetch without
remembering the steps. List registered workflows with `workflow_list()`, then
pass their names in `workflows`:

```
composite_create_manifest(..., workflows=["data-fetch", "indicators"])
```

Each name becomes a lazy tool on the composite — calling it runs the workflow
engine with the params you pass.

### 4. Attach a prompt

A short system prompt scopes the serving agent. Keep it brief — a scope beats a
playbook:

```
composite_create_manifest(..., prompt="You are a macro-data analyst. Only fetch sovereign and central-bank series.")
```

### 5. Serve

```bash
COMPOSITE=macro-analyst fd-daas-mcp/bin/fd-daas-mcp-server
```

The served surface exposes: each selected tool (as `<key>_<tool>`), each embedded
workflow (as its own tool), plus the management tools — all behind the system
prompt.

## Maintenance

- **Update** — `composite_update_manifest(name, ...)`; note `upstreams`/`tools`
  *replace* the existing sets wholesale when given.
- **List** — `composite_list_manifests()`.
- **Delete** — `composite_delete_manifest(name)` (cascades upstreams/tools/chains).

## Principles

- **Curate, don't create.** A composite selects existing tools/workflows; it
  never invents new ones. If a needed tool doesn't exist, build the upstream
  first (`fd-coding-daas-datasource-builder`) or register a workflow
  (`workflow_register`).
- **One upstream by default.** `fd-open-data-mcp` covers all data fetch.
- **Prompt is scope, not script.** A short bound beats a long playbook.
