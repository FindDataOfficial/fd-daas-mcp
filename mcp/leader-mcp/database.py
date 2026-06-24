"""
Database module for AKShare registry.

Provides SQLAlchemy engine and session management. Reads DATABASE_URL
from environment (defaults to SQLite at metadata/registry.db). Auto-creates
tables on first use.

Usage:
    from database import get_database

    db = get_database()
    session = db.get_session()
    try:
        # ... queries ...
        session.commit()
    finally:
        session.close()
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from unified_models import Base

logger = logging.getLogger(__name__)

# Default SQLite path relative to the akshare-agent-harness package
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / "akshare-agent-harness" / "cli_anything" / "akshare" / "metadata"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "registry.db"


class Database:
    """SQLAlchemy engine and session factory.

    Reads DATABASE_URL env var; defaults to SQLite at metadata/registry.db.
    Singleton — use get_database() instead of constructing directly.
    """

    def __init__(self, database_url: Optional[str] = None):
        if database_url is None:
            database_url = os.environ.get(
                "AKSHARE_DATABASE_URL",
                f"sqlite:///{_DEFAULT_DB_PATH}",
            )
        self._database_url = database_url
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @property
    def database_url(self) -> str:
        return self._database_url

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self.init_db()
        assert self._engine is not None
        return self._engine

    def get_session(self) -> Session:
        """Get a new SQLAlchemy session. Caller is responsible for closing."""
        if self._session_factory is None:
            self.init_db()
        assert self._session_factory is not None
        return self._session_factory()

    def init_db(self) -> None:
        """Initialize the engine and create all tables."""
        self._engine = create_engine(
            self._database_url,
            echo=False,
            # SQLite needs connect_args for WAL mode and foreign keys
            connect_args=(
                {"check_same_thread": False}
                if self._database_url.startswith("sqlite")
                else {}
            ),
        )
        self._session_factory = sessionmaker(bind=self._engine)

        # Auto-create tables if they don't exist
        Base.metadata.create_all(self._engine)
        logger.info("Database initialized: %s", self._database_url)

    def dispose(self) -> None:
        """Close the engine and release all connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database disposed")


# Module-level singleton
_database: Optional[Database] = None


def get_database(database_url: Optional[str] = None) -> Database:
    """Get or create the singleton Database instance.

    Args:
        database_url: Override the default DATABASE_URL. Only used on first call.

    Returns:
        The singleton Database instance.
    """
    global _database
    if _database is None:
        _database = Database(database_url)
        _database.init_db()
    return _database


def reset_database() -> None:
    """Dispose and reset the singleton. Useful for testing."""
    global _database
    if _database is not None:
        _database.dispose()
    _database = None
