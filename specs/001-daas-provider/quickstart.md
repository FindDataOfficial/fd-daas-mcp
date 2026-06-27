# Quickstart: DAAS Provider

## Prerequisites

- Python >=3.10
- uv

## Setup

```bash
# Clone and install
cd daas-agent-harness
uv sync
uv pip install -e ".[dev,repl]"

# Install optional source deps (pick what you need)
uv pip install akshare wbgapi ckanapi
```

## Validation Scenarios

### 1. CLI: List available sources

```bash
uv run cli-anything-daas list-sources
```

**Expected**: Table of 5 sources (akshare, yfinance, worldbank, ckan, cnstats) with enabled status.

### 2. CLI: Search for functions

```bash
uv run cli-anything-daas search GDP
uv run cli-anything-daas search 股票
```

**Expected**: Matching functions across sources, with source, category, description.

### 3. CLI: Yahoo Finance functions

```bash
uv run cli-anything-daas call yfinance_info symbol=AAPL
uv run cli-anything-daas call yfinance_history symbol=MSFT period=1mo
uv run cli-anything-daas --json call yfinance_download tickers=AAPL period=1mo
```

**Expected**: Company info dict, OHLCV DataFrame, or download DataFrame. Works without API key.

### 4. CLI: Call a function (other sources)

```bash
uv run cli-anything-daas call worldbank_gdp country=CN date=2020:2023
uv run cli-anything-daas --json call stock_zh_a_hist symbol=000001 period=monthly
```

**Expected**: Pandas DataFrame output (table or JSON depending on flag).

### 4. CLI: REPL mode

```bash
uv run cli-anything-daas
# > search GDP
# > call worldbank_gdp country=CN date=2020:2023
# > help
# > exit
```

**Expected**: Interactive REPL with search, call, help, exit commands.

### 5. Store registry

```bash
uv run python cli_anything/daas/scripts/store_registry.py
```

**Expected**: `registry.json` and `daas_registry.db` populated with discovered functions and columns.

### 5. Standalone MCP servers (yfinance, ckan, cnstats, worldbank)

```bash
cd mcp/yfinance-mcp && uv run python server.py    # Yahoo Finance: 16 functions
cd mcp/ckan-mcp && uv run python server.py         # CKAN: 5 functions
cd mcp/cnstats-mcp && uv run python server.py      # CNStats: 8 functions
cd mcp/worldbank-mcp && uv run python server.py    # World Bank: 20 functions
```

**Expected**: Each MCP stdio server starts, responds to `list_tools` with 5 tools: `search_functions`, `get_function_info`, `list_categories`, `list_functions`, `call_*_function`.

### 7. Populate daas.db

```bash
cd mcp && uv run python populate_daas.py
```

**Expected**: 33 functions and 132 columns committed across ckan (5), cnstats (8), worldbank (20).

### 8. Unified MCP server

```bash
cd mcp/daas-mcp
uv run python server.py
```

**Expected**: MCP stdio server starts, responds to `list_tools` with `search_functions`, `get_function_detail`, `fetch_data`, `list_sources`.

### 7. Run tests

```bash
cd daas-agent-harness
uv run pytest -v
```

**Expected**: All tests pass (skipped tests for sources without their deps installed).

## Skill Usage

```
/cli-anything-daas search GDP
/cli-anything-daas call worldbank_gdp country=CN
```
