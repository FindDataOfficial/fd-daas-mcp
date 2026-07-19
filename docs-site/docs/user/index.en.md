# User Guide

This guide is for **normal users** - people who want to fetch data, compute
indicators, build collections, run research, and share dashboards. You do not
need to write code or modify the project.

## What DAAS gives you

DAAS is a local data platform. Out of the box it ships with:

- **~5,600 entities** - 5,575 stocks + 60 countries, each linkable to its
  datasource identifiers.
- **Hundreds of prebuilt indicator rules** (and the platform scales to thousands
  as you add datasources) - moving averages, RSI, rolling volatility, pct
  change, z-scores, and macro/economic series.
- **8 MCP tool groups** (alerts, cron, composite, daas, dashboard, leader, pdf,
  research) for browsing, scheduling, alerting, and orchestration.
- **40+ skills** that wrap common workflows (fetch, research, dashboard,
  collections, PDF search, web scraping).

## How you talk to DAAS

You have two first-class paths; pick whichever fits the moment:

1. **Skills** (recommended for first-time users) - in Claude Code, just describe
   what you want ("fetch AAPL daily prices and add a 20-day moving average").
   The right skill resolves the entity, calls the Python library, and persists
   to `daas.db`. See [First Fetch in 5 Minutes](first-fetch.md).
2. **MCP server** - if your client speaks MCP, point it at `fd-daas-mcp` (the
   sole `.mcp.json` entry) and call the `<group>_<tool>` tools directly. See
   [MCP Tools](../mcp/index.md).

Both paths share one `daas.db`, so work done through one is immediately visible
to the other.

## Recommended reading order

1. [Install & Deploy](install.md) - get the project running.
2. [First Fetch in 5 Minutes](first-fetch.md) - your first real fetch + indicator.
3. [Examples](../examples/index.md) - the seven canonical workflows.
4. [Concepts](../concepts/entities.md) - understand entities, collections, indicators.
5. [Skills](../skills/index.md) - the official skill families.

## Concepts you will meet

- **Entity** - a stock or country (e.g. AAPL, CN). See
  [Entities](../concepts/entities.md).
- **Datasource** - a source of data (akshare, yfinance, edgar, ...).
- **Indicator rule** - a binding that computes a series (e.g. `SPY_ma5` = 5-day
  SMA of SPY closes) into the `observations` table.
- **Collection** - a named group of entities or indicators. See
  [Collections & Indicators](../concepts/collections.md).
- **Research** - a persisted bundle tying an entity collection, an indicator
  collection, a dashboard, and a pipeline to a markdown report.

!!! note "No coding required"
    If you can describe what you want in plain language, a skill can do it. The
    examples use real commands so you can copy-paste when you prefer.
