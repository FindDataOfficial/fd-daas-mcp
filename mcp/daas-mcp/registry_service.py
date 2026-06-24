"""
Registry query service for daas-mcp.

Query layer over SQLAlchemy models — search, detail, categories, list.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from models import Function, FunctionColumn, Source


class RegistryService:
    """Query orchestration for DAAS function metadata."""

    def __init__(self, session: Session):
        self._session = session

    def list_sources(self) -> list[dict]:
        sources = self._session.query(Source).order_by(Source.name).all()
        result = []
        for s in sources:
            cnt = (
                self._session.query(func.count(Function.id))
                .filter(Function.source_id == s.id)
                .scalar()
            )
            d = s.to_dict()
            d["function_count"] = cnt
            result.append(d)
        return result

    def search_functions(self, query: str, source: Optional[str] = None, limit: int = 20) -> list[dict]:
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
        results = q_obj.order_by(Source.name, Function.name).limit(limit).all()
        return [f.to_dict() for f in results]

    def get_function_detail(self, name: str) -> Optional[dict]:
        func = self._session.query(Function).filter(Function.name == name).first()
        if func is None:
            return None
        return func.to_dict()

    def list_categories(self, source: Optional[str] = None) -> list[dict]:
        q = (
            self._session.query(
                Source.name.label("source_name"),
                Function.category,
                func.count(Function.id).label("cnt"),
            )
            .join(Function.source)
        )
        if source:
            q = q.filter(Source.name == source)
        rows = (
            q.group_by(Source.name, Function.category)
            .order_by(Source.name, func.count(Function.id).desc())
            .all()
        )
        return [
            {"source": row.source_name, "category": row.category, "count": row.cnt}
            for row in rows
        ]
