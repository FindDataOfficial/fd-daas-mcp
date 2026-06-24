"""
Unified database for the Leader MCP — connects all harness registries
into one database. Supports SQLite (default) or PostgreSQL/MySQL.

Usage:
    from leader_mcp.leader_database import get_leader_db

    db = get_leader_db()
    session = db.get_session()
    try:
        results = session.query(Function).filter(Function.harness == "akshare").all()
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

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "daas.db"


class LeaderDatabase:
    """SQLAlchemy engine + session factory for the unified multi-harness DB.

    Reads LEADER_MCP_DATABASE_URL env var; defaults to SQLite at mcp/daas.db.
    """

    def __init__(self, database_url: Optional[str] = None):
        if database_url is None:
            _DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            database_url = os.environ.get(
                "LEADER_MCP_DATABASE_URL",
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
        if self._session_factory is None:
            self.init_db()
        assert self._session_factory is not None
        return self._session_factory()

    def init_db(self) -> None:
        self._engine = create_engine(
            self._database_url,
            echo=False,
            connect_args=(
                {"check_same_thread": False}
                if self._database_url.startswith("sqlite")
                else {}
            ),
        )
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        logger.info("Leader DB initialized: %s", self._database_url)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Module-level singleton
_leader_db: Optional[LeaderDatabase] = None


def get_leader_db(database_url: Optional[str] = None) -> LeaderDatabase:
    global _leader_db
    if _leader_db is None:
        _leader_db = LeaderDatabase(database_url)
        _leader_db.init_db()
    return _leader_db


def reset_leader_db() -> None:
    global _leader_db
    if _leader_db is not None:
        _leader_db.dispose()
    _leader_db = None
