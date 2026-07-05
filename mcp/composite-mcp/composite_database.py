"""Database + upstream-client helpers for composite-mcp.

Mirrors leader_database.py: SQLAlchemy engine + session factory over the
shared mcp/daas.db, CRUD for the four composite tables, a loader that
returns a composite's full definition, and a helper to build a FastMCP
Client for an upstream.

Usage:
    from composite_database import get_composite_db
    db = get_composite_db()
    session = db.get_session()
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Composite, CompositeChain, CompositeTool, Upstream

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "daas.db"


def _resolve_database_url(database_url: Optional[str]) -> str:
    """Resolve DAAS_DATABASE_URL, defaulting to mcp/daas.db.

    Relative sqlite:/// URLs are resolved against the repo root so the
    gateway spawn path (``uv run --directory mcp/composite-mcp``) doesn't
    resolve them against the composite-mcp cwd — otherwise
    ``sqlite:///mcp/daas.db`` resolves to ``mcp/composite-mcp/mcp/daas.db``
    (nonexistent) and composite-mcp crashes at startup with "unable to open
    database file". Mirrors ``gateway_database._resolve_database_url``.
    """
    if database_url is None:
        database_url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        rel = database_url[len("sqlite:///"):]
        if not os.path.isabs(rel):
            repo_root = _DEFAULT_DB_PATH.parent.parent
            database_url = f"sqlite:///{(repo_root / rel).resolve()}"
    return database_url


class CompositeDatabase:
    """SQLAlchemy engine + session factory + CRUD for the composite tables.

    Reads DAAS_DATABASE_URL env var; defaults to SQLite at mcp/daas.db.
    """

    def __init__(self, database_url: Optional[str] = None):
        resolved = _resolve_database_url(database_url)
        # ensure the default DB's parent dir exists when we fall back to it
        if resolved == f"sqlite:///{_DEFAULT_DB_PATH}":
            _DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._database_url = resolved
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

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
        logger.info("Composite DB initialized: %s", self._database_url)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    # ── composites ──────────────────────────────────────────────

    def list_composites(self) -> list[dict]:
        session = self.get_session()
        try:
            return [c.to_dict() for c in session.query(Composite).order_by(Composite.name).all()]
        finally:
            session.close()

    def get_composite_by_name(self, name: str) -> Optional[Composite]:
        session = self.get_session()
        try:
            return session.query(Composite).filter(Composite.name == name).first()
        finally:
            session.close()

    def create_composite(self, name: str, description: Optional[str] = None) -> dict:
        session = self.get_session()
        try:
            existing = session.query(Composite).filter(Composite.name == name).first()
            if existing:
                raise ValueError(f"composite {name!r} already exists")
            row = Composite(name=name, description=description)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    # ── upstreams ───────────────────────────────────────────────

    def list_upstreams(self, composite_id: int) -> list[dict]:
        session = self.get_session()
        try:
            return [
                u.to_dict()
                for u in session.query(Upstream)
                .filter(Upstream.composite_id == composite_id)
                .order_by(Upstream.key)
                .all()
            ]
        finally:
            session.close()

    def add_upstream(
        self,
        composite_id: int,
        key: str,
        transport: str,
        command: Optional[str] = None,
        args: Optional[list] = None,
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
        url: Optional[str] = None,
    ) -> dict:
        session = self.get_session()
        try:
            existing = (
                session.query(Upstream)
                .filter(Upstream.composite_id == composite_id, Upstream.key == key)
                .first()
            )
            if existing:
                raise ValueError(f"upstream {key!r} already exists in this composite")
            row = Upstream(
                composite_id=composite_id,
                key=key,
                transport=transport,
                command=command,
                args=args,
                env=env,
                cwd=cwd,
                url=url,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def remove_upstream(self, composite_id: int, key: str) -> dict:
        session = self.get_session()
        try:
            row = (
                session.query(Upstream)
                .filter(Upstream.composite_id == composite_id, Upstream.key == key)
                .first()
            )
            if not row:
                raise ValueError(f"upstream {key!r} not found")
            # cascade: drop tools referencing this upstream
            session.query(CompositeTool).filter(
                CompositeTool.composite_id == composite_id,
                CompositeTool.upstream_key == key,
            ).delete()
            session.delete(row)
            session.commit()
            return {"removed": key}
        finally:
            session.close()

    # ── composite tools (proxy selection) ───────────────────────

    def list_composite_tools(self, composite_id: int) -> list[dict]:
        session = self.get_session()
        try:
            return [
                t.to_dict()
                for t in session.query(CompositeTool)
                .filter(CompositeTool.composite_id == composite_id)
                .order_by(CompositeTool.upstream_key, CompositeTool.tool_name)
                .all()
            ]
        finally:
            session.close()

    def add_tool(
        self,
        composite_id: int,
        upstream_key: str,
        tool_name: str,
        alias: Optional[str] = None,
    ) -> dict:
        session = self.get_session()
        try:
            existing = (
                session.query(CompositeTool)
                .filter(
                    CompositeTool.composite_id == composite_id,
                    CompositeTool.upstream_key == upstream_key,
                    CompositeTool.tool_name == tool_name,
                )
                .first()
            )
            if existing:
                raise ValueError(
                    f"tool {tool_name!r} from {upstream_key!r} already in composite"
                )
            row = CompositeTool(
                composite_id=composite_id,
                upstream_key=upstream_key,
                tool_name=tool_name,
                alias=alias,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def remove_tool(self, composite_id: int, upstream_key: str, tool_name: str) -> dict:
        session = self.get_session()
        try:
            row = (
                session.query(CompositeTool)
                .filter(
                    CompositeTool.composite_id == composite_id,
                    CompositeTool.upstream_key == upstream_key,
                    CompositeTool.tool_name == tool_name,
                )
                .first()
            )
            if not row:
                raise ValueError(f"tool {tool_name!r} from {upstream_key!r} not found")
            session.delete(row)
            session.commit()
            return {"removed": tool_name, "upstream": upstream_key}
        finally:
            session.close()

    # ── chains ──────────────────────────────────────────────────

    def list_chains(self, composite_id: int) -> list[dict]:
        session = self.get_session()
        try:
            return [
                c.to_dict()
                for c in session.query(CompositeChain)
                .filter(CompositeChain.composite_id == composite_id)
                .order_by(CompositeChain.name)
                .all()
            ]
        finally:
            session.close()

    def add_chain(
        self,
        composite_id: int,
        name: str,
        steps: list,
        description: Optional[str] = None,
    ) -> dict:
        _validate_steps(steps)
        session = self.get_session()
        try:
            existing = (
                session.query(CompositeChain)
                .filter(
                    CompositeChain.composite_id == composite_id,
                    CompositeChain.name == name,
                )
                .first()
            )
            if existing:
                raise ValueError(f"chain {name!r} already exists in this composite")
            row = CompositeChain(
                composite_id=composite_id,
                name=name,
                description=description,
                steps=steps,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def remove_chain(self, composite_id: int, name: str) -> dict:
        session = self.get_session()
        try:
            row = (
                session.query(CompositeChain)
                .filter(
                    CompositeChain.composite_id == composite_id,
                    CompositeChain.name == name,
                )
                .first()
            )
            if not row:
                raise ValueError(f"chain {name!r} not found")
            session.delete(row)
            session.commit()
            return {"removed": name}
        finally:
            session.close()

    # ── loader ──────────────────────────────────────────────────

    def load_composite(self, name: str) -> Optional[dict]:
        """Return a composite's full definition: {composite, upstreams, tools, chains}."""
        comp = self.get_composite_by_name(name)
        if comp is None:
            return None
        return {
            "composite": comp.to_dict(),
            "upstreams": self.list_upstreams(comp.id),
            "tools": self.list_composite_tools(comp.id),
            "chains": self.list_chains(comp.id),
        }


