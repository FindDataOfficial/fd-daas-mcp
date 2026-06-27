# Research: DAAS Provider

## 1. World Bank API

**Decision**: Use `wbgapi` package (already well-maintained, pandas-native output).

**Rationale**: `wbgapi` wraps the World Bank API v2 and returns pandas DataFrames directly. It handles indicator codes, country codes, pagination, and date ranges. The alternative — raw `requests` to `api.worldbank.org` — would require reimplementing all of this.

**Alternatives considered**:
- Raw `requests` — too much boilerplate (indicator lookup, pagination, format parsing)
- `pandas-datareader` — deprecated World Bank support, no longer maintained

**Key indicators**: GDP (`NY.GDP.MKTP.CD`), population (`SP.POP.TOTL`), trade, education, health — 1,400+ indicators available.

## 2. CKAN API

**Decision**: Use `ckanapi` package with configurable portal URLs.

**Rationale**: CKAN is a standard open data portal API used by `data.gov`, `data.gov.uk`, and many others. `ckanapi` provides a clean Python wrapper. We'll support configurable portal URLs so users can point at any CKAN instance.

**Alternatives considered**:
- Raw requests — CKAN API is simple REST, but `ckanapi` handles auth, pagination, and result parsing
- Hardcoding a single portal — defeats the purpose of CKAN's federated model

**Default portals**: `https://data.gov/api/3/` (US), `https://data.gov.uk/api/3/` (UK)

## 3. Chinese National Statistics

**Decision**: Lean on `akshare` for Chinese data; add `cnstats` adapter for National Bureau of Statistics direct queries.

**Rationale**: `akshare` already covers 673+ Chinese financial data functions. The `cnstats` source adds direct queries to the National Bureau of Statistics (NBS) API for macro indicators not covered by akshare: CPI, PMI, industrial output, fixed asset investment, retail sales.

**Alternatives considered**:
- `akshare` only — misses some macro indicators
- Custom scraper — maintenance burden, NBS changes their site frequently

## 4. Registry DB Schema

**Decision**: Extend `leader_mcp.db` with a `daas_functions` and `daas_columns` table; also maintain a standalone `daas_registry.db` for the daas-mcp server.

**Rationale**: Follow the existing pattern — `leader_mcp.db` has a `functions` table (harness, command, category, source, description, parameters as JSON) and `function_columns` table. DAAS adds its own tables in the same DB for unified queries, plus a standalone DB for when daas-mcp runs independently.

**Alternatives considered**:
- Single unified schema — too coupled, harder to run daas-mcp standalone
- JSON file only — no query capability, leader-mcp integration needs SQL

## 5. Source Adapter Pattern

**Decision**: Single `SourceAdapter` abstract base class with `discover()`, `fetch()`, `columns()` methods.

**Rationale**: One base class, not a factory. Each source implements three methods:
- `discover() -> list[dict]` — returns available functions for this source
- `fetch(function_name, **params) -> pd.DataFrame` — executes a function
- `columns(function_name) -> list[dict]` — returns column metadata

**Alternatives considered**:
- Per-source factory — overkill, 4 sources don't need a factory
- Plugin system — YAGNI, add when sources exceed ~10

## 6. yfinance (Yahoo Finance)

**Decision**: Use `yfinance` package, wrap with a `YFinanceAdapter` that follows the existing `SourceAdapter` interface.

**Rationale**: yfinance is the de-facto Python library for Yahoo Finance data (stocks, ETFs, indices, crypto, currencies). It wraps Yahoo's reverse-engineered API and returns pandas DataFrames natively. Unlike AKShare (which has a function registry), yfinance is object-oriented (Ticker + methods). The adapter translates this into the DAAS function-call pattern by mapping ~16 Ticker methods to namespaced function names (`yfinance_info`, `yfinance_history`, etc.).

**yfinance API surface**:

| Method | DAAS Function | Returns |
|--------|--------------|---------|
| `yf.download()` | `yfinance_download` | DataFrame (OHLCV) |
| `Ticker.history()` | `yfinance_history` | DataFrame (OHLCV) |
| `Ticker.info` | `yfinance_info` | dict (company profile) |
| `Ticker.financials` | `yfinance_financials` | DataFrame |
| `Ticker.balance_sheet` | `yfinance_balance_sheet` | DataFrame |
| `Ticker.cashflow` | `yfinance_cashflow` | DataFrame |
| `Ticker.earnings` | `yfinance_earnings` | DataFrame |
| `Ticker.recommendations` | `yfinance_recommendations` | DataFrame |
| `Ticker.sustainability` | `yfinance_sustainability` | DataFrame (ESG) |
| `Ticker.major_holders` | `yfinance_holders` | DataFrame |
| `Ticker.actions` | `yfinance_actions` | DataFrame (dividends+splits) |
| `Ticker.news` | `yfinance_news` | list[dict] |
| `Ticker.calendar` | `yfinance_calendar` | dict |
| `Ticker.analyst_price_targets` | `yfinance_analyst_price_targets` | DataFrame |
| `Ticker.options` | `yfinance_options` | list[str] |
| `yf.Search()` | `yfinance_search` | dict (quotes+news) |

**Alternatives considered**:
- Raw requests — Yahoo has no public API; yfinance handles the reverse-engineered endpoints
- `pandas-datareader` — deprecated Yahoo support, yfinance is the maintained successor
- `yfinance-mcp` (existing MCP server) — could reuse, but it has a different tool shape; building our own keeps the pattern consistent

**MCP server**: Standalone `mcp/yfinance-mcp/` (mirrors `mcp/akshare-mcp/` exactly) — 5 tools: search, get_function_info, list_categories, list_functions, call_yfinance_function.

**Registry integration**: Functions are hardcoded in the adapter (like worldbank), no live discovery needed. `store_registry.py` auto-discovers them via the adapter.

## 7. Registry Storage Script

**Decision**: `store_registry.py` script that calls `discover()` on all sources, builds the registry, and writes to both JSON and SQLite.

**Rationale**: Simple script, not a service. Runs on demand (or via cron-mcp schedule) to refresh the registry. JSON is the canonical format (portable, diffable). SQLite is the query format (fast, integrated with leader-mcp).
