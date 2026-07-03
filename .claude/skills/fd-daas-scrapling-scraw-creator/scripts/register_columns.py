#!/usr/bin/env python3
"""Register scraped columns into the daas `datasource_columns` table.

Why this exists: daas-mcp exposes `create_datasource` (writes the `datasources`
row) but has NO tool for adding columns — `datasource_columns` is written
directly. This helper does that write, idempotently.

It uses only the Python stdlib (sqlite3) so it runs in any environment with
python3 — no venv, no sqlalchemy, no mcp_models import required. The target DB
is the shared `mcp/daas.db`, located via `DAAS_DATABASE_URL` (root `.env`) or
by walking up from the cwd to find `mcp/daas.db`.

Usage:
  python3 register_columns.py <datasource_name> <columns.json>

columns.json is an array; each entry maps 1:1 to a `datasource_columns` row:
  [
    {
      "table_name": "moa_archive",          # logical table (use datasource name)
      "column_name": "title",
      "column_type": "string",              # string|integer|float|date|datetime|boolean
      "is_primary_key": 0,                  # 0|1
      "is_nullable": 0,                     # 0|1
      "description": "full document title",
      "source_field": "a@title",            # CSS selector / URL token — the scraw bridge
      "unit": "",                           # e.g. "元", "%", "" if none
      "semantic_type": "title"             # title|date|url|identifier|category|amount|...
    }
  ]

Missing optional fields default to 0 / "".
"""
import json
import os
import sqlite3
import sys
from pathlib import Path


def resolve_db_path() -> str:
    """Find daas.db: prefer DAAS_DATABASE_URL, else walk up to mcp/daas.db."""
    url = os.environ.get("DAAS_DATABASE_URL", "").strip()
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
        if os.path.isabs(p):
            return p
        # resolve relative to cwd
        if os.path.exists(p):
            return p
    # walk up from cwd looking for mcp/daas.db
    cur = Path.cwd()
    for _ in range(8):
        cand = cur / "mcp" / "daas.db"
        if cand.exists():
            return str(cand)
        if cur.parent == cur:
            break
        cur = cur.parent
    # last resort
    return "mcp/daas.db"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    ds_name = sys.argv[1]
    cols_path = sys.argv[2]

    with open(cols_path, "r", encoding="utf-8") as f:
        cols = json.load(f)
    if not isinstance(cols, list) or not cols:
        print("error: columns.json must be a non-empty array", file=sys.stderr)
        sys.exit(1)

    db_path = resolve_db_path()
    if not os.path.exists(db_path):
        print(f"error: daas.db not found at {db_path}", file=sys.stderr)
        print("set DAAS_DATABASE_URL or run from the repo root", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    row = cur.execute(
        "SELECT id FROM datasources WHERE name = ?", (ds_name,)
    ).fetchone()
    if not row:
        print(
            f"error: datasource '{ds_name}' not found. "
            f"Run create_datasource first (mcp__daas-mcp__create_datasource).",
            file=sys.stderr,
        )
        sys.exit(1)
    ds_id = row[0]

    # idempotent: replace all columns for this datasource+table_name set
    table_names = sorted({c.get("table_name", ds_name) for c in cols})
    for tn in table_names:
        cur.execute(
            "DELETE FROM datasource_columns WHERE datasource_id=? AND table_name=?",
            (ds_id, tn),
        )

    inserted = 0
    for c in cols:
        cur.execute(
            """INSERT INTO datasource_columns
               (datasource_id, table_name, column_name, column_type,
                is_primary_key, is_nullable, description, source_field,
                unit, semantic_type)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                ds_id,
                c.get("table_name", ds_name),
                c["column_name"],
                c.get("column_type", "string"),
                int(c.get("is_primary_key", 0)),
                int(c.get("is_nullable", 1)),
                c.get("description", ""),
                c.get("source_field", ""),
                c.get("unit", ""),
                c.get("semantic_type", ""),
            ),
        )
        inserted += 1

    conn.commit()

    # report
    cnt = cur.execute(
        "SELECT COUNT(*) FROM datasource_columns WHERE datasource_id=?", (ds_id,)
    ).fetchone()[0]
    conn.close()
    print(
        f"registered {inserted} columns for datasource '{ds_name}' (id={ds_id}); "
        f"{cnt} total columns now on this datasource"
    )


if __name__ == "__main__":
    main()
