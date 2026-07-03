"""
MCP Server for EdgarTools — SEC EDGAR filings, financials, insider trades.

Purpose-built (not a registry/harness) because `edgar` exposes an object model
(Company / Filing / Financials), not a flat function catalog.

Tools:
  get_company          — company facts (name, cik, sic, description, ...)
  list_filings         — a company's filings, optionally filtered by form
  get_filing           — a single filing by accession, parsed via filing.obj()
  get_financials       — financial statements (income / balance / cashflow)
  get_insider_trades   — Form 4 insider transactions

Identity: SEC requires a descriptive User-Agent. Set EDGAR_IDENTITY="Name email@domain"
in root .env (preferred) or this dir's .env. The library reads EDGAR_IDENTITY; we also
call set_identity() explicitly to fail fast with a clear message if it is missing.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="edgartools-mcp")

# Configure SEC identity at startup if available. We import edgar lazily inside
# tools (so the server stays importable without the dep), but set_identity is
# cheap and worth doing once at load when the lib is present.
_IDENTITY_OK: bool = bool(os.environ.get("EDGAR_IDENTITY", "").strip())
if _IDENTITY_OK:
    try:
        from edgar import set_identity

        set_identity(os.environ["EDGAR_IDENTITY"])
    except Exception:
        # Don't crash the server; tools will surface a clearer error per-call.
        _IDENTITY_OK = False


# ── Guards & serialization ────────────────────────────────────────────


def _require_identity() -> Optional[dict]:
    """Return an error dict if SEC identity is not configured, else None."""
    if not _IDENTITY_OK:
        return {
            "error": "EDGAR_IDENTITY is not set",
            "hint": 'Set EDGAR_IDENTITY="Name email@domain" in root .env (required by SEC).',
        }
    return None


def _import_edgar():
    """Lazy-import edgar, returning (module, error_dict)."""
    try:
        import edgar

        return edgar, None
    except ImportError:
        return None, {
            "error": "edgartools is not installed",
            "hint": "Install with: pip install edgartools",
        }


def _serialize(result: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Convert an edgar result to a JSON-serializable value."""
    if depth > max_depth:
        return str(result)

    # Lazy pandas import
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore

    if pd is not None and isinstance(result, pd.DataFrame):
        # object dtype so NaN -> None survives to_dict on float columns
        clean = result.astype(object).where(result.notna(), None)
        return {
            "type": "dataframe",
            "shape": list(result.shape),
            "columns": [str(c) for c in result.columns],
            "data": clean.to_dict(orient="records"),
        }
    if pd is not None and isinstance(result, pd.Series):
        clean = result.astype(object).where(result.notna(), None)
        return {
            "type": "series",
            "length": len(result),
            "name": str(result.name) if result.name is not None else None,
            "data": clean.to_dict(),
        }
    # numpy scalars / arrays (e.g. edgar's int64 shares_traded) — convert to native.
    if hasattr(result, "dtype") and hasattr(result, "item"):
        try:
            return result.item() if result.ndim == 0 else _serialize(result.tolist(), depth + 1, max_depth)
        except Exception:
            return str(result)
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    if isinstance(result, dict):
        return {str(k): _serialize(v, depth + 1, max_depth) for k, v in result.items()}
    if isinstance(result, (list, tuple, set)):
        return [_serialize(v, depth + 1, max_depth) for v in result]

    # Objects with __dict__: flatten to a dict of public, non-callable attrs.
    if hasattr(result, "__dict__"):
        d = {}
        for k, v in vars(result).items():
            if k.startswith("_") or callable(v):
                continue
            d[k] = _serialize(v, depth + 1, max_depth)
        if d:
            return d

    # Fallback: enumerate public non-callable attributes; else stringify.
    out: dict[str, Any] = {}
    for a in dir(result):
        if a.startswith("_"):
            continue
        try:
            v = getattr(result, a)
        except Exception:
            continue
        if callable(v):
            continue
        out[a] = _serialize(v, depth + 1, max_depth)
    if out:
        return out
    return {"type": "scalar", "data": str(result)}


# ── Tools ─────────────────────────────────────────────────────────────


@app.tool
def get_company(ticker_or_cik: str) -> dict:
    """Return SEC EDGAR company facts for a ticker or CIK.

    Args:
        ticker_or_cik: Ticker (e.g. "AAPL") or CIK (e.g. "0000320193").
    """
    if err := _require_identity():
        return err
    edgar, err = _import_edgar()
    if err:
        return err

    try:
        company = edgar.Company(ticker_or_cik)
    except Exception as e:
        return {"error": f"Company lookup failed: {type(e).__name__}: {e}"}

    # Pull a curated set of summary fields; tolerate attribute differences
    # across edgar versions.
    fields = [
        "name", "cik", "tickers", "former_names", "sic", "sic_description",
        "state_of_incorporation", "description", "website", "category",
        "fiscal_year_end", "market_cap", "entity_type",
    ]
    out: dict[str, Any] = {}
    for f in fields:
        try:
            out[f] = _serialize(getattr(company, f))
        except Exception:
            continue
    if not out:
        return {"error": "No company fields could be read", "raw": _serialize(company)}
    return out


