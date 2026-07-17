# DAAS - Data As a Service

**Skill-driven data fetch for financial, economic, and statistical data** - a
local platform that turns Python data libraries (`akshare`, `yfinance`, `edgar`,
`edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`) into a queryable,
indicator-computing, dashboard-ready store backed by a single SQLite file
(`daas.db`).

You can drive DAAS through **Claude Code skills** or through a **consolidated
MCP server** - both paths read/write the same database.

## What you can do

- **Browse thousands of indicators** across companies, industries, cities, and
  countries - moving averages, RSI, volatility, macro series, and more.
- **Build collections** - group entities (a watchlist) and indicators (a
  reusable bundle) with audit-tracked membership.
- **Run a research** - from a goal to a persisted bundle: analyze -> collections
  -> indicators -> dashboard -> markdown report.
- **Inspect any entity** - see which datasources cover a stock/country and how
  to fetch them.
- **Extract & analyze financial reports** - pull filings (EDGAR/EDINET/DART) and
  compute dozens of prebuilt indicators on top.
- **Add your own datasource** - a website, a PDF/document, or a database - and
  query it like the built-ins.
- **Share a dashboard** - publish a standalone HTML dashboard over WiFi/LAN or
  a public tunnel.

## Two ways to use it

| Path | When to use |
| --- | --- |
| **Skills** (`.claude/skills/`) | Offline-friendly, simplest. Skills call Python libs directly + `sqlite3`. |
| **MCP server** (`fd-daas-mcp`) | Richer - catalog browsing, cron, alerts, dashboards, orchestration, PDF search. |

Both share one `daas.db`. See [Concepts -> Entities](concepts/entities.md) for
the data model, or jump to the [Examples](examples/index.md).

## Where to start

- **New here?** Read the [User Guide](user/index.md), then
  [Install & Deploy](user/install.md), then
  [First Fetch in 5 Minutes](user/first-fetch.md).
- **Want examples?** Go straight to [Examples](examples/index.md).
- **Contributing?** Read the [Contributor Guide](contributor/index.md).

!!! tip "This site vs. the repo README"
    The repo-root `README.md` is a verified quickstart. This site is the
    teachable, role-based guide - start here, use the README for copy-paste
    commands.
