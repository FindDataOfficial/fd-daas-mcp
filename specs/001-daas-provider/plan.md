# Implementation Plan: DAAS Provider (updated — yfinance)

## Technical Context

- **Language/Version**: Python >=3.10
- **Primary Dependencies**: click, pandas, akshare, yfinance, wbgapi, ckanapi, requests, sqlalchemy, fastmcp
- **Storage**: SQLite (`mcp/daas.db`, `mcp/daas_registry.db`), plus registry JSON
- **Testing**: pytest (`@pytest.mark.skipif` for optional deps)
- **Target Platform**: macOS/Linux CLI, MCP stdio transport
- **Project Type**: multi-package monorepo (daas-agent-harness + per-source MCP servers + leader-mcp)
- **Performance Goals**: function discovery <100ms, data fetch varies by source (5-30s typical)
- **Constraints**: must follow existing harness pattern (PEP 420 namespace `cli_anything/daas/`), must integrate with leader-mcp unified registry
- **Scale/Scope**: 5 data sources (akshare, yfinance, world bank, ckan, chinese statistics), extensible for more

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Follows existing harness pattern | ✅ PASS | Mirrors `akshare-agent-harness/` and existing daas adapters |
| PEP 420 namespace package | ✅ PASS | `cli_anything/daas/` (no `__init__.py`) |
| uv for dependency management | ✅ PASS | `uv sync`, `uv run` |
| MCP stdio transport | ✅ PASS | FastMCP server in `mcp/yfinance-mcp/`, mirrors `mcp/akshare-mcp/` |
| SQLite for persistence | ✅ PASS | Extends `mcp/daas.db` with yfinance functions |
| Tests with pytest | ✅ PASS | Unit + E2E CLI tests |
| No modifications to CLI-Anything/ | ✅ PASS | Custom work in `daas-agent-harness/` and `mcp/yfinance-mcp/` |

## Project Structure (new additions highlighted)

```
daas-agent-harness/
├── cli_anything/
│   └── daas/
│       ├── cli.py
│       ├── sources/
│       │   ├── akshare_source.py
│       │   ├── yfinance_source.py     # NEW — Yahoo Finance adapter
│       │   ├── worldbank_source.py
│       │   ├── ckan_source.py
│       │   ├── cnstats_source.py
│       │   ├── config.py              # UPDATED — add yfinance to DEFAULT_SOURCES + get_adapter()
│       │   ├── router.py              # UPDATED — add yfinance_ to SOURCE_PREFIXES
│       │   └── base.py
│       └── scripts/
│           └── store_registry.py      # (unchanged, auto-discovers new adapter)
├── skills/
│   └── cli-anything-daas/
│       └── SKILL.md                   # UPDATED — add yfinance to source list
└── tests/
    └── test_sources.py                # UPDATED — add yfinance adapter tests

mcp/yfinance-mcp/                      # NEW — standalone Yahoo Finance MCP server
├── server.py                          # FastMCP entry point (5 tools, mirrors akshare-mcp)
├── pyproject.toml
└── .env.example

mcp/daas-mcp/                          # UPDATED — adds yfinance to unified server
│   ├── server.py
│   ├── daas_tools.py
│   └── sources/
```

## Phase 0: Research

### New Research: yfinance

**Decision**: Use `yfinance` package directly (mirrors how AKShare adapter wraps `akshare`).

**Rationale**: yfinance is the de-facto Python library for Yahoo Finance data. It wraps Yahoo's API and returns pandas DataFrames natively. The adapter translates yfinance's Ticker-method pattern into the DAAS function-call pattern.

**yfinance API surface mapped to DAAS functions**:

