---
name: "cli-anything-akshare"
description: "Command-line interface for AKShare Chinese financial data library — stocks, funds, futures, macro, bonds, and more."
---

# cli-anything-akshare

A CLI for querying Chinese financial data via [AKShare](https://github.com/akfamily/akshare).

## Prerequisites

- Python 3.10+
- `pip install akshare`

## Installation

```bash
pip install cli-anything-akshare
```

## Quick Start

```bash
# List all available functions
cli-anything-akshare list

# Search for functions by keyword
cli-anything-akshare search 历史行情

# Get function details including parameters
cli-anything-akshare info stock_zh_a_hist

# Call a function (REPL style)
cli-anything-akshare

# Call a function (one-shot)
cli-anything-akshare call stock_zh_a_hist symbol=000001 start_date=20250101

# JSON output for machine consumption
cli-anything-akshare --json list
```

## Command Groups

| Command | Description |
|---------|-------------|
| `list [--category CAT]` | List all 673 functions, optionally filtered by category |
| `search <query>` | Search functions by name, category, or description |
| `info <function>` | Show parameter schema and output columns |
| `call <function> [key=value ...]` | Execute any AKShare function |
| `categories` | List all 430 data categories with function counts |

## Calling Functions

Use the `call` command with `key=value` pairs:

```bash
# Historical stock data
cli-anything-akshare call stock_zh_a_hist symbol=000001 start_date=20240101 end_date=20240601

# Real-time stock quote
cli-anything-akshare call stock_zh_a_spot_em symbol=000001

# Market overview
cli-anything-akshare call stock_sse_summary date=20250601

# Fund data
cli-anything-akshare call fund_etf_hist_em symbol=510050

# Futures data
cli-anything-akshare call futures_zh_minute_sina symbol=IF0
```

## JSON Output

All commands support `--json` for machine parsing:

```bash
cli-anything-akshare --json call stock_sse_summary
cli-anything-akshare --json search 龙虎榜
```

## Agent Guidance

When using this CLI as an AI agent:

1. **Discover**: Start with `list` or `search` to find the right function
2. **Inspect**: Use `info <function>` to see required parameters and output schema
3. **Execute**: Use `call <function> key=value ...` to get data
4. **Parse**: Use `--json` flag for structured output

Common parameter types:
- `symbol`: Stock/fund/futures code (string)
- `start_date`/`end_date`: Date in YYYYMMDD format (string)
- `period`: Time period like "daily", "weekly", "monthly" (string)
- `timeout`: HTTP timeout in seconds (string)
- `token`: API token if required (string)

Parameters are passed as `key=value` pairs separated by spaces. Optional parameters can be omitted.
