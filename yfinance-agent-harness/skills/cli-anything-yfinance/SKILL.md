---
name: "cli-anything-yfinance"
description: "Command-line interface for yfinance (Yahoo Finance) global / US-market data — price history, fundamentals, holders, options, calendar."
---

# cli-anything-yfinance

A CLI for querying global / US-market financial data via [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance).

## Prerequisites

- Python 3.10+
- `pip install yfinance`

## Installation

```bash
# from yfinance-agent-harness/
uv pip install -e ".[dev,repl]"
```

## Quick Start

```bash
# List all available functions
cli-anything-yfinance list

# Search for functions by keyword
cli-anything-yfinance search history

# Get function details including parameters
cli-anything-yfinance info ticker_history

# Call a function (REPL style)
cli-anything-yfinance

# Call a function (one-shot)
cli-anything-yfinance call ticker_history symbol=AAPL period=1mo

# JSON output for machine consumption
cli-anything-yfinance list --json
```

## Command Groups

| Command | Description |
|---------|-------------|
| `list [--category CAT]` | List all functions, optionally filtered by category |
| `search <query>` | Search functions by name, category, or description |
| `info <function>` | Show parameter schema and output columns |
| `call <function> [key=value ...]` | Execute any yfinance function |
| `categories` | List all categories with function counts |

## Command Convention

yfinance centers on the `Ticker` object. This CLI flattens it into a registry of commands:

- `ticker_<method>` — calls `yfinance.Ticker(symbol).<method>(...)`
- top-level functions keep their names (e.g. `download`, `search`)

## Calling Functions

Use the `call` command with `key=value` pairs:

```bash
# Historical OHLCV
cli-anything-yfinance call ticker_history symbol=AAPL period=1mo

# Summary info dict
cli-anything-yfinance call ticker_info symbol=MSFT

# Annual income statement
cli-anything-yfinance call ticker_financials symbol=AAPL

# Option chain for an expiry
cli-anything-yfinance call ticker_option_chain symbol=AAPL expiration=2025-12-19

# Download many symbols
cli-anything-yfinance call download tickers=AAPL,MSFT period=1mo

# Search Yahoo Finance for a ticker
cli-anything-yfinance call search query=Apple
```

## JSON Output

Commands support `--json` (place it after the subcommand) for machine parsing:

```bash
cli-anything-yfinance list --json
cli-anything-yfinance call ticker_history symbol=AAPL period=1mo --json
```

## Agent Guidance

When using this CLI as an AI agent:

1. **Discover**: Start with `list` or `search` to find the right function
2. **Inspect**: Use `info <function>` to see required parameters and output schema
3. **Execute**: Use `call <function> key=value ...` to get data
4. **Parse**: Use the `--json` flag for structured output

Common parameter types:
- `symbol`: Ticker symbol, e.g. `AAPL`, `MSFT`, `600519.SS` (string)
- `period`: `1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max` (string)
- `interval`: `1m,5m,15m,1h,1d,1wk,1mo` (string)
- `start`/`end`: Date in `YYYY-MM-DD` format (string)

For `ticker_*` commands, `symbol` is always required and selects the Ticker; the
remaining params are passed to the Ticker method. Parameters are passed as
`key=value` pairs separated by spaces; optional parameters can be omitted.

Note: Yahoo may rate-limit heavy automated use; yfinance retries/caches internally.
