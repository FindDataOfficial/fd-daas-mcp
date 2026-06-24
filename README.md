# DAAS — Data as a Service

Multi-harness MCP platform for financial, economic, and statistical data — built on [CLI-Anything](https://github.com/HKUDS/CLI-Anything).

## Overview

DAAS wraps 673+ Chinese financial data functions (AKShare), plus CKAN, World Bank, and CNStats data sources, behind MCP servers that AI agents can discover and call.

## MCP Servers

| Server | Purpose |
|--------|---------|
| `mcp/akshare-mcp/` | AKShare financial data — 673+ functions (stocks, funds, futures, macro) |
| `mcp/ckan-mcp/` | CKAN open data portal queries |
| `mcp/cnstats-mcp/` | China National Statistics data |
| `mcp/worldbank-mcp/` | World Bank development indicators |
| `mcp/leader-mcp/` | Unified multi-harness registry — search across all data sources |
| `mcp/cron-mcp/` | AI-agent-driven cron scheduler with execution history |
| `mcp/daas-mcp/` | DAAS unified data access layer |
| `mcp/scrapling-uv-mcp/` | Web scraping with Playwright (stealth mode) |
| `mcp/scrapling-docker-mcp/` | Web scraping via Docker |

## Quick Start

```bash
# Python 3.10+, uses uv for dependency management
uv sync

# Run AKShare CLI (REPL mode)
uv run cli-anything-akshare

# Search for a financial data function
uv run cli-anything-akshare search 历史行情

# Call a function directly
uv run cli-anything-akshare call stock_zh_a_hist symbol=000001 start_date=20250101
```

## Project Structure

```
├── akshare-agent-harness/   # AKShare CLI wrapper (Click + REPL)
├── CLI-Anything/            # Upstream (do not modify)
├── mcp/                     # All MCP servers
│   ├── leader_mcp.db        # Unified registry database
│   ├── cron.db              # Scheduler database
│   └── daas_registry.db     # DAAS data registry
└── .claude/                 # Claude Code skills & settings
```

## License

Apache 2.0 — see upstream [CLI-Anything](https://github.com/HKUDS/CLI-Anything).
