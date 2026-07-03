"""HK financial statements via akshare's stock_financial_hk_report_em.

Each call lazy-imports akshare. The serializer is the same one used by
edgartools-mcp (object dtype to survive NaN -> None).
"""
from __future__ import annotations

from typing import Any, Optional

# akshare's HK report endpoint uses Chinese indicator strings.
_INDICATORS = {
    "income_statement": "利润表",
    "balance_sheet": "资产负债表",
    "cashflow": "现金流量表",
}

# akshare report_type values for annual vs interim. (akshare uses 年度 / 报告期.)
_PERIODS = {
    "annual": "年度",
    "interim": "报告期",
}


def _import_akshare():
    try:
        import akshare as ak  # noqa: F401
        return ak
    except ImportError as e:
        raise ImportError("akshare is not installed") from e


def _serialize_df(df) -> dict[str, Any]:
    """Match edgartools-mcp's `_serialize` for DataFrames."""
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        return {"columns": [], "data": []}
    clean = df.astype(object).where(df.notna(), None)
    return {
        "columns": [str(c) for c in df.columns],
        "data": clean.to_dict(orient="records"),
    }


def _fetch(stock_code: str, statement: str, period: str) -> dict[str, Any]:
    indicator = _INDICATORS.get(statement)
    if indicator is None:
        raise ValueError(f"Unknown statement: {statement}")
    report_type = _PERIODS.get(period)
    if report_type is None:
        raise ValueError(f"Unknown period: {period} (use 'annual' or 'interim')")

    ak = _import_akshare()
    df = ak.stock_financial_hk_report_em(
        stock=stock_code, symbol=indicator, indicator=report_type
    )
    return _serialize_df(df)


def fetch_income_statement(stock_code: str, period: str = "annual") -> dict[str, Any]:
    return _fetch(stock_code, "income_statement", period)


def fetch_balance_sheet(stock_code: str, period: str = "annual") -> dict[str, Any]:
    return _fetch(stock_code, "balance_sheet", period)


def fetch_cashflow(stock_code: str, period: str = "annual") -> dict[str, Any]:
    return _fetch(stock_code, "cashflow", period)


def fetch_all(stock_code: str, period: str = "annual") -> dict[str, dict[str, Any]]:
    return {
        "income_statement": fetch_income_statement(stock_code, period),
        "balance_sheet": fetch_balance_sheet(stock_code, period),
        "cashflow": fetch_cashflow(stock_code, period),
    }


def fetch_one(stock_code: str, statement: str, period: str = "annual") -> dict[str, Any]:
    return _fetch(stock_code, statement, period)


# Optional thin wrapper for the analysis-indicator function — unused by the
# server tools, kept here for parity with the cnreport client.
def fetch_indicators(stock_code: str) -> dict[str, Any]:
    ak = _import_akshare()
    df = ak.stock_financial_hk_analysis_indicator_em(symbol=stock_code, indicator="年度")
    return _serialize_df(df)
