"""
MCP Server for AKShare — registry queries + live function execution.

Exposes tools that Claude Code can invoke directly:
  search_functions     — search the AKShare registry
  get_function_info    — get function details (params, columns, description)
  list_categories      — list all categories with counts
  list_functions       — list all functions, optionally filtered by category
  call_akshare_function — execute an AKShare function and return results as JSON
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from fastmcp import FastMCP

app = FastMCP(name="akshare-mcp")

# Ensure the akshare harness package is importable
_HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AKSHARE_PKG = os.path.join(_HARNESS_ROOT, "akshare-agent-harness")
if _AKSHARE_PKG not in sys.path:
    sys.path.insert(0, _AKSHARE_PKG)


# ── Registry query tools ──────────────────────────────────────────────


@app.tool
def search_functions(query: str, limit: int = 20) -> dict:
    """Search AKShare functions by name, category, or description.

    Multi-word queries are split and each term is OR-matched against
    function name, category, and description.

    Args:
        query: Search term(s) — matches function name, category, and description.
        limit: Maximum results to return (default 20, max 100).
    """
    from cli_anything.akshare.core.registry import search_functions as _search

    # Split multi-word queries and OR-match each term, then dedupe
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
    """Get detailed information about an AKShare function.

    Returns parameters (name, type, required, description), output columns,
    category, description, and source URL.

    Args:
        name: The exact function name (e.g., 'stock_zh_a_hist').
    """
    from cli_anything.akshare.core.registry import get_function_info as _info

    data = _info(name)
    if not data:
        return {"error": f"Function '{name}' not found"}
    return data


@app.tool
def list_categories() -> dict:
    """List all AKShare function categories with function counts.

    Returns categories sorted by function count descending.
    """
    from cli_anything.akshare.core.registry import get_categories as _cats

    cats = _cats()
    items = [{"category": k, "count": v} for k, v in cats.items()]
    return {"total_categories": len(cats), "categories": items}


@app.tool
def list_functions(category: Optional[str] = None, limit: int = 100) -> dict:
    """List AKShare functions, optionally filtered by category.

    Category filter uses partial (LIKE) matching — you can pass a
    substring like 'stock', '历史行情', or '期货'.

    Args:
        category: Optional category name substring to filter by.
        limit: Maximum results to return (default 100, max 500).
    """
    from cli_anything.akshare.core.database import get_database
    from cli_anything.akshare.core.models import Function
    from sqlalchemy import or_

    db = get_database()
    session = db.get_session()
    try:
        query = session.query(Function)
        if category:
            # LIKE match for Chinese category names
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
def call_akshare_function(name: str, params_json: str = "{}") -> dict:
    """Execute an AKShare function and return results as JSON.

    This is the MAIN tool — it actually calls the real AKShare library
    and returns live financial data.

    Args:
        name: AKShare function name (e.g., 'stock_zh_a_hist').
        params_json: JSON object string of parameter name→value pairs.
                     Example: '{"symbol": "000001", "period": "daily"}'
    """
    import importlib

    # Parse params
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid params_json: {e}"}

    # Import akshare
    try:
        akshare = importlib.import_module("akshare")
    except ImportError:
        return {
            "error": "akshare is not installed",
            "hint": "Install with: pip install akshare",
        }

    func = getattr(akshare, name, None)
    if func is None:
        return {"error": f"Function '{name}' not found in akshare"}

    try:
        result = func(**params)
    except TypeError as e:
        import inspect

        sig = inspect.signature(func)
        param_hints = []
        for p_name, p_param in sig.parameters.items():
            default = ""
            if p_param.default is not inspect.Parameter.empty:
                default = f" (default: {p_param.default})"
            param_hints.append(f"{p_name}{default}")
        return {
            "error": f"Parameter error: {e}",
            "expected_params": param_hints,
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
        # Replace NaN/NaT with None for valid JSON
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
