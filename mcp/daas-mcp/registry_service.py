"""
Registry query service for daas-mcp.

Query layer over SQLAlchemy models — search, detail, categories, list.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from models import DaasFunction, DaasFunctionColumn, DaasSource


class RegistryService:
    """Query orchestration for DAAS function metadata."""

    def __init__(self, session: Session):
        self._session = session

    def list_sources(self) -> list[dict]:
        sources = self._session.query(DaasSource).order_by(DaasSource.name).all()
        result = []
        for s in sources:
            cnt = (
                self._session.query(func.count(DaasFunction.id))
                .filter(DaasFunction.source_id == s.id)
                .scalar()
            )
            d = s.to_dict()
            d["function_count"] = cnt
            result.append(d)
        return result

    def search_functions(self, query: str, source: Optional[str] = None, limit: int = 20) -> list[dict]:
        q = f"%{query}%"
        q_obj = (
            self._session.query(DaasFunction)
            .join(DaasSource)
            .filter(
                or_(
                    DaasFunction.name.like(q),
                    DaasFunction.category.like(q),
                    DaasFunction.description.like(q),
                )
            )
        )
        if source:
            q_obj = q_obj.filter(DaasSource.name == source)
        results = q_obj.order_by(DaasSource.name, DaasFunction.name).limit(limit).all()
        return [f.to_dict() for f in results]

    def get_function_detail(self, name: str) -> Optional[dict]:
        func = self._session.query(DaasFunction).filter(DaasFunction.name == name).first()
        if func is None:
            return None
        return func.to_dict()

    def list_categories(self, source: Optional[str] = None) -> list[dict]:
        q = (
            self._session.query(
                DaasSource.name.label("source_name"),
                DaasFunction.category,
                func.count(DaasFunction.id).label("cnt"),
            )
            .join(DaasFunction.source)
        )
        if source:
            q = q.filter(DaasSource.name == source)
        rows = (
            q.group_by(DaasSource.name, DaasFunction.category)
            .order_by(DaasSource.name, func.count(DaasFunction.id).desc())
            .all()
        )
        return [
            {"source": row.source_name, "category": row.category, "count": row.cnt}
            for row in rows
        ]
