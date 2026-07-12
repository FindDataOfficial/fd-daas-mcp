"""
Curated registry of yfinance callables.

Source of truth for the yfinance registry DB. yfinance's API is small and
stable enough to hand-curate (unlike akshare, which scrapes ~673 functions).

Convention:
  - ticker_<method>:  yfinance.Ticker(symbol).<method>(**rest)
  - everything else:   yfinance.<name>(**params)

# ponytail: output columns are representative, not exhaustive — yfinance
# returns wide / sometimes nested DataFrames; we record the key columns only.
"""
from __future__ import annotations

YFINANCE_SOURCE = "https://github.com/ranaroussi/yfinance"

# Shared parameter for all ticker_* commands
_SYMBOL_PARAM = {"name": "symbol", "type": "str", "required": True,
                 "description": "Ticker symbol, e.g. 'AAPL', 'MSFT', '600519.SS'"}

REGISTRY: dict[str, dict] = {
    # ── price-history ────────────────────────────────────────────────
    "ticker_history": {
        "category": "price-history",
        "description": "Historical OHLCV price history for a symbol",
        "source": YFINANCE_SOURCE,
        "parameters": [
            _SYMBOL_PARAM,
            {"name": "period", "type": "str", "required": False,
             "description": "1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max (default 1mo)"},
            {"name": "interval", "type": "str", "required": False,
             "description": "1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo (default 1d)"},
            {"name": "start", "type": "str", "required": False, "description": "Start date YYYY-MM-DD"},
            {"name": "end", "type": "str", "required": False, "description": "End date YYYY-MM-DD"},
        ],
        "columns": [
            {"name": "Open", "type": "float"},
            {"name": "High", "type": "float"},
            {"name": "Low", "type": "float"},
            {"name": "Close", "type": "float"},
            {"name": "Volume", "type": "int"},
            {"name": "Dividends", "type": "float"},
            {"name": "Stock Splits", "type": "float"},
        ],
    },
    "ticker_dividends": {
        "category": "price-history",
        "description": "Dividend history for a symbol",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [
            {"name": "Date", "type": "str"},
            {"name": "Dividends", "type": "float"},
        ],
    },
    "ticker_splits": {
        "category": "price-history",
        "description": "Stock split history for a symbol",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [
            {"name": "Date", "type": "str"},
            {"name": "Stock Splits", "type": "float"},
        ],
    },
    "download": {
        "category": "price-history",
        "description": "Download historical market data for one or many symbols (top-level)",
        "source": YFINANCE_SOURCE,
        "parameters": [
            {"name": "tickers", "type": "str", "required": True,
             "description": "Symbol or list of symbols, e.g. 'AAPL' or ['AAPL','MSFT']"},
            {"name": "period", "type": "str", "required": False, "description": "1d,5d,1mo,...,max"},
            {"name": "interval", "type": "str", "required": False, "description": "1m,...,3mo"},
            {"name": "start", "type": "str", "required": False, "description": "Start date YYYY-MM-DD"},
            {"name": "end", "type": "str", "required": False, "description": "End date YYYY-MM-DD"},
        ],
        "columns": [
            {"name": "Open", "type": "float"},
            {"name": "High", "type": "float"},
            {"name": "Low", "type": "float"},
            {"name": "Close", "type": "float"},
            {"name": "Volume", "type": "int"},
        ],
    },

    # ── fundamentals ─────────────────────────────────────────────────
    "ticker_info": {
        "category": "fundamentals",
        "description": "Summary info dict for a symbol (price, sector, market cap, etc.)",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [],
    },
    "ticker_financials": {
        "category": "fundamentals",
        "description": "Annual income statement (DataFrame)",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [
            {"name": "Total Revenue", "type": "float"},
            {"name": "Net Income", "type": "float"},
        ],
    },
    "ticker_balance_sheet": {
        "category": "fundamentals",
        "description": "Annual balance sheet (DataFrame)",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [
            {"name": "Total Assets", "type": "float"},
            {"name": "Total Liab", "type": "float"},
        ],
    },
    "ticker_cashflow": {
        "category": "fundamentals",
        "description": "Annual cash flow statement (DataFrame)",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [
            {"name": "Operating Cash Flow", "type": "float"},
            {"name": "Free Cash Flow", "type": "float"},
        ],
    },

    # ── holders ──────────────────────────────────────────────────────
    "ticker_holders": {
        "category": "holders",
        "description": "Major holders of a symbol (DataFrame)",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [
            {"name": "5", "type": "str"},
            {"name": "Date Reported", "type": "str"},
        ],
    },

    # ── options ──────────────────────────────────────────────────────
    "ticker_option_chain": {
        "category": "options",
        "description": "Option chain for a given expiry (calls + puts DataFrames)",
        "source": YFINANCE_SOURCE,
        "parameters": [
            _SYMBOL_PARAM,
            {"name": "expiration", "type": "str", "required": False,
             "description": "Expiry date; if omitted, uses the nearest"},
        ],
        "columns": [
            {"name": "strike", "type": "float"},
            {"name": "lastPrice", "type": "float"},
            {"name": "volume", "type": "int"},
        ],
    },

    # ── calendar ─────────────────────────────────────────────────────
    "ticker_calendar": {
        "category": "calendar",
        "description": "Earnings calendar / next event for a symbol (dict)",
        "source": YFINANCE_SOURCE,
        "parameters": [_SYMBOL_PARAM],
        "columns": [],
    },

    # ── search (top-level) ───────────────────────────────────────────
    "search": {
        "category": "search",
        "description": "Search Yahoo Finance for matching tickers (top-level)",
        "source": YFINANCE_SOURCE,
        "parameters": [
            {"name": "query", "type": "str", "required": True, "description": "Search text"},
            {"name": "max_results", "type": "int", "required": False, "description": "Max results (default 8)"},
        ],
        "columns": [
            {"name": "symbol", "type": "str"},
            {"name": "shortname", "type": "str"},
            {"name": "exchange", "type": "str"},
        ],
    },
}
