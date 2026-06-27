"""
MCP Server for Dashboard — browse databases, manage cron tasks, query data.

Exposes tools that Claude Code can invoke directly:
  list_databases     — list all registered SQLite databases
  query_table        — run read-only queries against any database
  list_datasources   — list managed datasources
  get_executions     — get cron execution history
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from fastmcp import FastMCP
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Datasource, DatasourceColumn, Execution, Schedule, Task, Function

app = FastMCP(name="dashboard-mcp")


def _get_db_url() -> str:
    """Get the database URL from env or default to mcp/daas.db."""
    url = os.environ.get("DAAS_DATABASE_URL")
    if url:
        return url
    db_path = Path(__file__).resolve().parent / "daas.db"
    return f"sqlite:///{db_path}"


def _get_engine():
    url = _get_db_url()
    return create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


def _get_session():
    engine = _get_engine()
    return sessionmaker(bind=engine)()


def _init_db():
    """Ensure all tables exist."""
    engine = _get_engine()
    Base.metadata.create_all(engine)


# Ensure tables exist at import time
_init_db()


def _connect(name: str, readonly: bool = True) -> sqlite3.Connection:
    """Low-level sqlite3 connection for direct table queries."""
    db_path = _get_db_url().replace("sqlite:///", "")
    if readonly:
        uri = f"file:{db_path}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    return sqlite3.connect(db_path)


@app.tool
def list_databases() -> str:
    """List all known SQLite databases in the MCP directory with table counts."""
    known = ["daas"]
    result = []
    for name in known:
        try:
            conn = _connect(name)
            tables = [
                row[0] for row in
                conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            ]
            conn.close()
            result.append({"name": f"{name}.db", "tables": tables, "table_count": len(tables)})
        except Exception as e:
            result.append({"name": f"{name}.db", "error": str(e)})
    return json.dumps(result, ensure_ascii=False, indent=2)


@app.tool
def query_table(database: str, table: str, limit: int = 50, offset: int = 0) -> str:
    """Run a read-only query against a database table. Returns rows as JSON."""
    try:
        conn = _connect(database)
        cols = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        rows = conn.execute(f'SELECT * FROM "{table}" LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        conn.close()

        data = []
        for row in rows:
            data.append({cols[i]: row[i] for i in range(len(cols))})

        return json.dumps({
            "columns": cols,
            "rows": data,
            "total": count,
            "limit": limit,
            "offset": offset,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@app.tool
def list_datasources() -> str:
    """List managed datasources from daas.db (schema managed by mcp/models/models.py)."""
    try:
        session = _get_session()
        try:
            rows = session.query(Datasource).order_by(Datasource.name).all()
            result = [
                {
                    "id": r.id,
                    "name": r.name,
                    "db_type": r.db_type,
                    "connection_string": r.connection_string,
                    "description": r.description,
                    "is_readonly": r.is_readonly,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]
            return json.dumps(result, ensure_ascii=False, indent=2)
        finally:
            session.close()
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@app.tool
def get_executions(database: str = "daas", limit: int = 50, schedule_id: str = "") -> str:
    """Get cron execution history from a database."""
    try:
        conn = _connect(database)
        if schedule_id:
            rows = conn.execute(
                "SELECT * FROM executions WHERE schedule_id = ? ORDER BY started_at DESC LIMIT ?",
                (schedule_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM executions ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        cols = ["id", "schedule_id", "started_at", "finished_at", "status", "output"]
        result = []
        for row in rows:
            result.append({cols[i]: row[i] for i in range(len(cols))})
        conn.close()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@app.tool
def get_stats() -> str:
    """Get aggregated statistics across all MCP databases."""
    stats = {}
    try:
        session = _get_session()
        try:
            stats["functions"] = session.query(Function).count()
            stats["datasources"] = session.query(Datasource).count()
            stats["schedules"] = session.query(Schedule).count()
            stats["executions"] = session.query(Execution).count()
            stats["tasks"] = session.query(Task).count()
            harnesses = session.query(Function.harness).distinct().count()
            stats["harnesses"] = harnesses
        finally:
            session.close()
    except Exception as e:
        stats["error"] = str(e)

    return json.dumps(stats, ensure_ascii=False, indent=2)