@app.tool
def list_filings(ticker_or_cik: str, form: Optional[str] = None, limit: int = 20) -> dict:
    """List a company's SEC filings, optionally filtered by form type.

    Args:
        ticker_or_cik: Ticker or CIK.
        form: Optional form filter (e.g. "10-K", "10-Q", "8-K", "4").
        limit: Max filings to return (default 20, max 200).
    """
    if err := _require_identity():
        return err
    edgar, err = _import_edgar()
    if err:
        return err

    try:
        company = edgar.Company(ticker_or_cik)
        filings = company.get_filings(form=form) if form else company.get_filings()
    except Exception as e:
        return {"error": f"list_filings failed: {type(e).__name__}: {e}"}

    limit = max(1, min(int(limit), 200))
    rows = []
    for f in filings[:limit]:
        rows.append(_filing_summary(f))
    return {"count": len(rows), "form": form, "filings": rows}


@app.tool
def get_filing(
    accession_number: str,
    ticker_or_cik: Optional[str] = None,
    detail: str = "standard",
    form: Optional[str] = None,
) -> dict:
    """Fetch and parse a single SEC filing by accession number.

    Args:
        accession_number: Filing accession number (with or without dashes).
        ticker_or_cik: Optional ticker/CIK to scope the lookup (faster).
        detail: Payload size — "minimal", "standard" (default), or "full".
        form: Optional form type hint to speed the lookup.
    """
    if err := _require_identity():
        return err
    edgar, err = _import_edgar()
    if err:
        return err

    # Normalize accession: edgar wants dashes.
    acc = accession_number.replace("-", "").replace(":", "")
    if len(acc) == 18:
        acc = f"{acc[:10]}-{acc[10:12]}-{acc[12:]}"

    filing = None
    try:
        if ticker_or_cik:
            company = edgar.Company(ticker_or_cik)
            filings = company.get_filings(form=form) if form else company.get_filings()
            for f in filings:
                if getattr(f, "accession_number", "").replace("-", "") == acc.replace("-", ""):
                    filing = f
                    break
        if filing is None:
            filing = edgar.Filing(form=form or "", accession_no=acc)
    except Exception as e:
        return {"error": f"Filing lookup failed: {type(e).__name__}: {e}"}

    if filing is None:
        return {"error": f"Filing '{accession_number}' not found"}

    out = _filing_summary(filing)

    if detail != "minimal":
        try:
            obj = filing.obj()
            out["data_object_type"] = type(obj).__name__
            if detail == "full":
                out["data_object"] = _serialize(obj, max_depth=5)
            else:  # standard
                out["context"] = _serialize(obj, max_depth=2)
        except Exception as e:
            out["obj_error"] = f"{type(e).__name__}: {e}"
    return out


@app.tool
def get_financials(
    ticker_or_cik: str,
    statement: Optional[str] = None,
    period: str = "annual",
) -> dict:
    """Return financial statements for a company.

    Args:
        ticker_or_cik: Ticker or CIK.
        statement: Optional single statement — "income_statement",
            "balance_sheet", or "cashflow" (a.k.a. "cashflow_statement").
            If omitted, returns all three standard statements.
        period: "annual" (default) or "quarterly".
    """
    if err := _require_identity():
        return err
    edgar, err = _import_edgar()
    if err:
        return err

    try:
        company = edgar.Company(ticker_or_cik)
        financials = company.get_financials()
    except Exception as e:
        return {"error": f"get_financials failed: {type(e).__name__}: {e}"}

    # edgar's Financials exposes .income_statement / .balance_sheet / .cash_flow
    # variants; pick by period then by requested statement.
    period_suffix = "quarterly" if period.lower().startswith("q") else "annual"
    statement_map = {
        "income_statement": "income_statement",
        "income": "income_statement",
        "balance_sheet": "balance_sheet",
        "balance": "balance_sheet",
        "cashflow": "cash_flow",
        "cash_flow": "cash_flow",
        "cashflow_statement": "cash_flow",
    }

    def _get(name: str) -> Any:
        # Try period-aware accessor first, then plain. Attributes here are
        # methods on Financials, so call them.
        for attr in (f"{name}_{period_suffix}", name):
            try:
                val = getattr(financials, attr)
            except Exception:
                continue
            try:
                return val() if callable(val) else val
            except Exception:
                continue
        return None

    if statement:
        key = statement_map.get(statement.lower().strip(), statement)
        result = _get(key)
        if result is None:
            return {"error": f"Statement '{statement}' not available"}
        return {"statement": key, "period": period_suffix, "data": _to_df_or_serialize(result)}

    out: dict[str, Any] = {"period": period_suffix, "statements": {}}
    for key in ("income_statement", "balance_sheet", "cash_flow"):
        try:
            out["statements"][key] = _to_df_or_serialize(_get(key))
        except Exception as e:
            out["statements"][key] = {"error": f"{type(e).__name__}: {e}"}
    return out