| DAAS Function | yfinance API | Returns |
|---|---|---|
| `yfinance_download` | `yf.download()` | DataFrame (OHLCV history) |
| `yfinance_history` | `Ticker.history()` | DataFrame (OHLCV history) |
| `yfinance_info` | `Ticker.info` | dict (company profile) |
| `yfinance_financials` | `Ticker.financials` | DataFrame (income statement) |
| `yfinance_balance_sheet` | `Ticker.balance_sheet` | DataFrame |
| `yfinance_cashflow` | `Ticker.cashflow` | DataFrame |
| `yfinance_earnings` | `Ticker.earnings` | DataFrame |
| `yfinance_recommendations` | `Ticker.recommendations` | DataFrame |
| `yfinance_sustainability` | `Ticker.sustainability` | DataFrame (ESG) |
| `yfinance_holders` | `Ticker.major_holders` + `.institutional_holders` | DataFrame |
| `yfinance_actions` | `Ticker.actions` | DataFrame (dividends + splits) |
| `yfinance_news` | `Ticker.news` | list[dict] |
| `yfinance_calendar` | `Ticker.calendar` | dict |
| `yfinance_analyst_price_targets` | `Ticker.analyst_price_targets` | DataFrame |
| `yfinance_options` | `Ticker.options` | list[str] (expiry dates) |
| `yfinance_search` | `yf.Search()` | dict (quotes + news) |

**Alternatives considered**:
- Raw requests to Yahoo Finance API — brittle, Yahoo has no public API, yfinance handles the reverse-engineered endpoints
- `pandas-datareader` — deprecated Yahoo support, yfinance is the maintained successor

**Dependency**: `yfinance>=0.2.0`, install via `pip install yfinance`.

## Phase 1: Design

### yfinance Adapter Design

Follows the exact `SourceAdapter` interface. Key decisions:

1. **`discover()`**: Returns ~16 curated yfinance functions (hardcoded, like worldbank). yfinance has no registry — its API is a set of Ticker methods, not standalone functions.
2. **`fetch()`**: Routes function name to the appropriate yfinance API call. The `symbol` parameter is required for all Ticker-based functions; `yfinance_download` accepts `tickers` (space-separated).
3. **`columns()`**: Returns column metadata for each function (hardcoded, matches known yfinance output schemas).
4. **Namespace prefix**: `yfinance_` — all functions are prefixed (e.g., `yfinance_info`, `yfinance_history`).

### yfinance MCP Server Design

Mirrors `mcp/akshare-mcp/server.py` exactly:

- **Tools**: `search_functions`, `get_function_info`, `list_categories`, `list_functions`, `call_yfinance_function`
- **Entry**: `python3 server.py` (FastMCP, stdio transport)
- **Dependencies**: `yfinance`, `pandas`, `fastmcp`
- **No separate DB**: The MCP server calls yfinance directly, no registry DB needed (functions are hardcoded in the adapter). The daas registry DB stores metadata for leader-mcp integration.

### Files to Create

1. `daas-agent-harness/cli_anything/daas/sources/yfinance_source.py` — YFinanceAdapter
2. `mcp/yfinance-mcp/server.py` — standalone MCP server
3. `mcp/yfinance-mcp/pyproject.toml` — project config
4. `mcp/yfinance-mcp/.env.example` — env template

### Files to Modify

1. `daas-agent-harness/cli_anything/daas/sources/config.py` — add yfinance to DEFAULT_SOURCES and get_adapter()
2. `daas-agent-harness/cli_anything/daas/sources/router.py` — add `yfinance_` to SOURCE_PREFIXES
3. `daas-agent-harness/skills/cli-anything-daas/SKILL.md` — add yfinance to source list

## Constitution Re-Check (Post-Design)

| Gate | Status | Notes |
|------|--------|-------|
| No unnecessary abstraction | ✅ PASS | Single adapter class, no factory, no plugin system |
| Stdlib where possible | ✅ PASS | yfinance handles all Yahoo API complexity |
| Follows existing patterns | ✅ PASS | Mirrors AKShare adapter + akshare-mcp patterns exactly |
| Tests cover core paths | ✅ PASS | Adapter discover/fetch/columns + MCP tool smoke tests |

## Complexity Tracking

None — the yfinance addition follows existing patterns exactly. No new abstractions.
