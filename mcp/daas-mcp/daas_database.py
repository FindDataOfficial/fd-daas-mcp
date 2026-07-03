"""Database singleton for daas-mcp — SQLAlchemy engine + session factory.

Defaults to mcp/daas.db. Override with DAAS_DATABASE_URL env var.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from models import Base

# Absolute default DB location (mcp/daas.db) — file-anchored so cwd doesn't
# matter. The writer is spawned via `uv run --directory mcp/daas-mcp`, which
# sets its cwd to mcp/daas-mcp/, so relative sqlite:/// paths would otherwise
# resolve against the wrong directory.
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "daas.db"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_url(url: str) -> str:
    """Resolve a relative sqlite:/// path against the repo root. Pass through
    otherwise (absolute paths, :memory:, non-sqlite URLs). Mirrors
    process-mcp/process_database.py so a relative DAAS_DATABASE_URL
    (e.g. `sqlite:///mcp/daas.db`) works regardless of the process cwd.
    """
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        path = url[len("sqlite:///"):]
        if path and path != ":memory:" and not os.path.isabs(path):
            return f"sqlite:///{(_REPO_ROOT / path).resolve()}"
    return url


class Database:
    """Singleton database accessor."""

    _instance: "Database | None" = None

    def __init__(self, db_url: str | None = None):
        if db_url is None:
            db_url = self._default_url()
        db_url = _resolve_url(db_url)
        self._engine = create_engine(db_url, echo=False)
        # SQLite ignores ON DELETE CASCADE unless PRAGMA foreign_keys=ON.
        # ponytail: enable per-connection so cascade deletes actually fire.
        if self._engine.dialect.name == "sqlite":
            @event.listens_for(self._engine, "connect")
            def _enable_fk(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        self._migrate_sources_category_id()
        self._migrate_collection_items_sort_order()

    def _migrate_sources_category_id(self) -> None:
        """Idempotent: add `category_id` to a pre-existing `sources` table.

        create_all adds the column on fresh DBs but won't ALTER an existing
        table. SQLite supports ADD COLUMN; guard on PRAGMA table_info so it
        runs exactly once. ponytail: additive only, no destructive migration.
        """
        insp = inspect(self._engine)
        if "sources" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("sources")]
        if "category_id" in cols:
            return
        with self._engine.begin() as conn:
            conn.execute(text("ALTER TABLE sources ADD COLUMN category_id INTEGER"))

    def _migrate_collection_items_sort_order(self) -> None:
        """Idempotent: add `sort_order` to a pre-existing
        `datasource_collection_items` table. ponytail: same pattern as category_id.
        """
        insp = inspect(self._engine)
        if "datasource_collection_items" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("datasource_collection_items")]
        if "sort_order" in cols:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE datasource_collection_items "
                    "ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
                )
            )

    @staticmethod
    def _default_url() -> str:
        url = os.environ.get("DAAS_DATABASE_URL")
        if url:
            return url
        # Legacy: DAAS_REGISTRY_DB is a filesystem path (not a URL). Wrapped
        # to a sqlite URL; _resolve_url then anchors any relative path to the
        # repo root.
        reg_db = os.environ.get("DAAS_REGISTRY_DB")
        if reg_db:
            return f"sqlite:///{reg_db}"
        # Absolute default — file-anchored so cwd doesn't matter.
        return f"sqlite:///{_DEFAULT_DB_PATH}"

    def get_session(self) -> Session:
        return self._session_factory()

    @property
    def engine(self):
        """Underlying SQLAlchemy engine — used by pipeline_tools for raw
        sqlite upserts into scraw_<slug> tables."""
        return self._engine

    @classmethod
    def get_instance(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_database() -> Database:
    return Database.get_instance()
