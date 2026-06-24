# AKShare — Agent-Specific Analysis

## Overview

AKShare is an open-source Python library for Chinese financial data, providing HTTP-request-based access to ~1,100+ functions across stocks, funds, futures, bonds, options, macroeconomics, forex, and more.

Key characteristics:
- **Backend**: Pure Python HTTP library (requests-based). No GUI, no external process.
- **Data model**: Functions return `pandas.DataFrame` objects (tabular data). No project files.
- **API pattern**: Each function is a stateless HTTP call returning fresh data. No state between calls.
- **Categories**: ~430 categories organized by Chinese financial domain names.
- **Function naming**: Prefix-based convention (`stock_zh_a_hist`, `fund_etf_hist_em`, `futures_zh_minute_sina`).

## CLI Adaptation

Since AKShare is a Python library (not a GUI app), the standard CLI-Anything "backend integration" pattern is simplified:

1. **No project files to manipulate** — AKShare functions are stateless queries.
2. **No external software to invoke** — AKShare IS the backend, called via `import akshare`.
3. **No rendering/export pipeline** — Results are DataFrames, printed as tables or JSON.
4. **No state persistence** — Each call is independent.

## Command Groups

All 673 registered functions are accessible via a unified `call` command. Helper commands provide discovery:

| Command | Purpose |
|---------|---------|
| `call <func> [k=v ...]` | Execute any akshare function with key=value parameters |
| `list` | List all registered functions |
| `search <query>` | Search functions by name, category, or description |
| `info <func>` | Show parameter details and output schema for a function |
| `categories` | List all 430 categories with function counts |
| `repl` | Interactive REPL mode (default) |

## Output Format

All commands support `--json` flag for machine-readable output. Default output is human-readable:
- DataFrames → formatted tables via pandas `to_string()`
- Dicts/lists → JSON
- Scalars → str()

## Key Functions (most commonly used)

| Function | Category | Parameters |
|----------|----------|------------|
| `stock_zh_a_hist` | 历史行情数据 | symbol, start_date, end_date |
| `stock_zh_a_spot_em` | 实时行情数据 | symbol (optional) |
| `stock_individual_info_em` | 个股信息查询 | symbol |
| `fund_etf_hist_em` | ETF基金历史 | symbol, period |
| `futures_zh_minute_sina` | 期货分时 | symbol, period |
