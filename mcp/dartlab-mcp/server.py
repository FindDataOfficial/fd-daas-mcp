"""
MCP Server for dartlab — Korea DART (+ US EDGAR) corporate filings, panels,
credit ratings, analysis, and market scans.

Purpose-built (not a registry/harness) because `dartlab` exposes an object model
(`Company(ticker)` → `.panel()`, `.credit()`, `.analysis()`; top-level `scan`),
not a flat function catalog — same shape as `edgartools-mcp`.

dartlab ships a built-in `dartlab mcp`, but it exposes *generic agent* tools
(`ask`, `RunPython`, `WebSearch`, …), not its financial-data surface. This server
wraps the data API directly so agents call typed, documented tools.

Tools:
  company_panel   — Company(ticker).panel(topic, freq=) — disclosure grid or a
                    named statement (IS/BS/ratios/사업/inventory/…). Uppercase
                    topics = finance-normalized; lowercase = native as-reported.
  panel_search    — Company(ticker).panel.search(query) — in-filing full-text
  list_filings    — Company(ticker).filings() — raw filing links (DART viewer)
  get_credit      — Company(ticker).credit("등급") — dCR grade / healthScore / PD
  analyze         — Company(ticker).analysis(kind, aspect) — deep analysis
  scan            — dartlab.scan(category, metric) — cross-sectional market scan

Identity: basic use is KEYLESS (pre-built parquet auto-downloads from
HuggingFace). An optional DART_API_KEY (free, opendart.fss.or.kr) is read by
dartlab from the environment for raw re-collection only — not required here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Unified env: root .env first, then per-MCP .env with override=True.
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="dartlab-mcp")

# DART_API_KEY is forwarded by dartlab's own env read (loadEnv at import); we do
# NOT gate any tool on it — basic use is keyless.


# ── Guards & serialization ────────────────────────────────────────────


def _import_dartlab():
    """Lazy-import dartlab, returning (module, error_dict)."""
    try:
        import dartlab

        return dartlab, None
    except ImportError:
        return None, {
            "error": "dartlab is not installed",
            "hint": "Install with: pip install dartlab",
        }


def _serialize(result: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Convert a dartlab result to a JSON-serializable value."""
    if depth > max_depth:
        return str(result)

    # Lazy pandas import (dartlab uses polars, but accept pandas too).
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore

    # polars DataFrame — duck-typed (dartlab's native).
    if pd is not None and isinstance(result, pd.DataFrame):
        clean = result.where(result.notna(), None)
        return {
            "type": "dataframe",
            "shape": list(result.shape),
            "columns": [str(c) for c in result.columns],
            "data": clean.to_dict(orient="records"),
        }
    if pd is not None and isinstance(result, pd.Series):
        clean = result.where(result.notna(), None)
        return {
            "type": "series",
            "length": len(result),
            "name": str(result.name) if result.name is not None else None,
            "data": clean.to_dict(),
        }
    if _is_polars_df(result):
        return _serialize_polars_df(result)
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


def _is_polars_df(obj: Any) -> bool:
    cls = type(obj)
    # polars DataFrame or any subclass (dartlab's Panel subclasses pl.DataFrame).
    for base in cls.__mro__:
        if base.__module__ == "polars.dataframe.frame" and base.__name__ == "DataFrame":
            return True
    return False


def _serialize_polars_df(df: Any) -> dict:
    """Serialize a polars DataFrame (or Panel subclass) to records."""
    try:
        rows = df.to_dicts()
    except Exception:
        try:
            rows = df.to_pandas().where(df.to_pandas().notna(), None).to_dict(orient="records")
        except Exception:
            return {"type": "scalar", "data": str(df)}
    # polars None/NaN → Python None already for most dtypes; sanitize floats.
    clean = []
    for r in rows:
        clean.append({str(k): _sanitize(v) for k, v in r.items()})
    try:
        shape = list(df.shape)
    except Exception:
        shape = [len(clean), 0]
    try:
        cols = [str(c) for c in df.columns]
    except Exception:
        cols = list(clean[0].keys()) if clean else []
    return {"type": "dataframe", "shape": shape, "columns": cols, "data": clean}


def _sanitize(v: Any) -> Any:
    """Turn polars NaN/inf and non-JSON values into JSON-safe scalars."""
    try:
        import math

        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
    except Exception:
        pass
    return v


# ── Tools ─────────────────────────────────────────────────────────────


