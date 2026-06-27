# CLAUDE.md — cli-anything

Fork of [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything). The `CLI-Anything/` directory is the upstream — do not modify. Custom work lives in `akshare-agent-harness/`.

## Environment

Use **uv** for dependency and environment management. Python 3.10+.

```bash
uv sync                    # Create venv and install deps
uv run <command>           # Run in the project venv
```

## Construction Docs

Read these for architecture and construction decisions:

- `construction/mcp.md` — unified env, schema package (`mcp/models/`), single database (`mcp/daas.db`), all MCP servers
- `construction/dashboard.md` — Next.js dashboard architecture, sql.js access, schema mirrors

## Env & Schema (unified)

**Single `.env`**: root `.env` holds `DAAS_DATABASE_URL`, proxy, CKAN portal, dashboard port. Every MCP `server.py` loads `dotenv` from root first, then its own `.env` with `override=True`. Per-MCP `.env` only contains overrides.

**Single schema package**: `mcp/models/` — installable `pyproject.toml` package (`pip install -e mcp/models`). One `Base`, 13 tables across all MCP domains. Schema changes go here first.

**Single database**: `mcp/daas.db` — all MCPs and the dashboard read/write here.

## MCP Servers (`mcp/`)

All MCP servers are under `mcp/`, each in its own `*-mcp` directory.

### mcp/models/ — Shared Schema Package

Installable package with the one SQLAlchemy `Base`. All MCPs depend on it. Tables: `functions`, `function_columns`, `data_snapshots`, `schedules`, `executions`, `tasks`, `sources`, `daas_functions`, `daas_function_columns`, `observations`, `scraw_configs`, `datasources`, `datasource_columns`.

### mcp/leader-mcp/ — Multi-Harness Registry MCP

Query the unified registry across all harnesses. Exposes: `list_harnesses`, `search_functions`, `get_function_detail`, `list_categories`, `find_functions_by_column`, `list_datasources`, `toggle_datasource`, `save_snapshot`, `list_snapshots`, `query_snapshots`, `get_column_provenance`, `update_column_meta`.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL` env var
- **Models**: `from models import Function, FunctionColumn, DataSnapshot`
- **Key files**: `server.py`, `leader_tools.py`, `leader_database.py`, `unified_models.py`, `database.py`, `migrate_registry.py`, `registry_service.py`, `leader_crew.py`
- Imports use direct relative imports — run from within `mcp/leader-mcp/`

### mcp/cron-mcp/ — Agent Scheduler MCP

AI-agent-driven cron scheduling with SQLite + APScheduler.

- **Entry**: `python3 server.py` or `uv run python server.py`
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Schedule, Execution, Task` (local `models.py` deleted)
- **Key files**: `server.py`, `database.py`, `scheduler.py`, `agent_runner.py`, `registry.py`
- **Dependencies**: `apscheduler>=3.11.2`, `sqlalchemy>=2.0.51`
- Uses relative imports — run from within `mcp/cron-mcp/`

### mcp/daas-mcp/ — DaaS Multi-Source Data MCP

Source-based registry with live function execution.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import DaasSource, DaasFunction, DaasFunctionColumn, Observation` (local `models.py` deleted)
- **Key files**: `server.py`, `daas_tools.py`, `daas_database.py`, `registry_service.py`

### mcp/dashboard-mcp/ — Dashboard MCP

Browse databases, query tables, manage datasources, get stats.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Datasource, DatasourceColumn, ...` (no more inline CREATE TABLE)
- **Key files**: `server.py`

### mcp/akshare-mcp/ — AKShare Financial Data MCP

Registry queries + live function execution for AKShare (673+ Chinese financial data functions).

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `akshare`, `pandas`, `fastmcp`, plus `akshare-agent-harness/` on `sys.path`

### mcp/yfinance-mcp/ — yfinance (Yahoo Finance) Global Data MCP

Registry queries + live function execution for yfinance (global / US-market data). Mirrors `mcp/akshare-mcp/`. Tools: `search_functions`, `get_function_info`, `list_categories`, `list_functions`, `call_yfinance_function`. Commands starting `ticker_` dispatch via `yfinance.Ticker(symbol).<method>(...)`; top-level commands (`download`, `search`) call `yfinance.<name>(...)` directly.

- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `yfinance`, `pandas`, `fastmcp`, `sqlalchemy`, `click`, plus `yfinance-agent-harness/` on `sys.path`
- **Database**: harness `yfinance-agent-harness/.../metadata/registry.db` via `YFINANCE_DATABASE_URL` (empty = harness default)
- **Registered in `.mcp.json`** via `uv run --directory mcp/yfinance-mcp python server.py`

### mcp/combine-mcp/ — Composite MCP

Curate a composite MCP: pick named tools from multiple upstream MCP servers (proxied verbatim) and define chained tools (linear pipelines across upstreams). One composite served per process, selected by `COMPOSITE` env. Selection persisted in `daas.db`; management tools (`list_composites`, `add_upstream`, `list_available_tools`, `add_tool`, `add_chained_tool`, ...) always present. Served tool names are `<upstream>_<tool>` (mount namespace). Selection changes apply on restart.

