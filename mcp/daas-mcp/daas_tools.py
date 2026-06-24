"""
MCP tools for daas-mcp — search, detail, fetch, list_sources, list_categories.

These are plain functions decorated with FastMCP @tool.
"""
from __future__ import annotations

import json
from typing import Optional

from daas_database import get_database
from registry_service import RegistryService


def _get_service() -> RegistryService:
    db = get_database()
    return RegistryService(db.get_session())


def list_sources() -> dict:
    """List all configured DAAS data sources with function counts.

    Returns sources like akshare, worldbank, ckan, cnstats
    with install status and available function counts.
    """
    svc = _get_service()
    sources = svc.list_sources()
    return {"sources": sources}


def search_functions(query: str, source: Optional[str] = None, limit: int = 20) -> dict:
    """Search DAAS functions by name, category, or description across all sources.

    Args:
        query: Search term — matches function name, category, and description.
        source: Optional source name filter (akshare, worldbank, ckan, cnstats).
        limit: Maximum results to return (default 20, max 100).
    """
    svc = _get_service()
    limit = min(limit, 100)
    results = svc.search_functions(query, source=source, limit=limit)
    return {"count": len(results), "results": results}


def get_function_detail(function_name: str) -> dict:
    """Get full details for a DAAS function — parameters, output columns, description.

    Args:
        function_name: Namespaced function name (e.g., 'worldbank_gdp', 'akshare_stock_zh_a_hist').
    """
    svc = _get_service()
    func = svc.get_function_detail(function_name)
    if func is None:
        return {"error": f"Function '{function_name}' not found"}
    return {"function": func}


def list_categories(source: Optional[str] = None) -> dict:
    """List all DAAS function categories with counts, optionally filtered by source.

    Args:
        source: Optional source name filter (akshare, worldbank, ckan, cnstats).
    """
    svc = _get_service()
    cats = svc.list_categories(source=source)
    return {"categories": cats}


def fetch_data(function_name: str, params_json: str = "{}") -> dict:
    """Execute a DAAS data function and return results as JSON.

    Routes to the correct source adapter based on function name prefix.

    Args:
        function_name: Namespaced function name (e.g., 'worldbank_ny_gdp_mktp_cd').
        params_json: JSON object string of parameter name→value pairs.
                     Example: '{"country": "CHN", "time": "2020:2023"}'
    """
    import os
    import sys

    # Resolve harness path
    _MCP_ROOT = os.path.dirname(os.path.abspath(__file__))
    _HARNESS_ROOT = os.path.join(os.path.dirname(_MCP_ROOT), "daas-agent-harness")
    if _HARNESS_ROOT not in sys.path:
        sys.path.insert(0, _HARNESS_ROOT)

    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid params_json: {e}"}

    try:
        from cli_anything.daas.sources.router import SourceRouter
        from cli_anything.daas.core.exceptions import DAASError

        router = SourceRouter()
        result = router.route(function_name, **params)
    except DAASError as e:
        return {"error": str(e)}
    except ImportError as e:
        return {"error": f"Dependency not available: {e}", "hint": "Install optional source packages"}
    except Exception as e:
        return {"error": f"Execution error: {type(e).__name__}: {e}"}

    return _serialize_result(result)


def _serialize_result(result) -> dict:
    """Convert a function result to a JSON-serializable dict."""
    try:
        import pandas as pd
    except ImportError:
        return {"type": "unknown", "data": str(result)}

    if isinstance(result, pd.DataFrame):
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