@app.tool
def company_panel(
    ticker: str,
    topic: Optional[str] = None,
    freq: Optional[str] = None,
) -> dict:
    """Return a company's disclosure grid or a named statement/panel.

    Args:
        ticker: Korean stock code (e.g. "005930" Samsung) or US ticker ("AAPL").
        topic: Panel key. None = full disclosure grid. Uppercase = finance-normalized
            ("IS", "BS", "CF", "CIS", "SCE", "ratios"); lowercase = native as-reported
            ("is", "bs", "cf", freq="year"). Also accepts Korean section names
            ("사업", "재고", "inventory", "borrowings", "segments", ...).
        freq: Granularity — "year", "quarter", or "ytd". Only meaningful for
            statement topics. Omitted = library default.
    """
    dartlab, err = _import_dartlab()
    if err:
        return err

    try:
        company = dartlab.Company(ticker)
        panel = company.panel
        if topic is None:
            result = panel  # Panel is itself the wide grid (pl.DataFrame subclass)
        else:
            kwargs: dict[str, Any] = {}
            if freq is not None:
                kwargs["freq"] = freq
            result = panel(topic, **kwargs)
    except Exception as e:
        return {"error": f"company_panel failed: {type(e).__name__}: {e}"}

    return _serialize(result)


@app.tool
def panel_search(ticker: str, query: str) -> dict:
    """Full-text search within a company's filings via panel.search.

    Args:
        ticker: Korean stock code or US ticker.
        query: Search text (e.g. "재고", "유상증자").
    """
    dartlab, err = _import_dartlab()
    if err:
        return err

    try:
        company = dartlab.Company(ticker)
        result = company.panel.search(query)
    except Exception as e:
        return {"error": f"panel_search failed: {type(e).__name__}: {e}"}

    return _serialize(result)


@app.tool
def list_filings(ticker: str, limit: int = 20) -> dict:
    """List a company's raw filings with links to the DART viewer.

    Args:
        ticker: Korean stock code or US ticker.
        limit: Max filings to return (default 20, max 200).
    """
    dartlab, err = _import_dartlab()
    if err:
        return err

    limit = max(1, min(int(limit), 200))
    try:
        company = dartlab.Company(ticker)
        filings = company.filings()
    except Exception as e:
        return {"error": f"list_filings failed: {type(e).__name__}: {e}"}

    if filings is None:
        return {"count": 0, "filings": []}

    # filings() returns a polars/pandas DataFrame; slice then serialize.
    try:
        sliced = filings.head(limit)
    except Exception:
        try:
            sliced = filings[:limit]
        except Exception:
            sliced = filings

    ser = _serialize(sliced)
    # Normalize to {count, filings} for a stable, agent-friendly shape.
    if isinstance(ser, dict) and ser.get("type") == "dataframe":
        return {"count": len(ser.get("data", [])), "filings": ser.get("data", [])}
    return ser


@app.tool
def get_credit(ticker: str) -> dict:
    """Return dartlab's independent credit rating (dCR grade, healthScore, PD).

    Args:
        ticker: Korean stock code or US ticker.
    """
    dartlab, err = _import_dartlab()
    if err:
        return err

    try:
        company = dartlab.Company(ticker)
        result = company.credit("등급")
    except Exception as e:
        return {"error": f"get_credit failed: {type(e).__name__}: {e}"}

    return _serialize(result)


@app.tool
def analyze(
    ticker: str,
    kind: str = "financial",
    aspect: Optional[str] = None,
) -> dict:
    """Run dartlab's deep analysis for a company.

    Args:
        ticker: Korean stock code or US ticker.
        kind: Analysis group — "financial", "valuation", "governance",
            "forecast", or "macro". Default "financial".
        aspect: Optional sub-axis within the group (e.g. "수익성", "가치평가").
            Omit to return the whole group / catalog.
    """
    dartlab, err = _import_dartlab()
    if err:
        return err

    try:
        company = dartlab.Company(ticker)
        result = company.analysis(kind, aspect) if aspect else company.analysis(kind)
    except Exception as e:
        return {"error": f"analyze failed: {type(e).__name__}: {e}"}

    return _serialize(result)


@app.tool
def scan(category: str, metric: Optional[str] = None) -> dict:
    """Cross-sectional scan across listed companies.

    Args:
        category: Scan category — e.g. "ratio", "account", "governance".
        metric: Optional metric within the category (e.g. "roe", "매출액").
            Omit for whole-category scans (e.g. scan("governance")).
    """
    dartlab, err = _import_dartlab()
    if err:
        return err

    try:
        result = dartlab.scan(category, metric) if metric else dartlab.scan(category)
    except Exception as e:
        return {"error": f"scan failed: {type(e).__name__}: {e}"}

    return _serialize(result)


def _selfcheck() -> int:
    """Opt-in smoke check: exercise one tool end-to-end. Not part of CI."""
    dartlab, err = _import_dartlab()
    if err:
        print(err["error"], "->", err["hint"])
        return 1
    r = company_panel("005930", "IS", freq="year")
    if "error" in r:
        print("FAIL company_panel:", r["error"])
        return 1
    shape = r.get("shape") if isinstance(r, dict) else None
    print(f"OK company_panel('005930','IS') -> type={r.get('type')} shape={shape}")
    return 0


if __name__ == "__main__":
    import sys

    if "--selfcheck" in sys.argv:
        raise SystemExit(_selfcheck())
    app.run(transport="stdio", show_banner=False)
