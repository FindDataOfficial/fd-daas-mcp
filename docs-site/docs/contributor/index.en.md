# Contributor Guide

For people extending DAAS - adding skills, datasources, MCP tools, or working on
the docs. The normal-user guide is [here](../user/index.md).

## Architecture in one paragraph

Data fetch is **skill-driven**: skills call Python data libraries (`akshare`,
`yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`)
directly and read/write `daas.db` via `sqlite3`. The consolidated
**`fd-daas-mcp`** MCP server is the sole `.mcp.json` entry - it hosts 9 tool
groups (`alerts`/`cron`/`composite`/`daas`/`dashboard`/`gateway`/`workflow`/`pdf`/
`research`) behind one stdio server and one Click CLI. The thin consolidation
layer is `fd-daas-mcp/daas/fd_daas_mcp/` (`server.py`/`registry.py`/`cli.py`/
`selfcheck.py`); each group's tool code lives in-package at
`fd-daas-mcp/<group>-mcp/`. Server and CLI both consume `registry.build()` so
the surfaces cannot drift.

## Repo layout

```
DAAS/
  .claude/skills/        # the fd-daas-* and fd-coding-* skills
  .mcp.json              # sole entry: fd-daas-mcp
  daas.db                # the git-tracked repo-root SQLite (registry + data)
  .env                   # single env file (git-ignored)
  fd-daas-mcp/           # consolidated MCP server + CLI + tests
    daas/fd_daas_mcp/    # consolidation layer (server/registry/cli/selfcheck)
    <group>-mcp/         # per-group tool code (alerts/cron/composite/.../research)
    bin/fd-daas-mcp-server
    tests/
  dashboards/            # standalone-HTML dashboards + index
  daas-doc/              # skill-generated markdown (research plans, intros, ...)
  docs-site/             # this MkDocs Material site
  construction/          # (stale) construction notes
  pyproject.toml         # uv project + dev dependency group (mkdocs-material)
```

## Environment

- **uv** + Python 3.10+ (dartlab needs 3.12 - run via
  `uv run --python 3.12 --with dartlab ...`).
- Single repo-root `.env`. Scripts load it automatically.
- `DAAS_DATABASE_URL=sqlite:///daas.db` (relative paths resolve against repo
  root). Query from repo root: `sqlite3 daas.db "..."`; `PRAGMA foreign_keys=ON`.

## Where to go next

- [Author a Skill](author-skill.md) - create a new `fd-daas-*` / `fd-coding-*` skill.
- [MCP Test Suite](mcp-tests.md) - run the server tests + selfcheck.
- [daas.db Schema](schema.md) - the table reference.
- [Deploy the Docs](deploy-docs.md) - GitHub Pages + WiFi/tunnel sharing.

## Removed surfaces - do not reference

Removed CLIs: `fd-akshare`/`fd-yfinance`/`fd-dartlab`/`fd-edgar`/`fd-edinet`/`fd-world`.
Removed skills/groups: `fd-daas-workflow-creator`, `fd-daas-scraw-scrapling`,
`fd-daas-scrapling-scraw-creator`, `fd-daas-cli-datasource-entities-builder`,
per-source `mcp__*` tools, and the `scrapling`/`firecrawl`/`massive` MCP groups.
The `cron`/`alerts`/`gateway`/`workflow`/`composite` MCPs are **not** removed - they are
folded into `fd-daas-mcp` as `<group>_<tool>`. `pdf` was restored (optional).
