"""
RegistryService for AKShare function metadata.

Replaces registry.py module-level functions with a class that queries
the SQLAlchemy database. Maintains backward-compatible API surface so
akshare_cli.py callers need minimal changes.

All methods return dicts matching the original registry.json format.

Usage:
    from leader_mcp.database import get_database
    from leader_mcp.registry_service import RegistryService

    db = get_database()
    session = db.get_session()
    try:
        svc = RegistryService(session)
        results = svc.list_functions()
    finally:
        session.close()
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from fd_daas_mcp.models import Function, FunctionColumn

logger = logging.getLogger(__name__)


class RegistryService:
    """Query orchestration for AKShare function metadata.

    Takes a SQLAlchemy Session via constructor injection for testability.
    All five operations match the existing registry.py API surface:
    list, search, info, categories, categoryFunctions.
    """

    def __init__(self, session: Session):
        self._session = session

    def list_functions(self, category: Optional[str] = None) -> dict[str, dict]:
        """List all functions, optionally filtered by category.

        Args:
            category: If provided, only return functions in this category.

        Returns:
            Dict mapping function command names to their metadata dicts.
        """
        query = self._session.query(Function)
        if category:
            query = query.filter(Function.category == category)
        results = {}
        for func in query.order_by(Function.command).all():
            results[func.command] = func.to_dict()
        return results

    def search_functions(self, query: str) -> dict[str, dict]:
        """Search functions by name, category, or description.

        Args:
            query: Case-insensitive search term.

        Returns:
            Dict mapping matching function command names to metadata dicts.
        """
        q = f"%{query}%"
        rows = (
            self._session.query(Function)
            .filter(
                Function.command.ilike(q)
                | Function.category.ilike(q)
                | Function.description.ilike(q)
            )
            .order_by(Function.command)
            .all()
        )
        return {func.command: func.to_dict() for func in rows}

    def get_function_info(self, name: str) -> Optional[dict]:
        """Get full metadata for a single function.

        Args:
            name: The function command name.

        Returns:
            Dict with all metadata, or None if not found.
        """
        func = (
            self._session.query(Function)
            .filter(Function.command == name)
            .first()
        )
        if func is None:
            return None
        return func.to_dict()

    def get_categories(self) -> dict[str, int]:
        """List all categories with function counts, sorted by count descending.

        Returns:
            Dict mapping category name to function count.
        """
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
        """Get all functions in a specific category.

        Args:
            category: The category name.

        Returns:
            Dict mapping function command names to metadata dicts.
        """
        return self.list_functions(category=category)
