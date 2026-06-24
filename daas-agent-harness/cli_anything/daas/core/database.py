"""
Database singleton for DAAS — SQLAlchemy engine + session factory.

Defaults to mcp/daas_registry.db (relative to project root).
Override with DATABASE_URL env var.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from cli_anything.daas.core.models import Base


class Database:
    """Singleton database accessor. Lazy-init on first get_session()."""

    _instance: "Database | None" = None

    def __init__(self, db_url: str | None = None):
        if db_url is None:
            db_url = self._default_url()
        self._engine = create_engine(db_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine)
        self._ensure_tables()

    @staticmethod
    def _default_url() -> str:
        """Resolve the default SQLite path relative to the project root."""
        # Try env override first
        url = os.environ.get("DATABASE_URL")
        if url:
            return url
        # Default: mcp/daas_registry.db from project root
        db_path = os.environ.get("DAAS_REGISTRY_DB", "mcp/daas_registry.db")
        return f"sqlite:///{db_path}"

    def _ensure_tables(self):
        Base.metadata.create_all(self._engine)

    def get_session(self) -> Session:
        return self._session_factory()

    @classmethod
    def get_instance(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_database() -> Database:
    return Database.get_instance()


def reset_database():
    """Reset the singleton (useful for tests)."""
    Database._instance = None
