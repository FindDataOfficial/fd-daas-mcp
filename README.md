# fd-daas-mcp

[![PyPI version](https://img.shields.io/pypi/v/fd-daas-mcp.svg)](https://pypi.org/project/fd-daas-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/fd-daas-mcp.svg)](https://pypi.org/project/fd-daas-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://finddataofficial.github.io/fd-daas-mcp/)

A single MCP server + CLI for skill-driven data access across financial,
economic, and statistical sources. Browse thousands of indicators, build entity
& indicator collections, run research workflows, and share dashboards - all
behind one stdio server with **181 tools across 8 groups** (187 with the
optional `pdf` extra).

`fd-daas-mcp` is the engine behind the [DAAS](https://github.com/FindDataOfficial)
skill-driven data-fetch workflow. Point any MCP client (Claude Code, etc.) at
it and the tools show up as `<group>_<tool>` calls - e.g. `daas_list_sources`,
`alerts_create_alert_rule`, `research_create`.

## Install

```bash
pip install fd-daas-mcp
```

Optional extras (all lazy-loaded - a missing extra degrades to a per-feature
error, never a startup crash):

```bash
pip install "fd-daas-mcp[pdf]"          # local PDF/text vector search (sqlite-vec)
pip install "fd-daas-mcp[crew]"         # CrewAI router for the leader group
pip install "fd-daas-mcp[akshare]"      # live A-share OHLCV/fundamentals
pip install "fd-daas-mcp[position]"     # CSS/xpath/json-path rule extraction
pip install "fd-daas-mcp[repl]"         # REPL history/autocomplete
pip install "fd-daas-mcp[dev]"          # pytest + mkdocs for contributors
```

## 60-second quickstart

```bash
# 1. Install
pip install fd-daas-mcp

# 2. Point your MCP client at it. For Claude Code, add to your .mcp.json:
```

```jsonc
// .mcp.json
{
  "mcpServers": {
    "fd-daas-mcp": {
      "command": "fd-daas-mcp-server",
      "args": []
    }
  }
}
```

```bash
# 3. Set a database URL (the schema auto-creates on first startup via
#    Base.metadata.create_all - no manual init step):
export DAAS_DATABASE_URL=sqlite:///daas.db

# 4. Or use the CLI directly:
fd-daas-mcp --help                  # see every group + tool
fd-daas-mcp daas list_sources       # invoke a tool: <group> <tool> [key=value ...]
fd-daas-mcp                          # drop into the REPL (needs [repl] extra)
```

On server startup the schema auto-creates and you'll see the registration
report:

```
registry: 181 tools across 8 sources (failed=0, skipped_optional=1)
```

(181 tools with the default install; 187 with the `pdf` extra installed. The
`pdf` group is optional and skipped when `sqlite-vec` is absent.)

## Tool groups

| Group       | Surface prefix   | What it does                                                          |
|-------------|------------------|-----------------------------------------------------------------------|
| `daas`      | `daas_*`         | Datasource/function/column catalog, entities, indicators, collections, rules, pipelines |
| `alerts`    | `alerts_*`       | Rule-based alerting over indicator series (Feishu/Discord/Slack/Telegram/DingTalk/WeCom/Twitter) |
| `cron`      | `cron_*`         | Scheduled task execution + history                                    |
| `composite` | `composite_*`    | Compose + chain tools across upstream MCPs                            |
| `dashboard` | `dashboard_*`    | Standalone-HTML dashboard registry + query                            |
| `leader`    | `leader_*`       | CrewAI DataCrew router, specialist agents, workflows, snapshots       |
| `pdf`       | `pdf_*`          | Local PDF/text semantic vector search (optional - needs `sqlite-vec`) |
| `research`  | `research_*`     | Persisted research bundles + generated markdown reports               |

The CLI tree mirrors this: `fd-daas-mcp <group> <tool>`. Both server and CLI
are generated from the same `registry.build()`, so they cannot drift.

## Skills

The `skills/` directory (in the repo, not the wheel) contains 15 Claude Code
skills that turn the raw tools into guided workflows - data fetch, research
orchestration, dashboard building, rule authoring, and more. To use them:

```bash
git clone https://github.com/FindDataOfficial/fd-daas-mcp.git
# Then point Claude Code at skills/ in the clone (or symlink into ~/.claude/skills/).
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [docs site](https://finddataofficial.github.io/fd-daas-mcp/) for details.

## Architecture

```
src/fd_daas_mcp/                 # the installable package
  server.py                      # FastMCP app - registers every tool as <group>_<tool>
  cli.py                         # Click CLI - auto-generated from registry.build()
  registry.py                    # AST-harvests tools from each mcp/<group>/ (per-group sys.modules isolation)
  selfcheck.py                   # offline invariants (run_invariants())
  models.py                      # vendored SQLAlchemy schema (Base + ORM for every domain)
  mcp/                           # tool-group source (shipped as package data)
    alerts/  cron/  composite/  daas/  dashboard/  leader/  pdf/  research/
```

The registry loads each group's `server.py` and harvests `@app.tool`-decorated
functions (inline groups) or the `*_tools.py` modules they import (non-inline
groups), with per-group `sys.modules` isolation so leaf modules like
`database.py` don't collide across groups. The `cron` group is loaded with
`suppress=True` to neutralize APScheduler's import-time thread while keeping
its idempotent DDL.

## Development

```bash
git clone https://github.com/FindDataOfficial/fd-daas-mcp.git
cd fd-daas-mcp
uv sync --extra dev               # editable install + dev deps (pytest, mkdocs, twine)
uv run pytest                     # offline test suite
uv run python -m fd_daas_mcp.selfcheck
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

## License

[MIT](LICENSE) - © FindDataOfficial.
