"""
Database singleton for daas-mcp — SQLAlchemy engine + session factory.

Defaults to mcp/daas_registry.db. Override with DATABASE_URL env var.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models import Base


class Database:
    """Singleton database accessor."""

    _instance: "Database | None" = None

    def __init__(self, db_url: str | None = None):
        if db_url is None:
            db_url = self._default_url()
        self._engine = create_engine(db_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)

    @staticmethod
    def _default_url() -> str:
        url = os.environ.get("DATABASE_URL")
        if url:
            return url
        db_path = os.environ.get("DAAS_REGISTRY_DB", "../daas_registry.db")
        return f"sqlite:///{db_path}"

    def get_session(self) -> Session:
        return self._session_factory()

    @classmethod
    def get_instance(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_database() -> Database:
    return Database.get_instance()
