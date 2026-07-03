"""Database + CRUD for leader-mcp's CrewAI specialist agents + data workflows.

Mirrors gateway_database.py: SQLAlchemy engine + session factory over the
shared mcp/daas.db, with `PRAGMA foreign_keys=ON` per connection so the
workflow→step and run→result `ON DELETE CASCADE`s fire. CRUD for:

  - `specialist_agents` (create/list/get; `upstream` validated against
    `leader_upstreams`, `upstream_missing` surfaced on list);
  - `workflows` + `workflow_steps` (create/get/list/add-step; `agent` validated
    against `specialist_agents`; auto `sort_order`);
  - `workflow_runs` + `workflow_step_results` (start/finish/upsert/get; unique
    on (run_id, step_sort_order) → idempotent step re-run).

`output_json` is capped at 1 MB (truncated with a `_truncated` flag) so a
year of daily prices doesn't bloat the DB. Identifiers (agent/workflow/model
names) are validated against a safe pattern; all other values are bind params.

Usage:
    from workflow_database import get_workflow_db
    db = get_workflow_db()
    db.create_specialist_agent(name="edgar-agent", upstream="edgartools", ...)
    db.create_workflow(name="aapl-dd", description="...")
    db.add_workflow_step(workflow_name="aapl-dd", agent="edgar-agent", request="...")
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from models import (
    Base,
    SpecialistAgent,
    Workflow,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "daas.db"

# 1 MB cap on stored step output (a year of daily prices is ~tens of KB; this
# leaves headroom and prevents a runaway upstream from bloating daas.db).
_MAX_OUTPUT_BYTES = 1 * 1024 * 1024

# Safe identifier pattern for user-provided names (agent / workflow / model).
# Allows letters, digits, underscore, hyphen; must start with a letter.
_IDENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")


def _validate_ident(name: str, field: str) -> None:
    if not name or not _IDENT_RE.match(name):
        raise ValueError(
            f"invalid {field} '{name}': must match {_IDENT_RE.pattern} "
            f"(letters, digits, underscore, hyphen; start with a letter)"
        )


def _resolve_database_url(database_url: Optional[str]) -> str:
    """Resolve DAAS_DATABASE_URL, defaulting to mcp/daas.db.

    Relative sqlite:/// URLs are resolved against the repo root so the
    `--run-workflow` / seed / cron paths work under `uv run --directory`.
    Mirrors gateway_database._resolve_database_url.
    """
    if database_url is None:
        database_url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        rel = database_url[len("sqlite:///"):]
        if not os.path.isabs(rel):
            repo_root = _DEFAULT_DB_PATH.parent.parent
            database_url = f"sqlite:///{(repo_root / rel).resolve()}"
    return database_url


def _cap_output(value) -> str:
    """JSON-encode a step output, capping at _MAX_OUTPUT_BYTES.

    When the encoding exceeds the cap, store a `{"_truncated": true, "len": N}`
    marker instead of the full payload (the data is re-fetchable via
    call_data_mcp)."""
    raw = json.dumps(value, default=str)
    if len(raw.encode("utf-8")) <= _MAX_OUTPUT_BYTES:
        return raw
    return json.dumps({"_truncated": True, "len": len(raw), "preview": raw[:512]})


class WorkflowDatabase:
    """SQLAlchemy engine + session factory + CRUD for the workflow domain."""

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
        if self._database_url.startswith("sqlite"):
            @event.listens_for(self._engine, "connect")
            def _fk_on(dbapi_conn, _):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        logger.info("Workflow DB initialized: %s", self._database_url)

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    # ── upstream lookup (soft-ref validation) ──────────────────

    @staticmethod
    def _upstream_names() -> set:
        """Names of all leader_upstreams (enabled + disabled) for soft-ref checks."""
        # Lazy import to avoid a hard gateway_database dependency at import time.
        from gateway_database import get_gateway_db
        try:
            rows = get_gateway_db().list_upstreams(include_disabled=True)
        except Exception:  # noqa: BLE001 — if the gateway DB isn't up yet, treat as empty
            return set()
        return {r["name"] for r in rows}

    # ── specialist agents ──────────────────────────────────────

    def create_specialist_agent(
        self,
        name: str,
        upstream: str,
        role: str,
        goal: str,
        backstory: Optional[str] = None,
        model: Optional[str] = None,
        enabled: bool = True,
    ) -> dict:
        """Insert a specialist agent. Validates `upstream` exists in
        `leader_upstreams` and `name`/`model` are safe identifiers. Rejects
        duplicate `name`."""
        _validate_ident(name, "specialist agent name")
        if model:
            _validate_ident(model, "model name")
        if upstream not in self._upstream_names():
            raise ValueError(f"upstream '{upstream}' not found in leader_upstreams")
        session = self.get_session()
        try:
            existing = session.query(SpecialistAgent).filter(SpecialistAgent.name == name).first()
            if existing is not None:
                raise ValueError(f"specialist agent '{name}' already exists")
            row = SpecialistAgent(
                name=name,
                upstream=upstream,
                role=role,
                goal=goal,
                backstory=backstory,
                model=model,
                enabled=bool(enabled),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def upsert_specialist_agent(
        self,
        name: str,
        upstream: str,
        role: str,
        goal: str,
        backstory: Optional[str] = None,
        model: Optional[str] = None,
        enabled: bool = True,
        preserve_model: bool = True,
    ) -> dict:
        """Insert or update a specialist agent by name (used by the seed).

        Validates `upstream` exists in `leader_upstreams`. On update, refreshes
        role/goal/backstory/enabled; when `preserve_model` is True and the
        existing row already has a model, it is kept (so re-seeding does not
        clobber a user's per-agent model choice).
        """
        _validate_ident(name, "specialist agent name")
        if model:
            _validate_ident(model, "model name")
        if upstream not in self._upstream_names():
            raise ValueError(f"upstream '{upstream}' not found in leader_upstreams")
        session = self.get_session()
        try:
            row = session.query(SpecialistAgent).filter(SpecialistAgent.name == name).first()
            if row is None:
                row = SpecialistAgent(
                    name=name, upstream=upstream, role=role, goal=goal,
                    backstory=backstory, model=model, enabled=bool(enabled),
                )
                session.add(row)
            else:
                row.upstream = upstream
                row.role = role
                row.goal = goal
                row.backstory = backstory
                row.enabled = bool(enabled)
                if not (preserve_model and row.model):
                    row.model = model
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def get_specialist_agent(self, name: str) -> Optional[dict]:
        session = self.get_session()
        try:
            row = session.query(SpecialistAgent).filter(SpecialistAgent.name == name).first()
            if row is None:
                return None
            missing = row.upstream not in self._upstream_names()
            return row.to_dict(upstream_missing=missing)
        finally:
            session.close()

    def list_specialist_agents(self) -> list[dict]:
        session = self.get_session()
        try:
            upstreams = self._upstream_names()
            rows = session.query(SpecialistAgent).order_by(SpecialistAgent.name).all()
            return [r.to_dict(upstream_missing=r.upstream not in upstreams) for r in rows]
        finally:
            session.close()

    # ── workflows + steps ─────────────────────────────────────

    def create_workflow(self, name: str, description: Optional[str] = None) -> dict:
        _validate_ident(name, "workflow name")
        session = self.get_session()
        try:
            existing = session.query(Workflow).filter(Workflow.name == name).first()
            if existing is not None:
                raise ValueError(f"workflow '{name}' already exists")
            row = Workflow(name=name, description=description)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def get_workflow(self, name: str) -> Optional[dict]:
        """Workflow + ordered steps, or None if not found."""
        session = self.get_session()
        try:
            row = session.query(Workflow).filter(Workflow.name == name).first()
            if row is None:
                return None
            d = row.to_dict()
            d["steps"] = [s.to_dict() for s in (row.steps or [])]
            return d
        finally:
            session.close()

    def list_workflows(self) -> list[dict]:
        session = self.get_session()
        try:
            rows = session.query(Workflow).order_by(Workflow.name).all()
            return [r.to_dict() for r in rows]
        finally:
            session.close()

    def get_workflow_steps(self, workflow_name: str) -> list[dict]:
        session = self.get_session()
        try:
            wf = session.query(Workflow).filter(Workflow.name == workflow_name).first()
            if wf is None:
                return []
            return [s.to_dict() for s in (wf.steps or [])]
        finally:
            session.close()

    def add_workflow_step(
        self,
        workflow_name: str,
        agent: str,
        request: str,
        depends_on: Optional[str] = None,
        on_fail: str = "continue",
        model: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> dict:
        """Add a step. Validates `agent` exists in specialist_agents. Auto-assigns
        `sort_order` = max(existing)+1 when omitted. `on_fail` ∈ {continue, stop}."""
        if on_fail not in ("continue", "stop"):
            raise ValueError(f"on_fail must be 'continue' or 'stop', got '{on_fail}'")
        if model:
            _validate_ident(model, "model name")
        session = self.get_session()
        try:
            wf = session.query(Workflow).filter(Workflow.name == workflow_name).first()
            if wf is None:
                raise ValueError(f"workflow '{workflow_name}' not found")
            agent_row = session.query(SpecialistAgent).filter(SpecialistAgent.name == agent).first()
            if agent_row is None:
                raise ValueError(f"specialist agent '{agent}' not found")
            if sort_order is None:
                existing = wf.steps or []
                sort_order = (max(s.sort_order for s in existing) + 1) if existing else 1
            row = WorkflowStep(
                workflow_id=wf.id,
                sort_order=sort_order,
                agent=agent,
                request=request,
                depends_on=depends_on,
                on_fail=on_fail,
                model=model,
                enabled=True,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def get_step(self, workflow_name: str, sort_order: int) -> Optional[dict]:
        session = self.get_session()
        try:
            wf = session.query(Workflow).filter(Workflow.name == workflow_name).first()
            if wf is None:
                return None
            row = (
                session.query(WorkflowStep)
                .filter(WorkflowStep.workflow_id == wf.id, WorkflowStep.sort_order == sort_order)
                .first()
            )
            return row.to_dict() if row else None
        finally:
            session.close()

    # ── run state ──────────────────────────────────────────────

    def start_run(self, workflow_id: int, fresh: bool = False, status: str = "in_progress") -> dict:
        """Begin (or resume) a run. If `fresh`, always create a new run. Else,
        if an `in_progress` run exists for this workflow, return it (resume)."""
        session = self.get_session()
        try:
            if not fresh:
                existing = (
                    session.query(WorkflowRun)
                    .filter(
                        WorkflowRun.workflow_id == workflow_id,
                        WorkflowRun.status == "in_progress",
                    )
                    .order_by(WorkflowRun.id.desc())
                    .first()
                )
                if existing is not None:
                    return existing.to_dict()
            row = WorkflowRun(workflow_id=workflow_id, status=status)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def finish_run(self, run_id: int, status: str) -> Optional[dict]:
        session = self.get_session()
        try:
            row = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if row is None:
                return None
            row.status = status
            row.finished_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def upsert_step_result(
        self,
        run_id: int,
        step_sort_order: int,
        status: str,
        output,
        error: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> dict:
        """Upsert a step result on (run_id, step_sort_order). Re-running a step
        overwrites the prior result (idempotent). `output` is JSON-capped."""
        session = self.get_session()
        try:
            row = (
                session.query(WorkflowStepResult)
                .filter(
                    WorkflowStepResult.run_id == run_id,
                    WorkflowStepResult.step_sort_order == step_sort_order,
                )
                .first()
            )
            output_json = _cap_output(output) if output is not None else None
            meta_json = json.dumps(meta, default=str) if meta else None
            if row is None:
                row = WorkflowStepResult(
                    run_id=run_id,
                    step_sort_order=step_sort_order,
                    status=status,
                    output_json=output_json,
                    error=error,
                    meta_json=meta_json,
                )
                session.add(row)
            else:
                row.status = status
                row.output_json = output_json
                row.error = error
                row.meta_json = meta_json
                row.ran_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def get_run(self, run_id: int) -> Optional[dict]:
        """Run + ordered step results."""
        session = self.get_session()
        try:
            row = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if row is None:
                return None
            d = row.to_dict()
            wf = session.query(Workflow).filter(Workflow.id == row.workflow_id).first()
            d["workflow_name"] = wf.name if wf else None
            d["steps"] = [r.to_dict() for r in (row.results or [])]
            return d
        finally:
            session.close()

    def list_step_results(self, run_id: int) -> list[dict]:
        session = self.get_session()
        try:
            run = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run is None:
                return []
            return [r.to_dict() for r in (run.results or [])]
        finally:
            session.close()

    def get_step_result(self, run_id: int, step_sort_order: int) -> Optional[dict]:
        session = self.get_session()
        try:
            row = (
                session.query(WorkflowStepResult)
                .filter(
                    WorkflowStepResult.run_id == run_id,
                    WorkflowStepResult.step_sort_order == step_sort_order,
                )
                .first()
            )
            return row.to_dict() if row else None
        finally:
            session.close()


# ═══════════════════════════════════════════════════════════════
# module singleton
# ═══════════════════════════════════════════════════════════════

_workflow_db: Optional[WorkflowDatabase] = None


def get_workflow_db(database_url: Optional[str] = None) -> WorkflowDatabase:
    global _workflow_db
    if _workflow_db is None:
        _workflow_db = WorkflowDatabase(database_url)
        _workflow_db.init_db()
    return _workflow_db


def reset_workflow_db() -> None:
    global _workflow_db
    if _workflow_db is not None:
        _workflow_db.dispose()
    _workflow_db = None
