"""
Registry service for DAAS function metadata.

Query orchestration over the SQLAlchemy models.
Mirrors the akshare RegistryService API surface:
  list_functions, search_functions, get_function_info, get_categories, get_category_functions.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from cli_anything.daas.core.models import Function, FunctionColumn, Source

logger = logging.getLogger(__name__)


class RegistryService:
    """Query orchestration for DAAS function metadata across all sources."""

    def __init__(self, session: Session):
        self._session = session

    def list_functions(self, source: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
        """List all functions, optionally filtered by source name or category."""
        query = self._session.query(Function).join(Source)
        if source:
            query = query.filter(Source.name == source)
        if category:
            query = query.filter(Function.category.like(f"%{category}%"))
        return [func.to_dict() for func in query.order_by(Source.name, Function.name).all()]

    def search_functions(self, query: str, source: Optional[str] = None) -> list[dict]:
        """Search functions by name, category, or description (case-insensitive)."""
        q = f"%{query}%"
        q_obj = (
            self._session.query(Function)
            .join(Source)
            .filter(
                or_(
                    Function.name.like(q),
                    Function.category.like(q),
                    Function.description.like(q),
                )
            )
        )
        if source:
            q_obj = q_obj.filter(Source.name == source)
        return [func.to_dict() for func in q_obj.order_by(Source.name, Function.name).all()]

    def get_function_info(self, name: str) -> Optional[dict]:
        """Get full metadata for a single function by its namespaced name (source_funcname)."""
        func = self._session.query(Function).filter(Function.name == name).first()
        if func is None:
            return None
        return func.to_dict()

    def get_categories(self, source: Optional[str] = None) -> list[dict]:
        """List categories with function counts, optionally filtered by source."""
        q = self._session.query(
            Source.name.label("source_name"),
            Function.category,
            func.count(Function.id).label("cnt"),
        ).join(Function.source)
        if source:
            q = q.filter(Source.name == source)
        rows = (
            q.group_by(Source.name, Function.category)
            .order_by(Source.name, func.count(Function.id).desc())
            .all()
        )
        return [{"source": row.source_name, "category": row.category, "count": row.cnt} for row in rows]

    def get_category_functions(self, category: str, source: Optional[str] = None) -> list[dict]:
        """Get all functions in a specific category."""
        return self.list_functions(source=source, category=category)

    def list_sources(self) -> list[dict]:
        """List all registered sources with function counts."""
        sources = self._session.query(Source).order_by(Source.name).all()
        result = []
        for s in sources:
            d = s.to_dict()
            # Get actual count from DB
            cnt = self._session.query(func.count(Function.id)).filter(Function.source_id == s.id).scalar()
            d["function_count"] = cnt
            result.append(d)
        return result

    def upsert_function(self, source_name: str, func_data: dict) -> None:
        """Insert or update a function and its columns. Idempotent."""
        source = self._session.query(Source).filter(Source.name == source_name).first()
        if source is None:
            return

        func = (
            self._session.query(Function)
            .filter(Function.source_id == source.id, Function.name == func_data["name"])
            .first()
        )
        if func is None:
            func = Function(source_id=source.id, name=func_data["name"])

        func.label = func_data.get("label", "")
        func.description = func_data.get("description", "")
        func.category = func_data.get("category", "未分类")
        func.parameters = func_data.get("parameters", [])
        func.output_type = func_data.get("output_type", "DataFrame")
        self._session.add(func)
        self._session.flush()

        # Replace columns
        (
            self._session.query(FunctionColumn)
            .filter(FunctionColumn.function_id == func.id)
            .delete()
        )
        for col_data in func_data.get("columns", []):
            col = FunctionColumn(
                function_id=func.id,
                name=col_data.get("name", ""),
                label=col_data.get("label", ""),
                type=col_data.get("type", ""),
                description=col_data.get("description", ""),
                nullable=col_data.get("nullable", True),
            )
            self._session.add(col)

    def upsert_source(self, source_data: dict) -> None:
        """Insert or update a source. Idempotent."""
        source = self._session.query(Source).filter(Source.name == source_data["name"]).first()
        if source is None:
            source = Source(name=source_data["name"])
        source.label = source_data.get("label", source_data["name"])
        source.description = source_data.get("description", "")
        source.url = source_data.get("url", "")
        source.enabled = source_data.get("enabled", True)
        source.config = source_data.get("config", {})
        self._session.add(source)


# ============================================
# Module-level convenience API
# ============================================

def _get_service() -> RegistryService:
    from cli_anything.daas.core.database import get_database

    db = get_database()
    session = db.get_session()
    return RegistryService(session)


def list_functions(source: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
    svc = _get_service()
    return svc.list_functions(source=source, category=category)


def search_functions(query: str, source: Optional[str] = None) -> list[dict]:
    svc = _get_service()
    return svc.search_functions(query, source=source)


def get_function_info(name: str) -> Optional[dict]:
    svc = _get_service()
    return svc.get_function_info(name)


def get_categories(source: Optional[str] = None) -> list[dict]:
    svc = _get_service()
    return svc.get_categories(source=source)


def get_category_functions(category: str, source: Optional[str] = None) -> list[dict]:
    svc = _get_service()
    return svc.get_category_functions(category, source=source)


def list_sources() -> list[dict]:
    svc = _get_service()
    return svc.list_sources()