def _to_df_or_serialize(stmt: Any) -> Any:
    """A Statement is a rich XBRL object; prefer its tabular form."""
    if stmt is None:
        return None
    for meth in ("to_dataframe", "get_raw_data"):
        fn = getattr(stmt, meth, None)
        if callable(fn):
            try:
                df = fn()
                if df is not None:
                    return _serialize(df)
            except Exception:
                continue
    return _serialize(stmt)


@app.tool
def get_insider_trades(ticker_or_cik: str, limit: int = 20) -> dict:
    """Return recent insider transactions (Form 4) for a company.

    Args:
        ticker_or_cik: Ticker or CIK.
        limit: Max Form 4 filings to parse (default 20, max 100).
    """
    if err := _require_identity():
        return err
    edgar, err = _import_edgar()
    if err:
        return err

    try:
        company = edgar.Company(ticker_or_cik)
        form4s = company.get_filings(form="4").head(limit)
    except Exception as e:
        return {"error": f"get_insider_trades failed: {type(e).__name__}: {e}"}

    limit = max(1, min(int(limit), 100))
    trades = []
    for f in form4s[:limit]:
        entry: dict[str, Any] = {
            "accession_number": getattr(f, "accession_number", None),
            "filed": str(getattr(f, "filing_date", "") or ""),
        }
        try:
            obj = f.obj()
            # Extract the useful Form4 fields explicitly (insider, period,
            # shares, and the buy/sell DataFrames) rather than dumping the
            # whole ownership object.
            issuer = getattr(obj, "issuer", None)
            entry["owner"] = getattr(obj, "insider_name", None)
            entry["issuer"] = getattr(issuer, "company", None) or str(issuer)
            entry["reported_at"] = str(getattr(obj, "reporting_period", "") or "")
            entry["position"] = getattr(obj, "position", None)
            entry["shares_traded"] = _serialize(getattr(obj, "shares_traded", None))
            entry["purchases"] = _serialize(getattr(obj, "common_stock_purchases", None))
            entry["sales"] = _serialize(getattr(obj, "common_stock_sales", None))
        except Exception as e:
            entry["parse_error"] = f"{type(e).__name__}: {e}"
        trades.append(entry)
    return {"count": len(trades), "trades": trades}


# ── Helpers ───────────────────────────────────────────────────────────


def _filing_summary(f) -> dict:
    """Extract a flat summary dict from a Filing object."""
    return {
        "accession_number": getattr(f, "accession_number", None),
        "form": getattr(f, "form", None),
        "company": _serialize(getattr(f, "company", None), max_depth=1),
        "filed": str(getattr(f, "filing_date", "") or ""),
        "primary_document": getattr(f, "primary_document", None),
        "url": getattr(f, "filing_url", None) or getattr(f, "url", None),
    }


def _selfcheck() -> int:
    """Offline check of the non-trivial _serialize logic. No network, no SEC."""
    import pandas as pd

    # DataFrame path
    df = pd.DataFrame({"a": [1, None], "b": ["x", "y"]})
    s = _serialize(df)
    assert s["type"] == "dataframe" and s["shape"] == [2, 2], s
    assert s["data"][1]["a"] is None, s["data"]  # NaN -> None

    # numpy scalar path
    assert _serialize(pd.Series([1]).iloc[0]) == 1

    # dict / list / scalar paths
    assert _serialize({"k": [1, 2]}) == {"k": [1, 2]}
    assert _serialize([1, "x"]) == [1, "x"]
    assert _serialize("hi") == "hi"

    # fallback object: public non-callable attrs only
    class _O:
        def __init__(self):
            self.name = "Apple"
            self._hidden = "no"

        def method(self):
            return 1

    out = _serialize(_O())
    assert out == {"name": "Apple"}, out

    # identity guard
    server_globals_id = _IDENTITY_OK
    assert _require_identity() is None if server_globals_id else isinstance(
        _require_identity(), dict
    )
    print("selfcheck OK")
    return 0


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        raise SystemExit(_selfcheck())
    app.run(transport="stdio", show_banner=False)
