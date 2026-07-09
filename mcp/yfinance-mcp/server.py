"""
MCP Server for yfinance — registry queries + live function execution.

Mirrors mcp/akshare-mcp/server.py. Exposes:
  search_functions        — search the yfinance registry
  get_function_info       — get function details (params, columns, description)
  list_categories         — list all categories with counts
  list_functions          — list all functions, optionally filtered by category
  call_yfinance_function  — execute a yfinance function and return results as JSON

Command dispatch:
  ticker_<method>  -> yfinance.Ticker(symbol).<method>(**rest)
  everything else  -> yfinance.<name>(**params)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Unified env: root .env first, then per-MCP .env with override=True
try:
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]  # repo root
    load_dotenv(_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

from fastmcp import FastMCP

app = FastMCP(name="yfinance-mcp")

# Ensure the yfinance harness package is importable
_HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_YFINANCE_PKG = os.path.join(_HARNESS_ROOT, "yfinance-agent-harness")
if _YFINANCE_PKG not in sys.path:
    sys.path.insert(0, _YFINANCE_PKG)


# ── Registry query tools ──────────────────────────────────────────────


@app.tool
def search_functions(query: str, limit: int = 20) -> dict:
    """Search yfinance functions by name, category, or description.

    Multi-word queries are split and each term is OR-matched against
    function name, category, and description.

    Args:
        query: Search term(s) — matches function name, category, and description.
        limit: Maximum results to return (default 20, max 100).
    """
    from cli_anything.yfinance.core.registry import search_functions as _search

    terms = query.split()
    if len(terms) > 1:
        all_results: dict[str, dict] = {}
        for term in terms:
            results = _search(term)
            for name, info in results.items():
                if name not in all_results:
                    all_results[name] = info
    else:
        all_results = _search(query)

    limit = min(limit, 100)
    items = []
    for name, info in sorted(all_results.items())[:limit]:
        items.append(
            {
                "name": name,
                "category": info.get("category", ""),
                "description": info.get("description", ""),
            }
        )
    return {"count": len(all_results), "shown": len(items), "functions": items}


@app.tool
def get_function_info(name: str) -> dict:
    """Get detailed information about a yfinance function.

    Returns parameters (name, type, required, description), output columns,
    category, description, and source URL.

    Args:
        name: The exact command name (e.g., 'ticker_history', 'download').
    """
    from cli_anything.yfinance.core.registry import get_function_info as _info

    data = _info(name)
    if not data:
        return {"error": f"Function '{name}' not found"}
    return data


@app.tool
def list_categories() -> dict:
    """List all yfinance function categories with function counts.

    Returns categories sorted by function count descending.
    """
    from cli_anything.yfinance.core.registry import get_categories as _cats

    cats = _cats()
    items = [{"category": k, "count": v} for k, v in cats.items()]
    return {"total_categories": len(cats), "categories": items}


@app.tool
def list_functions(category: Optional[str] = None, limit: int = 100) -> dict:
    """List yfinance functions, optionally filtered by category.

    Category filter uses partial (LIKE) matching — you can pass a
    substring like 'fundamentals', 'price-history', or 'options'.

    Args:
        category: Optional category name substring to filter by.
        limit: Maximum results to return (default 100, max 500).
    """
    from cli_anything.yfinance.core.database import get_database
    from cli_anything.yfinance.core.models import Function
    from sqlalchemy import or_

    db = get_database()
    session = db.get_session()
    try:
        query = session.query(Function)
        if category:
            query = query.filter(
                or_(
                    Function.category.like(f"%{category}%"),
                    Function.command.like(f"%{category}%"),
                )
            )
        limit = min(limit, 500)
        rows = query.order_by(Function.command).limit(limit).all()
        items = []
        for func in rows:
            items.append(
                {
                    "name": func.command,
                    "category": func.category or "",
                    "description": func.description or "",
                }
            )
        total = query.count() if category else session.query(Function).count()
        return {"count": total, "shown": len(items), "functions": items}
    finally:
        session.close()


# ── Execution tool ────────────────────────────────────────────────────


@app.tool
def call_yfinance_function(name: str, params_json: str = "{}") -> dict:
    """Execute a yfinance function and return results as JSON.

    This is the MAIN tool — it actually calls the real yfinance library
    and returns live market data.

    Dispatch:
      - commands starting with 'ticker_' call yfinance.Ticker(symbol).<method>(**rest)
        (e.g. 'ticker_history' -> Ticker(symbol).history(period=...))
      - other commands call the top-level yfinance.<name>(**params)
        (e.g. 'download', 'search')

    Args:
        name: yfinance command name (e.g., 'ticker_history', 'download').
        params_json: JSON object string of parameter name→value pairs.
                     Example: '{"symbol": "AAPL", "period": "1mo"}'
    """
    import importlib
    import inspect

    # Parse params
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid params_json: {e}"}

    # Import yfinance
    try:
        yfinance = importlib.import_module("yfinance")
    except ImportError:
        return {
            "error": "yfinance is not installed",
            "hint": "Install with: pip install yfinance",
        }

    # Dispatch ticker_<method> vs top-level
    if name.startswith("ticker_"):
        method_name = name[len("ticker_"):]
        symbol = params.pop("symbol", None)
        if symbol is None:
            return {"error": f"Command '{name}' requires a 'symbol' parameter"}
        ticker = yfinance.Ticker(symbol)
        target = getattr(ticker, method_name, None)
        if target is None or not callable(target):
            return {"error": f"Ticker has no callable method '{method_name}'"}
        target_name = f"Ticker({symbol}).{method_name}"
    else:
        target = getattr(yfinance, name, None)
        if target is None or not callable(target):
            return {"error": f"Function '{name}' not found in yfinance"}
        target_name = name

    try:
        result = target(**params)
    except TypeError as e:
        sig = inspect.signature(target)
        param_hints = []
        for p_name, p_param in sig.parameters.items():
            default = ""
            if p_param.default is not inspect.Parameter.empty:
                default = f" (default: {p_param.default})"
            param_hints.append(f"{p_name}{default}")
        return {
            "error": f"Parameter error: {e}",
            "expected_params": param_hints,
            "target": target_name,
        }
    except Exception as e:
        return {"error": f"Execution error: {type(e).__name__}: {e}"}

    return _serialize_result(result)


# ── Serialization helpers ─────────────────────────────────────────────


def _serialize_result(result) -> dict:
    """Convert a function result to a JSON-serializable dict."""
    try:
        import pandas as pd
    except ImportError:
        return {"type": "unknown", "data": str(result)}

    if isinstance(result, pd.DataFrame):
        # Preserve a DatetimeIndex (e.g. Ticker.history() daily/intraday
        # bars) as a `date` column so downstream consumers — the daas
        # pipeline bridge upserting into scraw_<slug> — can key on it.
        # Without this, to_dict(orient="records") drops the index and the
        # date is lost. Stringify to ISO date so the result is JSON-safe
        # (pandas Timestamps are not json-serializable).
        if isinstance(result.index, pd.DatetimeIndex):
            result = result.reset_index(names="date")
            result["date"] = result["date"].dt.strftime("%Y-%m-%d")
        elif result.index.name is not None:
            result = result.reset_index()
        clean = result.where(result.notna(), None)
        return {
            "type": "dataframe",
            "shape": list(result.shape),
            "columns": list(result.columns),
            "data": clean.to_dict(orient="records"),
        }
    elif isinstance(result, pd.Series):
        clean = result.where(result.notna(), None)
        return {
            "type": "series",
            "length": len(result),
            "name": str(result.name) if result.name else None,
            "data": clean.to_dict(),
        }
    elif isinstance(result, (dict, list)):
        return {"type": type(result).__name__, "data": result}
    else:
        return {"type": "scalar", "data": str(result)}


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
