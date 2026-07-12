---
name: "cli-anything-daas"
description: "Multi-source data access CLI — AKShare, World Bank, CKAN, Chinese National Statistics"
---

# cli-anything-daas

A CLI for discovering and fetching data from multiple open data sources.

## Prerequisites

- Python 3.10+
- `pip install cli-anything-daas`

## Installation

```bash
pip install cli-anything-daas

# Install optional source dependencies (pick what you need)
pip install akshare         # AKShare Chinese financial data
pip install wbgapi          # World Bank Open Data
pip install ckanapi         # CKAN open data portals
```

## Quick Start

```bash
# List all available data sources
cli-anything-daas list-sources

# Search for functions across all sources
cli-anything-daas search GDP
cli-anything-daas search 股票

# Get function details including parameters
cli-anything-daas describe worldbank_gdp

# Call a function
cli-anything-daas call worldbank_gdp country=CN time=2020:2023
cli-anything-daas call akshare_stock_zh_a_hist symbol=000001 period=daily

# JSON output for machine consumption
cli-anything-daas --json search inflation

# REPL mode
cli-anything-daas
```

## Command Groups

| Command | Description |
|---------|-------------|
| `list-sources` | List all configured data sources with install status |
| `search <query> [--source SRC]` | Search functions across all sources |
| `categories [--source SRC]` | List all categories with function counts |
| `describe <function>` | Show parameter schema and output columns |
| `call <function> [key=value ...]` | Execute any data function |
| `help` | Show help |

## Data Sources

| Source | Prefix | Description | Package |
|--------|--------|-------------|---------|
| AKShare | `akshare_` | Chinese financial data (673+ functions) | `akshare` |
| World Bank | `worldbank_` | Global development indicators (20 key indicators) | `wbgapi` |
| CKAN | `ckan_` | Open data portals (data.gov, etc.) | `ckanapi` |
| Chinese Stats | `cnstats_` | NBS macro indicators (CPI, PMI, GDP) | `akshare` |

## Calling Functions

Functions use `source_functionname` naming. Parameters are `key=value` pairs:

```bash
# World Bank GDP data
cli-anything-daas call worldbank_ny_gdp_mktp_cd country=CHN time=2020:2023

# CKAN dataset search
cli-anything-daas call ckan_package_search q=climate rows=5

# Chinese CPI data
cli-anything-daas call cnstats_cpi
```

## JSON Output

All commands support `--json` for machine parsing:

```bash
cli-anything-daas --json search GDP
cli-anything-daas --json call worldbank_ny_gdp_mktp_cd country=CHN
```

## Agent Guidance

When using this CLI as an AI agent:

1. **Discover**: Start with `list-sources` to see what's available and installed
2. **Search**: Use `search <query>` to find relevant functions across all sources
3. **Inspect**: Use `describe <function>` to see required parameters and output schema
4. **Execute**: Use `call <function> key=value ...` to get data
5. **Parse**: Use `--json` flag for structured output

Functions are namespaced by source prefix. Use the prefix to avoid ambiguity:
- `akshare_*` — Chinese stocks, funds, futures, macro
- `worldbank_*` — Global development indicators
- `ckan_*` — Open data portal search and retrieval
- `cnstats_*` — Chinese NBS macro indicators

Common parameter types:
- `country`: ISO 3-letter code (e.g., CHN, USA) or 'all'
- `time`: Year or range (e.g., 2020 or 2015:2023)
- `q`: Search query string
- `rows`: Maximum results
- `symbol`: Stock/fund/futures code
