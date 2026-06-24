"""
Registry module for AKShare function metadata.

Backed by SQLAlchemy database (default SQLite, swappable via DATABASE_URL).
Maintains backward-compatible API: list_functions, search_functions,
get_function_info, get_categories, get_category_functions.

All functions return dicts matching the original registry.json format.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from cli_anything.akshare.core.models import Function, FunctionColumn

logger = logging.getLogger(__name__)


class RegistryService:
    """Query orchestration for AKShare function metadata.

    Takes a SQLAlchemy Session via constructor injection for testability.
    All five operations match the original registry.py API surface.
    """

    def __init__(self, session: Session):
        self._session = session

    def list_functions(self, category: Optional[str] = None) -> dict[str, dict]:
        """List all functions, optionally filtered by category."""
        query = self._session.query(Function)
        if category:
            query = query.filter(Function.category == category)
        results = {}
        for func in query.order_by(Function.command).all():
            results[func.command] = func.toDict()
        return results

    def search_functions(self, query: str) -> dict[str, dict]:
        """Search functions by name, category, or description (case-insensitive)."""
        from sqlalchemy import or_
        q = f"%{query}%"
        rows = (
            self._session.query(Function)
            .filter(
                or_(Function.command.like(q), Function.category.like(q), Function.description.like(q))
            )
            .order_by(Function.command)
            .all()
        )
        return {func.command: func.toDict() for func in rows}

    def get_function_info(self, name: str) -> Optional[dict]:
        """Get full metadata for a single function, or None if not found."""
        func = (
            self._session.query(Function)
            .filter(Function.command == name)
            .first()
        )
        if func is None:
            return None
        return func.toDict()

    def get_categories(self) -> dict[str, int]:
        """List all categories with function counts, sorted by count descending."""
        rows = (
            self._session.query(
                Function.category,
                func.count(Function.id).label("cnt"),
            )
            .group_by(Function.category)
            .order_by(func.count(Function.id).desc())
            .all()
        )
        return {row.category: row.cnt for row in rows}

    def get_category_functions(self, category: str) -> dict[str, dict]:
        """Get all functions in a specific category."""
        return self.list_functions(category=category)


# ============================================
# Module-level convenience API (backward-compatible with original registry.py)
# ============================================

def _get_service() -> RegistryService:
    """Get a RegistryService backed by the singleton Database."""
    from cli_anything.akshare.core.database import get_database
    db = get_database()
    session = db.get_session()
    return RegistryService(session)


def get_registry() -> dict[str, dict]:
    """Return the full registry as a dict (for backward compatibility)."""
    svc = _get_service()
    return svc.list_functions()


def list_functions(category: Optional[str] = None) -> dict[str, dict]:
    svc = _get_service()
    return svc.list_functions(category)


def search_functions(query: str) -> dict[str, dict]:
    svc = _get_service()
    return svc.search_functions(query)


def get_function_info(name: str) -> Optional[dict]:
    svc = _get_service()
    return svc.get_function_info(name)


def get_categories() -> dict[str, int]:
    svc = _get_service()
    return svc.get_categories()


def get_category_functions(category: str) -> dict[str, dict]:
    svc = _get_service()
    return svc.get_category_functions(category)