- **Entry**: `python3 server.py` (FastMCP, stdio). `.mcp.json` entry sets `COMPOSITE=example`.
- **Database**: `mcp/daas.db` via `DAAS_DATABASE_URL`
- **Models**: `from models import Composite, Upstream, CompositeTool, CompositeChain`
- **Key files**: `server.py`, `combine_database.py`, `combine_tools.py`, `seed_example.py`, `selfcheck.py`
- **Self-check**: `uv run python selfcheck.py` (uses a temp DB; does not touch `daas.db`)
- **Seed shipped example**: `uv run python seed_example.py`
- Imports use direct relative imports — run from within `mcp/combine-mcp/`

### Other MCPs

`ckan-mcp/`, `cnstats-mcp/`, `worldbank-mcp/` — dotenv loading added, otherwise unchanged. `scrapling-*-mcp/` — own `init_db.py`.

## akshare-agent-harness

CLI wrapper for AKShare (673+ Chinese financial data functions). Click-based, with REPL.

```bash
# Install (from akshare-agent-harness/)
uv pip install -e ".[dev,repl]"

# Run CLI
uv run cli-anything-akshare              # REPL mode (default)
uv run cli-anything-akshare search 历史行情
uv run cli-anything-akshare call stock_zh_a_hist symbol=000001 start_date=20250101
uv run cli-anything-akshare --json call stock_sse_summary

# Run tests
uv run pytest -v                         # 8 unit + 6 E2E (from akshare-agent-harness/)
```

- Python >=3.10, depends on `click`, `pandas`, `akshare`
- Registry at `cli_anything/akshare/metadata/registry.json` (673 functions, 430 categories)
- `AKSHARE_REGISTRY` env var overrides registry path (falls back to auto-detected paths)
- Tests skip if `akshare` package not installed (`@pytest.mark.skipif`)
- E2E CLI tests use `_resolve_cli("cli-anything-akshare")` — falls back to `python -m`
- Two skill files: canonical at `skills/cli-anything-akshare/SKILL.md`, compatibility copy at `cli_anything/akshare/skills/SKILL.md`
- Run `AKSHARE.md` for agent-specific analysis of the AKShare adaptation

## yfinance-agent-harness

CLI wrapper for yfinance (Yahoo Finance global / US-market data). Click-based, with REPL. Mirrors the akshare harness layout; the proxy subcommand group is omitted (yfinance does not need it).

```bash
# Install (from yfinance-agent-harness/)
uv pip install -e ".[dev,repl]"

# Run CLI
.venv/bin/cli-anything-yfinance                       # REPL mode (default)
.venv/bin/cli-anything-yfinance search history
.venv/bin/cli-anything-yfinance call ticker_history symbol=AAPL period=1mo
.venv/bin/cli-anything-yfinance list --json

# Seed the registry DB
.venv/bin/python -m cli_anything.yfinance.core.migrate_registry

# Run tests (from yfinance-agent-harness/)
.venv/bin/python -m pytest -v                         # 17 tests
```

- Python >=3.10, depends on `click`, `pandas`, `yfinance`, `sqlalchemy`
- Curated registry at `cli_anything/yfinance/core/seed.py` (hand-curated, not scraped); mirrored into `cli_anything/yfinance/metadata/registry.db` via `migrate_registry.py`
- Two-table schema (`functions` / `function_columns`), same as the akshare harness
- `YFINANCE_DATABASE_URL` env var overrides the DB URL (empty = harness default)
- Command convention: `ticker_<method>` → `yfinance.Ticker(symbol).<method>(...)`; top-level (`download`, `search`) → `yfinance.<name>(...)`
- Tests skip live calls when `yfinance` not installed (`@pytest.mark.skipif`); E2E uses `_resolve_cli("cli-anything-yfinance")` → falls back to `python -m`
- Skill file: `skills/cli-anything-yfinance/SKILL.md`

## CLI-Anything (upstream)

Contains 60+ generated CLI harnesses in `<software>/agent-harness/` directories.

- **All use the same pattern**: `setup.py`, `cli_anything/<name>/` namespace (PEP 420 — no `__init__.py` in `cli_anything/`)
- **Generated by** `/cli-anything <path>` command (available via Claude Code plugin or OpenCode commands)
- **HARNESS.md** at `CLI-Anything/cli-anything-plugin/HARNESS.md` — the authoritative methodology spec
- Run harness tests: `cd <software>/agent-harness && uv run pytest -v`
- Force-installed mode: `CLI_ANYTHING_FORCE_INSTALLED=1 uv run pytest -v -s`
- CI: `check-root-skills.yml` validates root SKILL.md matches packaged copy on PR

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at /Users/chengsishi/code/cli-anything/specs/001-daas-provider/plan.md
<!-- SPECKIT END -->
