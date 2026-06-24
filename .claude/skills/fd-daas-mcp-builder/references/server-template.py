"""
MCP Server for {{SOURCE_LABEL}} — registry queries + live function execution.

Exposes tools for Claude Code:
  search_functions     — search {{SOURCE}} functions by name, category, or description
  get_function_info    — get function details (params, columns, description)
  list_categories      — list {{SOURCE}} categories with function counts
  list_functions       — list all {{SOURCE}} functions
  call_{{SOURCE}}_function — execute a {{SOURCE}} function and return results as JSON
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from fastmcp import FastMCP

app = FastMCP(name="{{SOURCE}}-mcp")

_HARNESS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "daas-agent-harness",
)
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)


def _get_db_url() -> str:
    url = os.environ.get("{{ENV_PREFIX}}_DATABASE_URL")
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


SOURCE = "{{SOURCE}}"


# ── Registry query tools ──────────────────────────────────────────────


@app.tool
def search_functions(query: str, limit: int = 20) -> dict:
    """Search {{SOURCE_LABEL}} functions by name, category, or description.

    {{SEARCH_HINT}}

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
    """Get detailed info for a {{SOURCE_LABEL}} function — params, output columns, description.

    Args:
        name: {{SOURCE}} function name (e.g., '{{EXAMPLE_FUNCTION}}').
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
            return {"error": f"Function '{name}' not found in {{SOURCE}}"}
        return func.to_dict()
    finally:
        session.close()


@app.tool
def list_categories() -> dict:
    """List all {{SOURCE_LABEL}} function categories with counts."""
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
    """List all {{SOURCE_LABEL}} functions, optionally filtered by category.

    Args:
        category: Optional category filter (substring match).
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


# ── Execution tool ────────────────────────────────────────────────────


@app.tool
def call_{{SOURCE}}_function(name: str, params_json: str = "{}") -> dict:
    """{{CALL_TOOL_DESCRIPTION}}

    {{SUPPORTED_FUNCTIONS}}

    Args:
        name: {{SOURCE}} function name (e.g., '{{EXAMPLE_FUNCTION}}').
        params_json: JSON object of parameter name→value pairs.
                     {{PARAMS_EXAMPLE}}
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid params_json: {e}"}

    try:
        from cli_anything.daas.sources.router import SourceRouter
        from cli_anything.daas.core.exceptions import DAASError

        router = SourceRouter()
        result = router.route(name, **params)
    except DAASError as e:
        return {"error": str(e)}
    except ImportError as e:
        return {
            "error": f"Dependency not available: {e}",
            "hint": "{{INSTALL_HINT}}",
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