# ═══════════════════════════════════════════════════════════════
# chain step validation
# ═══════════════════════════════════════════════════════════════


def _validate_steps(steps: list) -> None:
    """Reject chain definitions that aren't linear pipelines of upstream calls.

    Each step must be {upstream, tool, input} with input a dict. No branching
    or conditionals — v1 is linear only.
    """
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty list")
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {i} must be an object")
        if "upstream" not in step or "tool" not in step:
            raise ValueError(f"step {i} must have 'upstream' and 'tool'")
        if "input" in step and not isinstance(step["input"], dict):
            raise ValueError(f"step {i} 'input' must be an object")
        # branch/conditional constructs are rejected by structure: only
        # upstream/tool/input keys are meaningful; extra keys like 'if'/'branch'
        # are treated as a malformed step.
        allowed = {"upstream", "tool", "input"}
        extra = set(step.keys()) - allowed
        if extra & {"if", "branch", "switch", "loop", "for", "while"}:
            raise ValueError(
                f"step {i} uses unsupported control-flow construct {sorted(extra)}; "
                "v1 chains are linear only"
            )


# ═══════════════════════════════════════════════════════════════
# upstream client helper
# ═══════════════════════════════════════════════════════════════


def build_transport(upstream: dict):
    """Build a FastMCP transport for an upstream dict (from load_composite)."""
    if upstream["transport"] == "http":
        return StreamableHttpTransport(upstream["url"])
    return StdioTransport(
        command=upstream["command"],
        args=upstream.get("args") or [],
        env=upstream.get("env"),
        cwd=upstream.get("cwd"),
    )


def build_client(upstream: dict) -> Client:
    """Build a fresh FastMCP Client for an upstream dict (from load_composite).

    Caller is responsible for `async with client:`. Opened per-call — fine for
    chains and list_available_tools (not the hot path; proxy tools use
    create_proxy's own persistent client).
    # ponytail: per-call client open; persistent client if spawn latency matters.
    """
    return Client(build_transport(upstream))


# ═══════════════════════════════════════════════════════════════
# module singleton
# ═══════════════════════════════════════════════════════════════

_composite_db: Optional[CompositeDatabase] = None


def get_composite_db(database_url: Optional[str] = None) -> CompositeDatabase:
    global _composite_db
    if _composite_db is None:
        _composite_db = CompositeDatabase(database_url)
        _composite_db.init_db()
    return _composite_db


def reset_composite_db() -> None:
    global _composite_db
    if _composite_db is not None:
        _composite_db.dispose()
    _composite_db = None
