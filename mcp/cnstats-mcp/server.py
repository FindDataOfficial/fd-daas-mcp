"""
MCP Server for CNStats — Chinese National Statistics queries + live execution.

Exposes tools for Claude Code:
  search_functions     — search CNStats functions by name, category, or description
  get_function_info    — get function details (params, columns, description)
  list_categories      — list CNStats categories with function counts
  list_functions       — list all CNStats functions
  call_cnstats_function — execute a CNStats function and return results as JSON
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from cli_anything.daas.core.exceptions import DAASError
from fastmcp import FastMCP

app = FastMCP(name="cnstats-mcp")

_HARNESS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "daas-agent-harness",
)
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)


def _get_db_url() -> str:
    url = os.environ.get("CNSTATS_DATABASE_URL")
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


SOURCE = "cnstats"


@app.tool
def search_functions(query: str, limit: int = 20) -> dict:
    """Search Chinese Statistics functions by name, category, or description.

    Covers CPI, PMI, industrial output, fixed asset investment, retail sales,
    GDP, trade balance, and money supply data for China.

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
    """Get detailed info for a CNStats function — params, output columns, description.

    Args:
        name: CNStats function name (e.g., 'cnstats_cpi', 'cnstats_pmi').
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
            return {"error": f"Function '{name}' not found in cnstats"}
        return func.to_dict()
    finally:
        session.close()


@app.tool
def list_categories() -> dict:
    """List all CNStats function categories with counts (macro, industry, investment, etc.)."""
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
    """List all CNStats functions, optionally filtered by category.

    Args:
        category: Optional category filter — macro, industry, investment, consumption, trade, finance.
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
def call_cnstats_function(name: str, params_json: str = "{}") -> dict:
    """Execute a CNStats function and return results as JSON.

    Supported: cnstats_cpi, cnstats_pmi, cnstats_industrial_output,
    cnstats_fixed_asset_investment, cnstats_retail_sales,
    cnstats_gdp_quarterly, cnstats_trade_balance, cnstats_money_supply.

    Args:
        name: CNStats function name (e.g., 'cnstats_cpi').
        params_json: JSON object of parameter name→value pairs (most take no params).
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
            "hint": "Install: pip install akshare",
        }
    except Exception as e:
        return {"error": f"Execution error: {type(e).__name__}: {e}"}

    return _serialize_result(result)


@app.tool
def query_observations(
    source: Optional[str] = None,
    indicator: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """Query unified observations table across all DAAS sources.

    Returns indicator values from the observations table. Without filters,
    returns all indicators from all sources in one unified table.

    Args:
        source: Filter by source name ('cnstats', 'worldbank', 'ckan').
        indicator: Filter by indicator name (column name from source output).
        date_from: Filter observations on or after this date (inclusive).
        date_to: Filter observations on or before this date (inclusive).
        limit: Maximum results to return (default 100, max 5000).
    """
    from cli_anything.daas.core.models import Observation

    session = _get_session()
    try:
        q = session.query(Observation)
        if source:
            q = q.filter(Observation.source == source)
        if indicator:
            q = q.filter(Observation.indicator.like(f"%{indicator}%"))
        if date_from:
            q = q.filter(Observation.date >= date_from)
        if date_to:
            q = q.filter(Observation.date <= date_to)
        rows = q.order_by(Observation.source, Observation.indicator, Observation.date).limit(min(limit, 5000)).all()
        return {
            "count": len(rows),
            "observations": [r.to_dict() for r in rows],
        }
    finally:
        session.close()


@app.tool
def list_indicators(source: Optional[str] = None) -> dict:
    """List distinct indicators in the observations table.

    Args:
        source: Optional source filter ('cnstats', 'worldbank').
    """
    from cli_anything.daas.core.models import Observation
    from sqlalchemy import distinct, func

    session = _get_session()
    try:
        q = session.query(
            Observation.source, Observation.indicator, func.count(Observation.id).label("count")
        )
        if source:
            q = q.filter(Observation.source == source)
        q = q.group_by(Observation.source, Observation.indicator).order_by(
            Observation.source, func.count(Observation.id).desc()
        )
        rows = q.all()
        return {
            "count": len(rows),
            "indicators": [{"source": r[0], "indicator": r[1], "observations": r[2]} for r in rows],
        }
    finally:
        session.close()


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
