# Quickstart

From zero to your first tool call in under a minute.

## 1. Install

```bash
pip install fd-daas-mcp
```

## 2. Provision the database

```bash
fd-daas-mcp init       # creates daas.db (full schema + dep-free starter sources)
fd-daas-mcp doctor      # read-only health check (path, schema, row counts)
```

`DAAS_DATABASE_URL` is optional - unset, it defaults to `./daas.db` (writable
cwd) or `~/.fd-daas-mcp/daas.db`. Set it only to relocate.

For LLM-powered features (the `leader` group's CrewAI router) and alert
channels, copy `.env.example` to `.env` and fill in the values you need.
Everything else works offline.

## 3. Verify

```bash
fd-daas-mcp --help                  # lists every group + tool
fd-daas-mcp daas list_sources       # invoke a tool: <group> <tool> [k=v ...]
fd-daas-mcp daas list_sources --json
```

Or run the selfcheck:

```bash
python -m fd_daas_mcp.selfcheck
# registry: 181 tools across 8 sources (failed=0, skipped_optional=1)
```

## 4. Point an MCP client at it

Copy [`examples/.mcp.json`](.mcp.json) to your project root. Restart Claude
Code (or your MCP client). The tools appear as `daas_*`, `alerts_*`,
`cron_*`, `composite_*`, `dashboard_*`, `leader_*`, `pdf_*`, `research_*`.

The schema is also auto-created on first server startup (and the resolved DB
path is logged at INFO); `fd-daas-mcp init` is the explicit provision + seed
path, and `fd-daas-mcp doctor` is the read-only check.

## 5. (Optional) Start the stdio server manually

```bash
fd-daas-mcp-server                  # the console-script launcher
# or
python -m fd_daas_mcp.server
```

## Next steps

- Browse the [docs site](https://finddataofficial.github.io/fd-daas-mcp/) for
  concepts (entities, collections, indicators) and the seven canonical
  example workflows.
- Clone the repo to use the 15 Claude Code skills in `skills/`.
