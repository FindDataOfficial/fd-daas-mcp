"""Shared sqlite3 helpers for the skill-based-data-fetch scripts.

Reads `DAAS_DATABASE_URL` from the repo-root `.env` (then the process env),
resolves a relative `sqlite:///` path against the repo root, and returns a
`sqlite3` connection with `PRAGMA foreign_keys=ON`. No SQLAlchemy, no MCP -
stdlib only.

Follows `DAAS_DATABASE_URL` (repo-root `.env`), so it works wherever `daas.db`
lives (currently repo-root `daas.db`).
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

# scripts/db.py -> scripts(0) -> skill-based-data-fetch(1) -> skills(2) -> .claude(3) -> repo root(4)
REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_dotenv() -> None:
    """Populate os.environ from the repo-root .env (does not override set vars)."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def resolve_db_path() -> Path:
    """Resolve the daas.db path from `DAAS_DATABASE_URL` (relative -> repo root)."""
    _load_dotenv()
    url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{REPO_ROOT / 'daas.db'}")
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if path and path != ":memory:" and not os.path.isabs(path):
            return (REPO_ROOT / path).resolve()
        return Path(path)
    # Fallback: assume the canonical shared DB.
    return (REPO_ROOT / "mcp" / "daas.db").resolve()


def connect() -> sqlite3.Connection:
    """Open a sqlite3 connection to daas.db with FK enforcement + Row factory."""
    path = resolve_db_path()
    if not path.exists():
        raise FileNotFoundError(f"daas.db not found at {path} (DAAS_DATABASE_URL)")
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def backup(tag: str | None = None) -> Path:
    """Copy daas.db to a .bak alongside it. Call before bulk writes.

    Without ``tag``: ``daas.db.bak`` (overwrites any prior .bak — fine for
    routine pre-write backups in upsert.py / run_indicator.py).
    With ``tag``: ``daas.db.bak-<tag>`` (a distinct file — use for one-time
    destructive migrations so they don't clobber the routine .bak).
    """
    path = resolve_db_path()
    if tag:
        bak = path.with_name(f"{path.name}.bak-{tag}")
    else:
        bak = path.with_name(path.name + ".bak")
    shutil.copy2(path, bak)
    return bak
