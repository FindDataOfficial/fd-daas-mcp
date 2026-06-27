## Why

The project standardizes data libraries behind two parallel surfaces — a Click-based CLI harness (`*-agent-harness/`) for interactive/ scripted use, and a FastMCP server (`mcp/*-mcp/`) so Claude Code can query and execute functions directly. AKShare covers Chinese markets (673 functions), but there is no equivalent for global / US-market data. `yfinance` is the de-facto Python library for Yahoo Finance global market data and would fill that gap, giving both the CLI and the MCP layer access to global equities, ETFs, fundamentals, options, and historical prices.

## What Changes

- Add a new CLI harness `yfinance-agent-harness/` mirroring the akshare harness layout: namespace package `cli_anything/yfinance/` (PEP 420), a metadata registry of yfinance callables, `core/` (registry, models, database, runner), `akshare_cli`-equivalent `yfinance_cli.py` Click CLI with REPL, `setup.py` installable as `cli-anything-yfinance`, and pytest tests that skip when `yfinance` is not installed.
- Seed a yfinance function registry (curated set of the most useful `yfinance.Ticker` methods + top-level functions like `download`/`search`, organized into categories such as price-history, fundamentals, holders, options, calendar) stored as JSON and mirrored into a SQLite registry via the same two-table (`functions` / `function_columns`) SQLAlchemy design akshare uses.
- Add a new MCP server `mcp/yfinance-mcp/` mirroring `mcp/akshare-mcp/server.py`: tools `search_functions`, `get_function_info`, `list_categories`, `list_functions`, and `call_yfinance_function` (the live-execution tool), FastMCP stdio transport, own `pyproject.toml` + `.env`/`.env.example`.
- Register `yfinance-mcp` in root `.mcp.json` using the same `uv run --directory ... python server.py` pattern as `cron-mcp`.
- **BREAKING**: none. Purely additive.

## Capabilities

### New Capabilities
- `yfinance-cli`: A Click-based CLI harness for yfinance — registry of curated yfinance callables with search/info/list/call commands plus a REPL, backed by a SQLite registry using the shared `functions`/`function_columns` schema.
- `yfinance-mcp-server`: A FastMCP server exposing yfinance registry-query tools and a live `call_yfinance_function` execution tool, mirroring the akshare-mcp server pattern and registered in `.mcp.json`.

### Modified Capabilities
<!-- None — no existing spec-level behavior changes. -->

## Impact

- **New code**: `yfinance-agent-harness/` (namespace package, CLI, core, registry JSON + DB, tests, skills); `mcp/yfinance-mcp/` (server.py, pyproject.toml, .env, .env.example).
- **Modified config**: root `.mcp.json` gains a `yfinance-mcp` entry.
- **Dependencies**: new `yfinance` runtime dependency (plus existing `pandas`, `sqlalchemy`, `click`, `fastmcp`). `yfinance` is pulled into the harness `setup.py` and the MCP `pyproject.toml`.
- **Databases**: harness ships its own `metadata/registry.db` (SQLite), separate from the unified `mcp/daas.db`. No writes to `daas.db` required (mirrors akshare-mcp, which does not self-register).
- **No upstream changes**: `CLI-Anything/` upstream untouched.
