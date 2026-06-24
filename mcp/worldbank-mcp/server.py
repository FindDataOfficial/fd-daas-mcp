"""
MCP Server for World Bank — open data registry queries + live function execution.

Exposes tools for Claude Code:
  search_functions      — search World Bank functions by name, category, or description
  get_function_info     — get function details (params, columns, description)
  list_categories       — list World Bank categories with function counts
  list_functions        — list all World Bank functions
  call_worldbank_function — execute a World Bank function and return results as JSON
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from cli_anything.daas.core.exceptions import DAASError
from fastmcp import FastMCP

app = FastMCP(name="worldbank-mcp")

_HARNESS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "daas-agent-harness",
)
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)


def _get_db_url() -> str:
    url = os.environ.get("WORLDBANK_DATABASE_URL")
    if url:
        return url
    db_path = os.environ.get("DAAS_DATABASE_URL", "sqlite:///../daas.db")
    return db_path


def _get_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(_get_db_url(), echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


SOURCE = "worldbank"


@app.tool
def search_functions(query: str, limit: int = 20) -> dict:
    """Search World Bank functions by name, category, or description.

    Covers 20+ key indicators: GDP, population, unemployment, inflation,
    trade, education, health, environment, energy, and finance.

    Args:
        query: Search term — matches function name, category, and description.
        limit: Maximum results to return (default 20, max 100).
    """
    from cli_anything.daas.core.models import Function, Source
    from sqlalchemy import or_

    session = _get_session()
    try:
        q = f"%{query}%"
        rows = (
            session.query(Function)
            .join(Source)
            .filter(Source.name == SOURCE)
            .filter(
                or_(
                    Function.name.like(q),
                    Function.category.like(q),
                    Function.description.like(q),
                )
            )
            .order_by(Function.name)
            .limit(min(limit, 100))
            .all()
        )
        return {
            "source": SOURCE,
            "count": len(rows),
            "functions": [f.to_dict() for f in rows],
        }
    finally:
        session.close()


@app.tool
def get_function_info(name: str) -> dict:
    """Get detailed info for a World Bank function — params, output columns, description.

    Args:
        name: World Bank function name (e.g., 'worldbank_ny_gdp_mktp_cd').
    """
    from cli_anything.daas.core.models import Function, Source

    session = _get_session()
    try:
        func = (
            session.query(Function)
            .join(Source)
            .filter(Source.name == SOURCE, Function.name == name)
            .first()
        )
        if func is None:
            return {"error": f"Function '{name}' not found in worldbank"}
        return func.to_dict()
    finally:
        session.close()


@app.tool
def list_categories() -> dict:
    """List all World Bank function categories with counts."""
    from cli_anything.daas.core.models import Function, Source
    from sqlalchemy import func

    session = _get_session()
    try:
        rows = (
            session.query(
                Function.category,
                func.count(Function.id).label("cnt"),
            )
            .join(Source)
            .filter(Source.name == SOURCE)
            .group_by(Function.category)
            .order_by(func.count(Function.id).desc())
            .all()
        )
        cats = [{"category": r.category, "count": r.cnt} for r in rows]
        return {"source": SOURCE, "total_categories": len(cats), "categories": cats}
    finally:
        session.close()


@app.tool
def list_functions(category: Optional[str] = None, limit: int = 100) -> dict:
    """List all World Bank functions, optionally filtered by category.

    Args:
        category: Optional category filter (macro, demographics, trade, education, etc.).
        limit: Maximum results to return (default 100, max 500).
    """
    from cli_anything.daas.core.models import Function, Source

    session = _get_session()
    try:
        q = session.query(Function).join(Source).filter(Source.name == SOURCE)
        if category:
            q = q.filter(Function.category.like(f"%{category}%"))
        rows = q.order_by(Function.name).limit(min(limit, 500)).all()
        return {
            "source": SOURCE,
            "count": len(rows),
            "functions": [f.to_dict() for f in rows],
        }
    finally:
        session.close()


@app.tool
def call_worldbank_function(name: str, params_json: str = "{}") -> dict:
    """Execute a World Bank function and return results as JSON.

    Supported: 20 indicators covering GDP, population, unemployment, inflation,
    trade, education, health, environment, energy, and finance.

    Args:
        name: World Bank function name (e.g., 'worldbank_ny_gdp_mktp_cd').
        params_json: JSON object of parameter name→value pairs.
                     Example: '{"country": "CHN", "time": "2020:2023"}'
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid params_json: {e}"}

    try:
        from cli_anything.daas.sources.router import SourceRouter

        router = SourceRouter()
        result = router.route(name, **params)
    except DAASError as e:
        return {"error": str(e)}
    except ImportError as e:
        return {
            "error": f"Dependency not available: {e}",
            "hint": "Install: pip install requests (worldbank uses REST API, no extra deps needed)",
        }
    except Exception as e:
        return {"error": f"Execution error: {type(e).__name__}: {e}"}

    return _serialize_result(result)


def _serialize_result(result) -> dict:
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


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
