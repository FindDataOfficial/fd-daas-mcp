# MCP Tools

DAAS ships one consolidated MCP server - **`fd-daas-mcp`** - as the sole entry
in repo-root `.mcp.json`. It hosts **8 tool groups** behind one stdio server and
one `fd-daas-mcp` Click CLI. Tools register as **`<group>_<tool>`** (e.g.
`daas_search_entities`, `research_create`, `pdf_ingest_document`).

## Why one server

Server and CLI both consume `daas/fd_daas_mcp/registry.py` (`registry.build()`),
so the two surfaces cannot drift. Each group's tool code lives in-package at
`fd-daas-mcp/<group>-mcp/`; the thin consolidation layer is
`fd-daas-mcp/daas/fd_daas_mcp/` (`server.py` / `registry.py` / `cli.py` /
`selfcheck.py`).

## Launch

`.mcp.json` points `command` at `fd-daas-mcp/bin/fd-daas-mcp-server`, a
self-locating POSIX shell script that sets `PYTHONPATH` and execs
`.venv/bin/python -m fd_daas_mcp.server`.

```bash
fd-daas-mcp/bin/fd-daas-mcp-server             # launch the server
fd-daas-mcp/.venv/bin/python -m fd_daas_mcp.selfcheck   # offline invariants
```

## The 8 groups

| Group | Prefix | Covers |
| --- | --- | --- |
| `daas` | `daas_*` | Entity/datasource/indicator/catalog browsing, collections, rules, calc. |
| `research` | `research_*` | Research bundle create/get/list/update/delete/refresh/report + components. |
| `dashboard` | `dashboard_*` | Standalone-HTML dashboard registry CRUD + index regen. |
| `cron` | `cron_*` | DB-stored tasks + schedules + execution history. |
| `alerts` | `alerts_*` | Alert rules, channels, series, events over `observations`/`scraw_*`. |
| `leader` | `leader_*` | CrewAI DataCrew + specialist agents + workflows + registry. |
| `pdf` | `pdf_*` | Local PDF/text vector search (sqlite-vec). Optional - gated on `sqlite-vec`. |
| `composite` | `composite_*` | Compose multiple upstream MCP servers + chained tool pipelines. |

See [Tool Groups](groups.md) for the per-group tool lists.

!!! note "Skills vs. MCP"
    Skills and MCP tools share one `daas.db`. Skills are simpler/offline; the
    MCP server is richer (scheduling, alerts, orchestration, search). Use either.

## Not removed

The `cron` / `alerts` / `leader` / `composite` groups are **not** removed -
they are folded into `fd-daas-mcp` as `<group>_<tool>`. The dropped
`scrapling` / `firecrawl` / `massive` MCP groups and the per-source `mcp__*`
tools are gone; do not reference them.
