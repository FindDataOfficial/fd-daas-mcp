from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: str = "data/scraw.db") -> sqlite3.Connection:
    """Open a WAL-mode SQLite connection, creating the parent dir."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
