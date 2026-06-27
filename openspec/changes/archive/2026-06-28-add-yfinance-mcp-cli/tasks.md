## 1. Harness scaffold

- [x] 1.1 Create `yfinance-agent-harness/` with `setup.py` (name `cli-anything-yfinance`, console script `cli-anything-yfinance=cli_anything.yfinance.yfinance_cli:cli`, deps `click`, `pandas`, `yfinance`, `sqlalchemy`, extras `repl`/`dev`, `python_requires>=3.10`)
- [x] 1.2 Create PEP 420 namespace package `cli_anything/yfinance/` (no `cli_anything/__init__.py`), with `__init__.py`, `__main__.py`, `README.md`
- [x] 1.3 Create `cli_anything/yfinance/core/` (`__init__.py`, `models.py`, `database.py`, `registry.py`, `runner.py`) by copying the akshare equivalents and namespacing to `cli_anything.yfinance`; env var `YFINANCE_DATABASE_URL`, default `metadata/registry.db`
- [x] 1.4 Create `cli_anything/yfinance/utils/` (`__init__.py`, `output.py`) copied from akshare utils

## 2. Registry curation

- [x] 2.1 Create `cli_anything/yfinance/core/seed.py` — curated dict of yfinance callables: `ticker_history`, `ticker_info`, `ticker_financials`, `ticker_balance_sheet`, `ticker_cashflow`, `ticker_holders`, `ticker_option_chain`, `ticker_calendar`, `ticker_dividends`, `ticker_splits` (categories: price-history, fundamentals, holders, options, calendar) plus top-level `download`, `search`; each with `command`, `category`, `description`, `source`, `parameters`, representative `columns` (mark representative-only with a `ponytail:` comment)
- [x] 2.2 Create `cli_anything/yfinance/core/migrate_registry.py` — build `metadata/registry.db` from `seed.py` into the two-table schema, mirroring akshare's `migrate_registry.py`
- [x] 2.3 Run `migrate_registry.py`; verify `metadata/registry.db` has populated `functions` + `function_columns` tables

## 3. CLI

- [x] 3.1 Create `cli_anything/yfinance/yfinance_cli.py` by adapting `akshare_cli.py`: Click group with default→REPL, subcommands `search`, `info`, `list`, `categories`, `call`; `--json` flag; omit the `proxy` subcommand group
- [x] 3.2 Adapt REPL (`repl`, `_repl_help`, `_repl_execute`, `_simple_repl` fallback) — commands `list`/`search`/`info`/`categories`/`call`/`exit`/`help`
- [x] 3.3 Implement `call` to parse `k=v` args and invoke `core.runner.call_yfinance_function`, formatting output via `utils.output`

## 4. Runner

- [x] 4.1 Implement `core/runner.py` `call_yfinance_function(func_name, params=None)`: dispatch `ticker_*` via `yf.Ticker(params["symbol"]).<suffix>(**rest)`, dispatch top-level via `yf.<name>(**params)`; handle `ImportError` (clear message + install hint), unknown command (list available), `TypeError` (print expected signature), generic `Exception`

## 5. Tests

- [x] 5.1 Create `cli_anything/yfinance/tests/test_core.py` — registry query tests (search/info/list/categories) against the seeded SQLite DB
- [x] 5.2 Create `tests/test_full_e2e.py` — CLI E2E via `_resolve_cli("cli-anything-yfinance")` fallback to `python -m`, gated with `@pytest.mark.skipif` on `yfinance` import
- [x] 5.3 Run `uv run pytest -v` from `yfinance-agent-harness/`; confirm registry tests pass and live tests skip when yfinance absent

## 6. MCP server

- [x] 6.1 Create `mcp/yfinance-mcp/` with `pyproject.toml` (deps `fastmcp>=2.0`, `yfinance`, `pandas>=1.0`, `sqlalchemy>=1.4`, `click>=8.0`, `requires-python>=3.10`), `.env`, `.env.example` (`YFINANCE_DATABASE_URL`)
- [x] 6.2 Create `mcp/yfinance-mcp/server.py` by adapting `akshare-mcp/server.py`: same five tools, dotenv root-then-local `override=True`, harness-root on `sys.path`; `call_yfinance_function` uses the `ticker_*` vs top-level dispatch; reuse `_serialize_result`
- [x] 6.3 `uv sync` in `mcp/yfinance-mcp/`; smoke-test `call_yfinance_function(name="ticker_history", params_json='{"symbol":"AAPL","period":"1mo"}')` returns a dataframe result (skip-note if Yahoo unreachable)

## 7. Registration & docs

- [x] 7.1 Add `yfinance-mcp` entry to root `.mcp.json` using `uv run --directory /Users/chengsishi/code/cli-anything/mcp/yfinance-mcp python server.py`
- [x] 7.2 Add a `skills/cli-anything-yfinance/SKILL.md` (canonical) and `cli_anything/yfinance/skills/SKILL.md` (compat copy), mirroring the akshare skill files
- [x] 7.3 Update root `CLAUDE.md` "MCP Servers" and "akshare-agent-harness" sections to mention the yfinance harness + `yfinance-mcp` server
