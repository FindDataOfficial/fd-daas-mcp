# cli-anything-yfinance

A CLI for querying global / US-market financial data via [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance).

Part of the cli-anything fork. Mirrors the `cli-anything-akshare` harness layout.

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

# Call a function (one-shot)
cli-anything-yfinance call ticker_history symbol=AAPL period=1mo

# JSON output for machine consumption
cli-anything-yfinance --json call ticker_history symbol=AAPL period=1mo

# Interactive REPL (default when no subcommand given)
cli-anything-yfinance
```

## Command conventions

yfinance centers on the `Ticker` object. This harness flattens it into a registry of commands:

- `ticker_<method>` — calls `yfinance.Ticker(symbol).<method>(...)`, e.g. `ticker_history`, `ticker_info`, `ticker_financials`.
- Top-level functions keep their names, e.g. `download`, `search`.

## Notes

- Yahoo may rate-limit heavy automated use; yfinance retries/caches internally.
- Output-column metadata in the registry is representative, not exhaustive.
