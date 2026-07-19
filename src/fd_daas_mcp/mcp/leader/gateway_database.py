"""Database + upstream-client helpers for leader-mcp's data gateway.

Mirrors leader_database.py / composite_database.py: SQLAlchemy engine + session
factory over the shared mcp/daas.db, CRUD for the `leader_upstreams` table,
and a helper to build a per-call fastmcp.Client for an upstream.

The `leader_upstreams` table holds the stdio launch config for each
data-fetch MCP (yfinance, edgartools, …) so leader-mcp can launch them on
demand after they are removed from `.mcp.json`.

Usage:
    from gateway_database import get_gateway_db, build_client
    db = get_gateway_db()
    row = db.get_upstream("yfinance")
    async with build_client(row) as client:
        tools = await client.list_tools()
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from fd_daas_mcp.models import Base, LeaderUpstream

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "daas.db"


def _resolve_database_url(database_url: Optional[str]) -> str:
    """Resolve DAAS_DATABASE_URL, defaulting to mcp/daas.db.

    Relative sqlite:/// URLs are resolved against the repo root so the
    `--run-rule` / seed / cron paths work under `uv run --directory`.
    """
    if database_url is None:
        database_url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        # relative path → resolve against repo root (parent of mcp/)
        rel = database_url[len("sqlite:///"):]
        if not os.path.isabs(rel):
            repo_root = _DEFAULT_DB_PATH.parent.parent
            database_url = f"sqlite:///{(repo_root / rel).resolve()}"
    return database_url


class GatewayDatabase:
    """SQLAlchemy engine + session factory + CRUD for leader_upstreams."""

    def __init__(self, database_url: Optional[str] = None):
        self._database_url = _resolve_database_url(database_url)
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
        # PRAGMA foreign_keys=ON per connection (no FKs on this table today,
        # but set for consistency with the project's daas/process MCPs).
        if self._database_url.startswith("sqlite"):
            @event.listens_for(self._engine, "connect")
            def _fk_on(dbapi_conn, _):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        logger.info("Gateway DB initialized: %s", self._database_url)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    # ── CRUD ────────────────────────────────────────────────────

    def upsert_upstream(
        self,
        name: str,
        transport: str = "stdio",
        command: Optional[str] = None,
        args: Optional[list] = None,
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
        enabled: bool = True,
        description: Optional[str] = None,
    ) -> dict:
        """Insert or update a leader_upstreams row by name."""
        session = self.get_session()
        try:
            row = session.query(LeaderUpstream).filter(LeaderUpstream.name == name).first()
            if row is None:
                row = LeaderUpstream(name=name)
                session.add(row)
            row.transport = transport
            row.command = command
            row.args_json = args or []
            row.env_json = env or None
            row.cwd = cwd
            row.enabled = bool(enabled)
            if description is not None:
                row.description = description
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def get_upstream(self, name: str) -> Optional[dict]:
        session = self.get_session()
        try:
            row = session.query(LeaderUpstream).filter(LeaderUpstream.name == name).first()
            return row.to_dict() if row else None
        finally:
            session.close()

    def list_upstreams(self, include_disabled: bool = False) -> list[dict]:
        session = self.get_session()
        try:
            q = session.query(LeaderUpstream).order_by(LeaderUpstream.name)
            if not include_disabled:
                q = q.filter(LeaderUpstream.enabled == True)  # noqa: E712
            return [r.to_dict() for r in q.all()]
        finally:
            session.close()

    def delete_upstream(self, name: str) -> bool:
        session = self.get_session()
        try:
            row = session.query(LeaderUpstream).filter(LeaderUpstream.name == name).first()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    def set_enabled(self, name: str, enabled: bool) -> Optional[dict]:
        session = self.get_session()
        try:
            row = session.query(LeaderUpstream).filter(LeaderUpstream.name == name).first()
            if row is None:
                return None
            row.enabled = bool(enabled)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()


# ═══════════════════════════════════════════════════════════════
# upstream client helper
# ═══════════════════════════════════════════════════════════════


def build_client(upstream: dict) -> Client:
    """Build a fresh fastmcp Client for an upstream dict (from get_upstream /
    list_upstreams). Caller is responsible for `async with client:`.

    Per-call open — fine for on-demand data fetch (not a hot path). Add a
    persistent client if spawn latency ever hurts.

    For stdio: if `env` is provided, it is MERGED with the current process
    environment (so PATH / DAAS_DATABASE_URL are preserved); if absent, the
    subprocess inherits the parent env outright. Data-fetch MCPs rely on
    inheriting the parent env + their own dotenv load, so seeded rows carry
    no env and inherit cleanly.
    """
    if upstream.get("transport") == "http" and upstream.get("url"):
        return Client(StreamableHttpTransport(upstream["url"]))

    env_override = upstream.get("env") or None
    if env_override:
        env_override = {**os.environ, **env_override}

    return Client(
        StdioTransport(
            command=upstream.get("command"),
            args=upstream.get("args") or [],
            env=env_override,
            cwd=upstream.get("cwd"),
        )
    )


# ═══════════════════════════════════════════════════════════════
# module singleton
# ═══════════════════════════════════════════════════════════════

_gateway_db: Optional[GatewayDatabase] = None


def get_gateway_db(database_url: Optional[str] = None) -> GatewayDatabase:
    global _gateway_db
    if _gateway_db is None:
        _gateway_db = GatewayDatabase(database_url)
        _gateway_db.init_db()
    return _gateway_db


def reset_gateway_db() -> None:
    global _gateway_db
    if _gateway_db is not None:
        _gateway_db.dispose()
    _gateway_db = None
