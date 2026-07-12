"""Seed Massive.com REST endpoints as daas_functions + columns + indicator_rules.

The `massive` source, its `default` form, and its three composable-tool sections
(`Search-Endpoints`, `Call-API`, `Query-Data`) are created by
`seed_external_mcps.py`. This seeder adds the per-endpoint layer underneath that
source:

  - `daas_functions` — one row per Massive.com REST endpoint (~37), organized
    by asset-class `category` (Reference / Stocks / Options / Crypto / Forex /
    Futures / Indices / Economy / Alternative).
  - `daas_function_columns` — the response columns for each endpoint, sampled
    once via `search_endpoints` / `call_api` and hard-coded here.
  - `indicator_rules` — math indicators (sma / ema / pct_change / zscore /
    rolling_std / level) over the Economy time-series endpoints (Treasury
    yields, inflation, inflation expectations, labor market), pointing at
    `scraw_massive_<slug>` tables populated by `backfill_massive.py`.

Idempotent: re-runnable on the live `daas.db`. `--dry-run` plans; `--unseed`
removes only the rows this seeder owns (the `daas_functions` + their cascade
columns + the `indicator_rules` it created under `massive`). The `massive`
source, its `default` form, its 3 sections, and its `core` collection item
(owned by `seed_external_mcps.py`) are never touched.

No network at seed time — all endpoint/column metadata is hard-coded constants.
Runs in the daas-mcp venv with no sibling-MCP imports (no `massive`/`fastmcp`),
mirroring `seed_external_mcps.py`.

Entitlement caveat: 12 endpoints return HTTP 403 on the current Massive.com
plan (real-time crypto/forex/indices, options last-trade, forex conversion,
futures snapshot/quotes/trades, alt merchant data). They are registered as
metadata (`parameters.gated=true`) so agents discover them, but are not
backfilled and have no indicators. All 4 Economy endpoints work.

Usage:
    uv run --directory mcp/daas-mcp python seed_massive_endpoints.py              # seed endpoints + indicators
    uv run --directory mcp/daas-mcp python seed_massive_endpoints.py --dry-run    # plan only
    uv run --directory mcp/daas-mcp python seed_massive_endpoints.py --unseed     # rollback
    uv run --directory mcp/daas-mcp python seed_massive_endpoints.py --no-indicators  # endpoints only
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent  # mcp/daas-mcp/ → mcp/ → repo root
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

sys.path.insert(0, str(_THIS.parent))

from daas_database import Database
from models import DaasFunction, DaasFunctionColumn, DaasSource, IndicatorRule


# ════════════════════════════════════════════════════════════════════════
# Massive.com endpoint catalog — hard-coded metadata (no network at seed time).
# Each entry: (name, label, description, category, path, query_params, gated, columns)
#   - path keeps {placeholder} tokens for path params an agent must supply.
#   - gated=True marks endpoints that 403 on the current plan.
#   - columns are the response column names (case-sensitive, exactly as returned).
# ════════════════════════════════════════════════════════════════════════

_GATED_SUFFIX = " (HTTP 403 — requires a higher Massive.com plan on the current entitlement; registered as metadata only)"

ENDPOINTS: list[tuple] = [
    # ── Reference ──
    ("reference_all_tickers", "All Tickers",
     "All ticker symbols supported by Massive across asset classes (stocks, indices, forex, crypto), with market, exchange, FIGI, and CIK identifiers.",
     "Reference", "/v3/reference/tickers",
     ["ticker", "type", "market", "exchange", "cusip", "cik", "date", "search", "active", "order", "limit", "sort"],
     False,
     ["ticker", "name", "market", "locale", "primary_exchange", "type", "active", "currency_name", "cik", "composite_figi", "share_class_figi", "last_updated_utc"]),

    ("reference_ticker_types", "Ticker Types",
     "All ticker types supported by Massive, categorized across asset classes, markets, and instruments.",
     "Reference", "/v3/reference/tickers/types",
     ["asset_class", "locale"],
     False,
     ["code", "description", "asset_class", "locale"]),

    ("reference_ticker_overview", "Ticker Overview",
     "Comprehensive details for a single ticker: exchange, identifiers (CIK, FIGI), market cap, industry classification, branding assets, and key dates.",
     "Reference", "/v3/reference/tickers/{ticker}",
     ["ticker", "date"],
     False,
     ["ticker", "name", "market", "locale", "primary_exchange", "type", "active", "currency_name", "cik", "composite_figi", "share_class_figi", "market_cap", "phone_number", "address_address1", "address_city", "address_state", "address_postal_code", "description", "sic_code", "sic_description", "ticker_root", "homepage_url", "total_employees", "list_date", "branding_logo_url", "branding_icon_url", "share_class_shares_outstanding", "weighted_shares_outstanding", "round_lot"]),

    # ── Stocks ──
    ("stocks_previous_bar", "Previous Day Bar (OHLC)",
     "Previous trading day's OHLC + volume + VWAP + transaction count for a stock ticker.",
     "Stocks", "/v2/aggs/ticker/{stocksTicker}/prev",
     ["adjusted"],
     False,
     ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),

    ("stocks_aggregates", "Aggregates (Bars)",
     "Custom aggregate bars over a date range for a stock ticker (OHLC + volume + VWAP + transaction count per bar).",
     "Stocks", "/v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{from}/{to}",
     ["adjusted", "sort", "limit"],
     False,
     ["v", "vw", "o", "c", "h", "l", "t", "n"]),

    ("stocks_related_companies", "Related Tickers",
     "Tickers related to a given ticker, derived from news coverage and returns analysis (peers / competitors).",
     "Stocks", "/v1/related-companies/{ticker}",
     [],
     False,
     ["ticker"]),

    ("stocks_ticker_events", "Ticker Events",
     "Timeline of key events for a ticker / CUSIP / Composite FIGI (symbol renames, rebrands). Experimental.",
     "Stocks", "/vX/reference/tickers/{id}/events",
     [],
     False,
     ["name", "composite_figi", "cik", "ticker_change_ticker", "type", "date"]),

    ("stocks_market_holidays", "Market Holidays",
     "Upcoming market holidays and their open/close times (forward-looking only).",
     "Stocks", "/v1/marketstatus/upcoming",
     [],
     False,
     ["date", "exchange", "name", "status", "close", "open"]),

    # ── Options ──
    ("options_chain_snapshot", "Option Chain Snapshot",
     "Snapshot of all options contracts for an underlying ticker: contract details, day stats (OHLC/volume/VWAP), open interest.",
     "Options", "/v3/snapshot/options/{underlyingAsset}",
     ["expiration_date", "contract_type", "strike_price", "order", "limit", "sort"],
     False,
     ["details_contract_type", "details_exercise_style", "details_expiration_date", "details_shares_per_contract", "details_strike_price", "details_ticker", "open_interest", "underlying_asset_ticker", "day_change", "day_change_percent", "day_close", "day_high", "day_last_updated", "day_low", "day_open", "day_previous_close", "day_volume", "day_vwap"]),

    ("options_contract_snapshot", "Option Contract Snapshot",
     "Snapshot of a single options contract: contract details, greeks (delta/gamma/theta/vega), implied volatility, open interest.",
     "Options", "/v3/snapshot/options/{underlyingAsset}/{optionContract}",
     [],
     False,
     ["details_contract_type", "details_exercise_style", "details_expiration_date", "details_shares_per_contract", "details_strike_price", "details_ticker", "greeks_delta", "greeks_gamma", "greeks_theta", "greeks_vega", "implied_volatility", "open_interest", "underlying_asset_ticker"]),

    ("options_all_contracts", "All Contracts",
     "Comprehensive index of options contracts (active and expired), filterable by underlying, type, expiration, strike.",
     "Options", "/v3/reference/options/contracts",
     ["underlying_ticker", "contract_type", "expiration_date", "as_of", "strike_price", "expired", "order", "limit", "sort"],
     False,
     ["cfi", "contract_type", "exercise_style", "expiration_date", "primary_exchange", "shares_per_contract", "strike_price", "ticker", "underlying_ticker"]),

    ("options_contract_overview", "Contract Overview",
     "Detailed information about a specific options contract: type, exercise style, expiration, strike, shares, underlying, exchange.",
     "Options", "/v3/reference/options/contracts/{options_ticker}",
     [],
     False,
     ["cfi", "contract_type", "exercise_style", "expiration_date", "primary_exchange", "shares_per_contract", "strike_price", "ticker", "underlying_ticker"]),

    ("options_last_trade", "Last Trade (Options)",
     "Latest available trade for an options contract: price, size, exchange, timestamp." + _GATED_SUFFIX,
     "Options", "/v2/last/trade/{optionsTicker}",
     [],
     True,
     ["price", "size", "exchange", "timestamp"]),

    # ── Crypto ──
    ("crypto_last_trade", "Last Trade (Crypto)",
     "Most recent trade for a crypto pair: price, size, timestamp, exchange, conditions." + _GATED_SUFFIX,
     "Crypto", "/v1/last/crypto/{from}/{to}",
     [],
     True,
     ["price", "size", "timestamp", "exchange", "conditions"]),

    ("crypto_daily_summary", "Daily Market Summary (Crypto OHLC)",
     "Daily OHLC + volume + VWAP for all crypto tickers on a given trading date.",
     "Crypto", "/v2/aggs/grouped/locale/global/market/crypto/{date}",
     ["adjusted"],
     False,
     ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),

    ("crypto_previous_bar", "Previous Day Bar (Crypto OHLC)",
     "Previous trading day's OHLC + volume + VWAP for a crypto pair.",
     "Crypto", "/v2/aggs/ticker/{cryptoTicker}/prev",
     ["adjusted"],
     False,
     ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),

    ("crypto_daily_open_close", "Daily Ticker Summary (Crypto)",
     "Opening and closing trades for a crypto pair on a given date.",
     "Crypto", "/v1/open-close/crypto/{from}/{to}/{date}",
     [],
     False,
     ["symbol", "isUTC", "day", "open", "close", "x", "p", "s", "c", "i", "t", "_source"]),

    # ── Forex ──
    ("forex_last_quote", "Last Quote (Forex)",
     "Most recent quote for a forex pair: bid, ask, exchange, timestamp." + _GATED_SUFFIX,
     "Forex", "/v1/last_quote/currencies/{from}/{to}",
     [],
     True,
     ["bid", "ask", "exchange", "timestamp"]),

    ("forex_previous_bar", "Previous Day Bar (Forex OHLC)",
     "Previous trading day's OHLC + volume + VWAP for a forex pair.",
     "Forex", "/v2/aggs/ticker/{forexTicker}/prev",
     ["adjusted"],
     False,
     ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),

    ("forex_daily_summary", "Daily Market Summary (Forex OHLC)",
     "Daily OHLC + volume + VWAP for all forex tickers on a given trading date.",
     "Forex", "/v2/aggs/grouped/locale/global/market/fx/{date}",
     ["adjusted"],
     False,
     ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),

    ("forex_conversion", "Currency Conversion",
     "Real-time currency conversion between two currencies using current bid/ask." + _GATED_SUFFIX,
     "Forex", "/v1/conversion/{from}/{to}",
     ["amount", "precision"],
     True,
     ["from", "to", "rate", "amount", "converted"]),

    # ── Futures ──
    ("futures_snapshot", "Futures Contracts Snapshot",
     "Real-time snapshots for futures contracts: last trade, quote, session metrics (OHLC, volume), settlement." + _GATED_SUFFIX,
     "Futures", "/futures/v1/snapshot",
     ["ticker", "product_code", "sort", "limit"],
     True,
     ["last_price", "last_size", "bid", "ask", "volume", "vwap", "open", "high", "low", "close", "settlement"]),

    ("futures_products", "Products",
     "All supported futures products with full specifications: codes, exchange, sector/asset class, type, settlement, pricing/quotation.",
     "Futures", "/futures/v1/products",
     ["name", "product_code", "date", "trading_venue", "sector", "sub_sector", "asset_class", "asset_sub_class", "type", "limit", "sort"],
     False,
     ["asset_sub_class", "date", "last_updated", "product_code", "trade_currency_code", "trading_venue", "type", "unit_of_measure", "unit_of_measure_qty"]),

    ("futures_exchanges", "Exchanges",
     "Supported futures exchanges with codes, names, MICs, and URLs.",
     "Futures", "/futures/v1/exchanges",
     [],
     False,
     ["id", "type", "locale", "name", "acronym", "mic", "operating_mic", "url"]),

    ("futures_quotes", "Quotes",
     "Quote data (best bid/offer prices, sizes, timestamps) for a futures contract ticker." + _GATED_SUFFIX,
     "Futures", "/futures/v1/quotes/{ticker}",
     [],
     True,
     ["bid_price", "bid_size", "ask_price", "ask_size", "timestamp"]),

    ("futures_trades", "Trades",
     "Tick-level trade data for a futures contract over a time range: price, size, session, timestamps." + _GATED_SUFFIX,
     "Futures", "/futures/v1/trades/{ticker}",
     ["limit", "sort"],
     True,
     ["price", "size", "session_start_date", "timestamp"]),

    ("futures_market_status", "Market Status",
     "Current market status (open/pause/close) for futures products, with exchange and product codes.",
     "Futures", "/futures/v1/market-status",
     [],
     False,
     ["product_code", "name", "session_end_date", "trading_venue", "market_event", "timestamp"]),

    # ── Indices ──
    ("indices_snapshot", "Indices Snapshot",
     "Snapshot for one or more indices: current value, recent performance, trading session details." + _GATED_SUFFIX,
     "Indices", "/v3/snapshot/indices",
     ["ticker"],
     True,
     ["value", "return", "status"]),

    ("indices_previous_bar", "Previous Day Bar (Indices OHLC)",
     "Previous trading day's OHLC + volume + VWAP for an index ticker." + _GATED_SUFFIX,
     "Indices", "/v2/aggs/ticker/{indicesTicker}/prev",
     ["adjusted"],
     True,
     ["T", "v", "vw", "o", "c", "h", "l", "t_2", "n"]),

    ("indices_daily_open_close", "Daily Ticker Summary (Indices)",
     "Opening and closing prices for an index on a given date, with pre-market and after-hours trade prices." + _GATED_SUFFIX,
     "Indices", "/v1/open-close/{indicesTicker}/{date}",
     [],
     True,
     ["open", "close", "high", "low", "afterHours", "preMarket"]),

    ("indices_market_status", "Market Status",
     "Current trading status for exchanges and overall financial markets (open/closed/pre/after-hours).",
     "Indices", "/v1/marketstatus/now",
     [],
     False,
     ["afterHours", "currencies_crypto", "currencies_fx", "earlyHours", "exchanges_nasdaq", "exchanges_nyse", "exchanges_otc", "indicesGroups_s_and_p", "indicesGroups_societe_generale", "indicesGroups_msci", "indicesGroups_ftse_russell", "indicesGroups_mstar", "indicesGroups_mstarc", "indicesGroups_cccy", "indicesGroups_cgi", "indicesGroups_nasdaq", "indicesGroups_dow_jones", "market", "serverTime"]),

    # ── Economy ──
    ("economy_treasury_yields", "Treasury Yields",
     "Historical U.S. Treasury yield data for standard maturities (3-month to 30-years), daily back to 1962.",
     "Economy", "/fed/v1/treasury-yields",
     ["date", "date_gte", "date_lte"],
     False,
     ["date", "yield_1_year", "yield_5_year", "yield_10_year", "yield_2_year", "yield_30_year", "yield_3_month"]),

    ("economy_inflation", "Inflation",
     "Realized inflation indicators — headline + core CPI and PCE, year-over-year CPI, and PCE spending.",
     "Economy", "/fed/v1/inflation",
     [],
     False,
     ["date", "cpi", "cpi_year_over_year", "cpi_core", "pce", "pce_core", "pce_spending"]),

    ("economy_inflation_expectations", "Inflation Expectations",
     "Expected U.S. inflation outlook — model + market signals across near- and long-term horizons (1y–30y).",
     "Economy", "/fed/v1/inflation-expectations",
     [],
     False,
     ["date", "model_1_year", "model_5_year", "model_10_year", "model_30_year", "market_5_year", "market_10_year", "forward_years_5_to_10"]),

    ("economy_labor_market", "Labor Market",
     "Key Federal Reserve labor-market indicators: unemployment, labor-force participation, job openings, average hourly earnings.",
     "Economy", "/fed/v1/labor-market",
     [],
     False,
     ["date", "unemployment_rate", "labor_force_participation_rate", "job_openings", "avg_hourly_earnings"]),

    # ── Alternative ──
    ("alt_merchant_hierarchy", "Merchant Hierarchy",
     "Merchants mapped to parent companies, tickers, sectors, and industries across the European consumer transaction panel." + _GATED_SUFFIX,
     "Alternative", "/consumer-spending/eu/v1/merchant-hierarchy",
     ["active_from", "active_to", "limit"],
     True,
     ["merchant_name", "parent_company", "ticker", "sector", "industry", "active_from", "active_to"]),

    ("alt_merchant_aggregates", "Merchant Aggregates",
     "Aggregated European consumer spending (credit/debit/open-banking) for ~250 US public companies across 6 EU countries." + _GATED_SUFFIX,
     "Alternative", "/consumer-spending/eu/v1/merchant-aggregates",
     ["ticker", "country", "date", "limit"],
     True,
     ["date", "ticker", "country", "spend_total", "transaction_count"]),
]

# Natural keys this seeder owns (functions + indicators). --unseed deletes exactly these.
OWNED_FUNCTION_NAMES = tuple(e[0] for e in ENDPOINTS)


# ════════════════════════════════════════════════════════════════════════
# Indicator definitions — Economy time-series endpoints.
# Built into (rule_name, ...) rows at seed time. Each rule reads from a
# scraw_massive_<slug> table populated by backfill_massive.py.
# ════════════════════════════════════════════════════════════════════════

# Each group: function_name, source_table, value_columns, ops[(op, params)]
_INDICATOR_GROUPS: list[dict] = [
    {
        "function_name": "economy_treasury_yields",
        "source_table": "scraw_massive_treasury_yields",
        "value_columns": ["yield_1_year", "yield_5_year", "yield_10_year", "yield_30_year"],
        "ops": [
            ("sma", {"window": 30}),
            ("ema", {"span": 20}),
            ("pct_change", {}),
            ("zscore", {"window": 30}),
            ("rolling_std", {"window": 30}),
            ("level", {}),
        ],
    },
    {
        "function_name": "economy_inflation",
        "source_table": "scraw_massive_inflation",
        "value_columns": ["cpi", "cpi_core", "pce"],
        "ops": [
            ("sma", {"window": 12}),
            ("pct_change", {}),
            ("zscore", {"window": 12}),
            ("level", {}),
        ],
    },
    {
        "function_name": "economy_inflation_expectations",
        "source_table": "scraw_massive_inflation_expectations",
        "value_columns": ["model_1_year", "model_5_year", "model_10_year", "model_30_year"],
        "ops": [
            ("sma", {"window": 12}),
            ("pct_change", {}),
            ("zscore", {"window": 12}),
        ],
    },
    {
        "function_name": "economy_labor_market",
        "source_table": "scraw_massive_labor_market",
        "value_columns": ["unemployment_rate", "labor_force_participation_rate", "job_openings", "avg_hourly_earnings"],
        "ops": [
            ("sma", {"window": 12}),
            ("pct_change", {}),
            ("zscore", {"window": 12}),
            ("level", {}),
        ],
    },
]


def _op_suffix(op: str, params: dict) -> str:
    """e.g. sma+{window:30} → 'sma30'; pct_change → 'pct_change'; ema+{span:20} → 'ema20'."""
    if op in ("sma", "ema", "zscore", "rolling_std", "rolling_min", "rolling_max", "rsi"):
        w = params.get("window") or params.get("span")
        return f"{op}{w}" if w is not None else op
    return op


def build_indicator_specs() -> list[dict]:
    """Expand _INDICATOR_GROUPS into one dict per indicator rule."""
    specs = []
    for grp in _INDICATOR_GROUPS:
        fn = grp["function_name"]
        tbl = grp["source_table"]
        for vc in grp["value_columns"]:
            for op, params in grp["ops"]:
                suffix = _op_suffix(op, params)
                indicator_name = f"{suffix}_{vc}"
                rule_name = f"massive_{fn}_{suffix}_{vc}"
                specs.append({
                    "rule_name": rule_name,
                    "datasource": "massive",
                    "function_name": fn,
                    "source_table": tbl,
                    "date_column": "date",
                    "value_column": vc,
                    "op": op,
                    "params": params,
                    "indicator_name": indicator_name,
                })
    return specs


OWNED_INDICATOR_NAMES = tuple(s["rule_name"] for s in build_indicator_specs())


# ════════════════════════════════════════════════════════════════════════
# Counters
# ════════════════════════════════════════════════════════════════════════

class Counts:
    def __init__(self) -> None:
        self.functions_new = 0
        self.functions_updated = 0
        self.columns_new = 0
        self.indicators_new = 0
        self.indicators_updated = 0
        self.deleted = {"functions": 0, "columns": 0, "indicators": 0}

    def print_seed_summary(self) -> None:
        print(f"  functions        +{self.functions_new} (~{self.functions_updated} updated)")
        print(f"  columns          +{self.columns_new}")
        print(f"  indicators       +{self.indicators_new} (~{self.indicators_updated} updated)")

    def print_unseed_summary(self) -> None:
        for k, v in self.deleted.items():
            print(f"  {k:<12} -{v}")


# ════════════════════════════════════════════════════════════════════════
# get-or-create helpers
# ════════════════════════════════════════════════════════════════════════

def goc_function(session, source_id, name, label, description, category, parameters, counts, dry_run):
    fn = (
        session.query(DaasFunction)
        .filter(DaasFunction.source_id == source_id, DaasFunction.name == name)
        .first()
    )
    if fn is not None:
        changed = False
        if fn.label != label:
            fn.label = label
            changed = True
        if fn.description != description:
            fn.description = description
            changed = True
        if fn.category != category:
            fn.category = category
            changed = True
        if fn.parameters != parameters:
            fn.parameters = parameters
            changed = True
        if changed:
            if dry_run:
                print(f"  [plan] UPDATE function name={name}")
            else:
                session.commit()
                counts.functions_updated += 1
        return fn
    if dry_run:
        print(f"  [plan] CREATE function name={name}")
        return None
    fn = DaasFunction(
        source_id=source_id, name=name, label=label, description=description,
        category=category, parameters=parameters, output_type="DataFrame",
    )
    session.add(fn)
    session.commit()
    counts.functions_new += 1
    return fn


def goc_column(session, function_id, name, counts, dry_run):
    col = (
        session.query(DaasFunctionColumn)
        .filter(DaasFunctionColumn.function_id == function_id, DaasFunctionColumn.name == name)
        .first()
    )
    if col is not None:
        return col
    if dry_run:
        return None
    col = DaasFunctionColumn(function_id=function_id, name=name)
    session.add(col)
    session.commit()
    counts.columns_new += 1
    return col


def goc_indicator(session, spec, counts, dry_run):
    """Direct insert into indicator_rules (bypasses create_indicator's
    source-table-existence validation — the scraw_massive_* tables are populated
    by backfill_massive.py, not present at seed time). Mirrors the seed pattern."""
    rule = session.query(IndicatorRule).filter(IndicatorRule.name == spec["rule_name"]).first()
    if rule is not None:
        changed = False
        for field in ("datasource", "function_name", "source_table", "date_column",
                       "value_column", "op", "params_json", "indicator_name"):
            val = spec["params"] if field == "params_json" else spec[field]
            if getattr(rule, field) != val:
                setattr(rule, field, val)
                changed = True
        if changed:
            if dry_run:
                print(f"  [plan] UPDATE indicator name={spec['rule_name']}")
            else:
                session.commit()
                counts.indicators_updated += 1
        return rule
    if dry_run:
        print(f"  [plan] CREATE indicator name={spec['rule_name']}")
        return None
    rule = IndicatorRule(
        name=spec["rule_name"],
        datasource=spec["datasource"],
        function_name=spec["function_name"],
        source_table=spec["source_table"],
        date_column=spec["date_column"],
        value_column=spec["value_column"],
        op=spec["op"],
        params_json=spec["params"],
        indicator_name=spec["indicator_name"],
        enabled=True,
    )
    session.add(rule)
    session.commit()
    counts.indicators_new += 1
    return rule


# ════════════════════════════════════════════════════════════════════════
# Seed
# ════════════════════════════════════════════════════════════════════════

def seed(session, counts: Counts, dry_run: bool = False, seed_indicators: bool = True) -> None:
    # ── 1. Resolve the massive source (created by seed_external_mcps.py) ──
    src = session.query(DaasSource).filter(DaasSource.name == "massive").first()
    if src is None:
        raise RuntimeError(
            "massive source not found in daas.db — run seed_external_mcps.py first "
            "to create it (source + default form + 3 composable-tool sections)."
        )

    # ── 2. daas_functions + daas_function_columns ──
    for (name, label, desc, category, path, qparams, gated, columns) in ENDPOINTS:
        parameters = {"path": path, "method": "GET", "query_params": qparams, "gated": gated}
        fn = goc_function(session, src.id, name, label, desc, category, parameters, counts, dry_run)
        if fn is None:
            # dry-run: still count planned columns for the summary
            continue
        for col_name in columns:
            goc_column(session, fn.id, col_name, counts, dry_run)

    # ── 3. indicator_rules over Economy series ──
    if seed_indicators:
        for spec in build_indicator_specs():
            goc_indicator(session, spec, counts, dry_run)


# ════════════════════════════════════════════════════════════════════════
# Unseed — remove only rows this seeder owns
# ════════════════════════════════════════════════════════════════════════

def unseed(session, counts: Counts) -> None:
    src = session.query(DaasSource).filter(DaasSource.name == "massive").first()
    if src is None:
        return  # nothing to unseed

    # 1. Owned daas_functions — cascade drops their daas_function_columns.
    fns = (
        session.query(DaasFunction)
        .filter(DaasFunction.source_id == src.id, DaasFunction.name.in_(OWNED_FUNCTION_NAMES))
        .all()
    )
    for fn in fns:
        col_n = session.query(DaasFunctionColumn).filter(
            DaasFunctionColumn.function_id == fn.id).count()
        counts.deleted["columns"] += col_n
        session.delete(fn)
        counts.deleted["functions"] += 1
    session.commit()

    # 2. Owned indicator_rules (datasource=massive, names this seeder created).
    rules = (
        session.query(IndicatorRule)
        .filter(IndicatorRule.datasource == "massive",
                IndicatorRule.name.in_(OWNED_INDICATOR_NAMES))
        .all()
    )
    for r in rules:
        session.delete(r)
        counts.deleted["indicators"] += 1
    session.commit()

    # NOTE: the massive source, its `default` form, its 3 sections, and its
    # `core` collection item are owned by seed_external_mcps.py — left intact.


# ════════════════════════════════════════════════════════════════════════
# Entrypoint
# ════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Seed Massive.com REST endpoints as daas_functions + columns + indicators.")
    p.add_argument("--db-url", help="Override DAAS_DATABASE_URL for this run")
    p.add_argument("--unseed", action="store_true", help="Remove only rows this seed owns")
    p.add_argument("--dry-run", action="store_true", help="Print the plan; perform no writes")
    p.add_argument("--no-indicators", action="store_true",
                   help="Seed endpoints only; skip indicator_rules")
    args = p.parse_args(argv)

    if args.db_url:
        os.environ["DAAS_DATABASE_URL"] = args.db_url

    # Reset the Database singleton so a --db-url override takes effect.
    Database._instance = None
    db = Database()
    session = db.get_session()
    counts = Counts()

    if args.unseed:
        print("Unseeding Massive.com endpoints + indicators...")
        unseed(session, counts)
        counts.print_unseed_summary()
        print("Done.")
    elif args.dry_run:
        print("Dry-run plan (no writes):")
        seed(session, counts, dry_run=True, seed_indicators=not args.no_indicators)
        counts.print_seed_summary()
    else:
        print("Seeding Massive.com endpoints + indicators...")
        seed(session, counts, dry_run=False, seed_indicators=not args.no_indicators)
        counts.print_seed_summary()
        print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
