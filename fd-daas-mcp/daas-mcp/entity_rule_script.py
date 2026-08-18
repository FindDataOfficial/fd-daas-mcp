"""Rule-script runner for entity collections.

A rule script is a Python file that defines `members(ctx) -> list`, returning
the intended member set of a collection. It is the script analogue of the
declarative `rule_json`: when `entity_collections.rule_script` is set,
`EntityCollectionService.sync_entity_collection` loads the script, calls
`members(ctx)`, and diffs the result against the current membership (recording
add_in / remove_out in `entity_collection_changes`).

`ctx` is a `RuleScriptContext` exposing a read-only `query(sql, params=())`
over daas.db — so a rule can express cross-table logic the declarative JSON
cannot, e.g. "stocks in today's block-trade table", "stocks whose observation
crossed a threshold", "union of two other collections". The connection is
opened in SQLite `mode=ro`, so a script cannot mutate the DB by construction.

The script path stored in `entity_collections.rule_script` is repo-root
relative (e.g. `mcp/daas-mcp/rules/entity_collections/my-watchlist.py`), so it
resolves regardless of the process cwd (cron runs under
`uv run --directory mcp/daas-mcp`; workflows call in-process).

Contract for `members(ctx)`:

    def members(ctx):
        rows = ctx.query(
            "SELECT code FROM entity_collection_items WHERE collection_id = 7"
        )
        return [r["code"] for r in rows]

Each returned item may be:
  - str  → a stock code (entity_type defaults to 'stock')
  - dict → {"entity_type": "stock", "code": "600519"}

Items that don't resolve to a known entity are skipped (a sync shouldn't fail
the whole collection over one delisted code); the EntityCollectionService
handles that normalization.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from typing import Any

from daas_database import _REPO_ROOT, _resolve_url


class RuleScriptContext:
    """Read-only query context handed to a rule script's `members(ctx)`.

    Opens its own sqlite3 connection in `mode=ro` so the script cannot mutate
    daas.db — it can only SELECT. The connection is separate from the
    EntityCollectionService's SQLAlchemy session, so the script sees committed
    state and cannot interfere with the sync transaction.
    """

    def __init__(self, db_url: str):
        self.db_url = _resolve_url(db_url)
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            url = self.db_url
            if url.startswith("sqlite:///"):
                path = url[len("sqlite:///"):]
                if path == ":memory:":
                    # An in-memory DB can't be reopened from another connection
                    # (each connection gets its own private DB). Share via the
                    # cache=shared URI so the script sees the session's data.
                    self._conn = sqlite3.connect(
                        "file::memory:?cache=shared",
                        uri=True,
                        check_same_thread=False,
                    )
                else:
                    self._conn = sqlite3.connect(
                        f"file:{path}?mode=ro",
                        uri=True,
                        check_same_thread=False,
                    )
            else:
                # Non-sqlite URL (unusual for daas) — best-effort normal connect.
                self._conn = sqlite3.connect(url, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def query(self, sql: str, params: tuple | list | dict = ()) -> list[dict]:
        """Run a SELECT and return rows as a list of dicts. Read-only by
        construction (the connection is opened in `mode=ro`); any write
        statement raises sqlite3.OperationalError."""
        cur = self._connect().execute(sql, params)
        try:
            rows = cur.fetchall()
        finally:
            cur.close()
        return [dict(r) for r in rows]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def run_rule_script(script_path: str, db_url: str) -> list:
    """Load `script_path` (repo-root relative or absolute), call its
    `members(ctx)`, and return the raw result list.

    Raises FileNotFoundError if the script is missing, TypeError if it has no
    callable `members`. The caller (EntityCollectionService) normalizes the
    returned items into entity ids.
    """
    p = Path(script_path)
    if not p.is_absolute():
        p = (_REPO_ROOT / script_path).resolve()
    if not p.exists():
        raise FileNotFoundError(
            f"rule script not found: {script_path!r} (resolved to {p})"
        )
    spec = importlib.util.spec_from_file_location(
        f"entity_rule_script_{p.stem}_{abs(hash(p)) % 100000}", p
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not callable(getattr(mod, "members", None)):
        raise TypeError(
            f"rule script {script_path!r} must define a callable `members(ctx)`"
        )
    ctx = RuleScriptContext(db_url)
    try:
        result = mod.members(ctx)
    finally:
        ctx.close()
    return result if result is not None else []
