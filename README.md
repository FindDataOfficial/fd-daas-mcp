# cli-anything

Skill-driven data fetch for financial, economic, and statistical data - built on [CLI-Anything](https://github.com/HKUDS/CLI-Anything).

## Overview

Skills call Python data libraries (`akshare`, `yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`) **directly** and read/write `daas.db` via **sqlite3**. There are no MCP servers and no `fd-*` CLIs - `.mcp.json` is empty.

## Quick Start

```bash
# Python 3.10+, uses uv
uv sync

# Resolve an entity + indicator via sqlite3, then fetch via the Python lib.
# The skill-based-data-fetch skill owns the workflow; its scripts do the work:

# List the source dispatch shapes
uv run python .claude/skills/skill-based-data-fetch/scripts/dispatch.py

# Compute an existing indicator (upserts into observations)
uv run --with pandas --with numpy python .claude/skills/skill-based-data-fetch/scripts/run_indicator.py SPY_ma5

# Query daas.db directly
sqlite3 mcp/daas.db "SELECT name, datasource, op FROM indicator_rules LIMIT 10"
```

See `CLAUDE.md` for the full architecture and `construction/daas-storage.md` for the `daas.db` schema.

## Project Structure

```
├── .claude/skills/          # Skills (skill-based-data-fetch is the core fetch skill)
├── mcp/daas.db              # The shared SQLite database (registry + observations + scraw_*)
├── dashboards/              # Standalone HTML dashboards (+ index.html, daas.md)
├── construction/            # Architecture docs
├── CLI-Anything/            # Upstream (do not modify)
└── .env                     # DAAS_DATABASE_URL, proxy, EDGAR_IDENTITY, EDINET_API_KEY, ...
```

## License

Apache 2.0 - see upstream [CLI-Anything](https://github.com/HKUDS/CLI-Anything).
