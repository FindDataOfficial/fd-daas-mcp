"""Shared runtime settings loader for MCP servers.

Usage in any MCP tool that makes HTTP requests:

    from settings_helper import load_runtime_settings
    load_runtime_settings('my-mcp-name')  # reads DB, sets os.environ
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv

_cache = {"ts": 0, "ttl": 5}  # 5-second in-process cache


def _get_db_path() -> str:
    ROOT = Path(__file__).resolve().parent  # mcp/
    load_dotenv(ROOT / ".env")
    db_url = os.environ.get("DAAS_DATABASE_URL", "sqlite:///mcp/daas.db")
    return db_url.replace("sqlite:///", "")


def load_runtime_settings(scope: str = "global") -> None:
    """Load runtime settings from daas.db, with scope priority.

    For each runtime key, checks: scope-specific → global → os.environ fallback.
    Cached for 5 seconds to avoid DB hits on every tool call.
    """
    now = time.time()
    if now - _cache["ts"] < _cache["ttl"]:
        return  # cache hit

    import sqlite3

    db_path = _get_db_path()

    conn = sqlite3.connect(db_path)
    try:
        # Load global settings first
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE scope='global' AND category='runtime'"
        ).fetchall()
        for key, value in rows:
            if value:
                os.environ[key] = value

        # Load scope-specific overrides on top
        if scope != "global":
            rows = conn.execute(
                "SELECT key, value FROM settings WHERE scope=? AND category='runtime'",
                (scope,),
            ).fetchall()
            for key, value in rows:
                if value:
                    os.environ[key] = value
    finally:
        conn.close()

    _cache["ts"] = now
