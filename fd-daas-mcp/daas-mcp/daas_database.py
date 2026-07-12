"""Database singleton for daas-mcp — SQLAlchemy engine + session factory.

Defaults to mcp/daas.db. Override with DAAS_DATABASE_URL env var.
"""
from __future__ import annotations

import os
import re
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
    process_database.py (now a sibling in this dir, relocated from the former
    process-mcp) so a relative DAAS_DATABASE_URL
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
                # Register a Python-side REGEXP function so entity-collection
                # rule filters can use `name_regex` via `Entity.name.op('REGEXP')`.
                # SQLite has no built-in REGEXP; this wires Python's `re` in.
                dbapi_conn.create_function(
                    "REGEXP", 2, lambda pattern, value: 1 if (value is not None and re.search(pattern, str(value)) is not None) else 0
                )
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        self._migrate_sources_category_id()
        self._migrate_collection_items_sort_order()
        self._migrate_sources_score()
        self._migrate_collection_items_score()
        self._migrate_functions_frequency()
        self._migrate_entity_collections_rule_script()

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

    def _migrate_sources_score(self) -> None:
        """Idempotent: add nullable `score` (REAL) to a pre-existing `sources`
        table. The default priority/quality weight for a datasource; NULL means
        unset. ponytail: same guard pattern as category_id / sort_order.
        """
        insp = inspect(self._engine)
        if "sources" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("sources")]
        if "score" in cols:
            return
        with self._engine.begin() as conn:
            conn.execute(text("ALTER TABLE sources ADD COLUMN score REAL"))

    def _migrate_collection_items_score(self) -> None:
        """Idempotent: add nullable `score` (REAL) to a pre-existing
        `datasource_collection_items` table. A per-collection override of the
        datasource's default score; NULL means inherit the datasource default.
        ponytail: same guard pattern as sort_order.
        """
        insp = inspect(self._engine)
        if "datasource_collection_items" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("datasource_collection_items")]
        if "score" in cols:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE datasource_collection_items ADD COLUMN score REAL")
            )

    def _migrate_functions_frequency(self) -> None:
        """Idempotent: add nullable `frequency` (VARCHAR(64)) to a pre-existing
        `daas_functions` table. Describes the data refresh cadence of a function
        (e.g. daily/weekly/monthly/quarterly/yearly/realtime/irregular); NULL
        means unset. ponytail: same guard pattern as score / sort_order.
        """
        insp = inspect(self._engine)
        if "daas_functions" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("daas_functions")]
        if "frequency" in cols:
            return
        with self._engine.begin() as conn:
            conn.execute(text("ALTER TABLE daas_functions ADD COLUMN frequency VARCHAR(64)"))

    def _migrate_entity_collections_rule_script(self) -> None:
        """Idempotent: add nullable `rule_script` (TEXT) to a pre-existing
        `entity_collections` table. Stores a repo-root-relative path to a Python
        rule script defining `members(ctx)` — the script analogue of `rule_json`.
        Mutually exclusive with `rule_json`. ponytail: same guard pattern as
        the other additive ALTERs.
        """
        insp = inspect(self._engine)
        if "entity_collections" not in insp.get_table_names():
            return
        cols = [c["name"] for c in insp.get_columns("entity_collections")]
        if "rule_script" in cols:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE entity_collections ADD COLUMN rule_script TEXT")
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
