"""
MCP Server for CKAN — open data portal registry queries + live function execution.

Exposes tools for Claude Code:
  search_functions     — search CKAN functions by name, category, or description
  get_function_info    — get function details (params, columns, description)
  list_categories      — list CKAN categories with function counts
  list_functions       — list all CKAN functions
  call_ckan_function   — execute a CKAN function and return results as JSON
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

from fastmcp import FastMCP
from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine, func, or_
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()

# ── Inline models (ponytail: avoid cli_anything.daas dependency) ──

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    functions = relationship("Function", back_populates="source")


class Function(Base):
    __tablename__ = "functions"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, default="")
    description = Column(Text, default="")
    parameters = Column(Text, default="{}")
    source = relationship("Source", back_populates="functions")

    def to_dict(self) -> dict:
        params = {}
        try:
            params = json.loads(self.parameters)
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "parameters": params,
            "source": self.source.name if self.source else None,
        }


SOURCE_NAME = "ckan"
_DB_URL: Optional[str] = None


def _get_db_url() -> str:
    global _DB_URL
    if _DB_URL:
        return _DB_URL
    url = os.environ.get("CKAN_DATABASE_URL") or os.environ.get("DAAS_DATABASE_URL")
    if not url:
        # Default: daas.db alongside ckan-mcp/ in mcp/
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "daas.db")
        url = f"sqlite:///{db_path}"
    _DB_URL = url
    return url


def _get_session() -> Session:
    engine = create_engine(_get_db_url(), echo=False)
    return sessionmaker(bind=engine)()


app = FastMCP(name="ckan-mcp")


# ── Registry query tools ──────────────────────────────────────────────

@app.tool
def search_functions(query: str, limit: int = 20) -> dict:
    """Search CKAN functions by name, category, or description.

    Args:
        query: Search term — matches function name, category, and description.
        limit: Maximum results to return (default 20, max 100).
    """
    session = _get_session()
    try:
        q = f"%{query}%"
        rows = (
            session.query(Function)
            .join(Source)
            .filter(Source.name == SOURCE_NAME)
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
        return {"source": SOURCE_NAME, "count": len(rows), "functions": [f.to_dict() for f in rows]}
    finally:
        session.close()


@app.tool
def get_function_info(name: str) -> dict:
    """Get detailed info for a CKAN function — params, output columns, description.

    Args:
        name: CKAN function name (e.g., 'ckan_package_search').
    """
    session = _get_session()
    try:
        func = (
            session.query(Function)
            .join(Source)
            .filter(Source.name == SOURCE_NAME, Function.name == name)
            .first()
        )
        if func is None:
            return {"error": f"Function '{name}' not found in ckan"}
        return func.to_dict()
    finally:
        session.close()


@app.tool
def list_categories() -> dict:
    """List all CKAN function categories with counts."""
    session = _get_session()
    try:
        rows = (
            session.query(Function.category, func.count(Function.id).label("cnt"))
            .join(Source)
            .filter(Source.name == SOURCE_NAME)
            .group_by(Function.category)
            .order_by(func.count(Function.id).desc())
            .all()
        )
        cats = [{"category": r.category, "count": r.cnt} for r in rows]
        return {"source": SOURCE_NAME, "total_categories": len(cats), "categories": cats}
    finally:
        session.close()


@app.tool
def list_functions(category: Optional[str] = None, limit: int = 100) -> dict:
    """List all CKAN functions, optionally filtered by category.

    Args:
        category: Optional category filter (substring match).
        limit: Maximum results to return (default 100, max 500).
    """
    session = _get_session()
    try:
        q = session.query(Function).join(Source).filter(Source.name == SOURCE_NAME)
        if category:
            q = q.filter(Function.category.like(f"%{category}%"))
        rows = q.order_by(Function.name).limit(min(limit, 500)).all()
        return {"source": SOURCE_NAME, "count": len(rows), "functions": [f.to_dict() for f in rows]}
    finally:
        session.close()


# ── Execution tool ────────────────────────────────────────────────────

@app.tool
def call_ckan_function(name: str, params_json: str = "{}") -> dict:
    """Execute a CKAN function and return results as JSON.

    Supported: ckan_package_search, ckan_package_show, ckan_resource_show,
    ckan_organization_list, ckan_tag_list.

    Args:
        name: CKAN function name (e.g., 'ckan_package_search').
        params_json: JSON object of parameter name→value pairs.
                     Example: '{"q": "air quality", "rows": 5}'
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid params_json: {e}"}

    try:
        import ckanapi
    except ImportError:
        return {"error": "ckanapi not installed", "hint": "pip install ckanapi"}

    # Map function names to CKAN API calls
    CKAN_URL = os.environ.get("CKAN_URL", "https://data.gov.uk")

    try:
        ckan = ckanapi.RemoteCKAN(CKAN_URL)

        if name == "ckan_package_search":
            data = ckan.action.package_search(**params)
        elif name == "ckan_package_show":
            data = ckan.action.package_show(**params)
        elif name == "ckan_resource_show":
            data = ckan.action.resource_show(**params)
        elif name == "ckan_organization_list":
            data = ckan.action.organization_list(**params)
        elif name == "ckan_tag_list":
            data = ckan.action.tag_list(**params)
        else:
            return {"error": f"Unknown CKAN function: {name}"}

        return {"type": "dict", "data": data}
    except Exception as e:
        return {"error": f"CKAN API error: {type(e).__name__}: {e}"}


if __name__ == "__main__":
    app.run(transport="stdio", show_banner=False)
