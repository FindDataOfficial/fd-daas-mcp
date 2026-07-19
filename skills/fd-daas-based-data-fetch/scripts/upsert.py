#!/usr/bin/env python3
"""upsert.py - persist fetched records into daas.db.

Two sinks:
  * `scraw_<slug>` tables - auto-CREATE TABLE + ALTER TABLE ADD COLUMN for new
    columns + INSERT OR REPLACE on the upsert keys. Mirrors the old
    `fetch_to_store.py` / pipeline bridge shape.
  * `observations` - upsert (date, value) pairs keyed on
    (source, function_name, identifier, date), matching `run_indicator.py`.

Parameterized queries; `PRAGMA foreign_keys=ON` (via db.connect); backs up
daas.db before bulk writes. Identifiers validated against
`^[A-Za-z_][A-Za-z0-9_]*$` (cannot be bind params).

Usage:
  uv run python scripts/upsert.py --table scraw_x --keys date \\
      --records '[{"date":"2024-01-01","close":"1.0"}]'
  uv run python scripts/upsert.py --observations \\
      '[{"source":"akshare","function_name":"f","indicator":"close","date":"2024-01-01","value":"1.0","metadata":{}}]'
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect, backup  # noqa: E402

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> None:
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"invalid identifier: {name!r}")


def upsert_scraw(conn, table: str, records: list[dict], upsert_keys: list[str]) -> dict:
    _validate_identifier(table)
    if not records:
        return {"rows_written": 0, "table": table}
    for k in upsert_keys:
        _validate_identifier(k)

    # Union of columns, preserving first-seen order.
    cols: list[str] = []
    seen: set[str] = set()
    for r in records:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                cols.append(k)
    for c in cols:
        _validate_identifier(c)

    if not _table_exists(conn, table):
        coldefs = ", ".join(f'"{c}" TEXT' for c in cols)
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({coldefs})')
    else:
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for c in cols:
            if c not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{c}" TEXT')

    # Unique index on upsert keys so INSERT OR REPLACE dedupes correctly.
    idx_name = f"uq_{table}_" + "_".join(upsert_keys)
    cols_csv = ", ".join(f'"{k}"' for k in upsert_keys)
    conn.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ({cols_csv})'
    )

    placeholders = ", ".join("?" for _ in cols)
    cols_def = ", ".join(f'"{c}"' for c in cols)
    sql = f'INSERT OR REPLACE INTO "{table}" ({cols_def}) VALUES ({placeholders})'
    rows = [
        [("" if r.get(c) is None else str(r.get(c))) for c in cols] for r in records
    ]
    conn.executemany(sql, rows)
    return {"rows_written": len(rows), "table": table, "columns": cols}


def upsert_observations(conn, records: list[dict]) -> dict:
    """records: [{source, function_name, indicator, date, value, metadata?}]"""
    if not records:
        return {"rows_written": 0}
    sql = (
        "INSERT INTO observations "
        "(source, function_name, indicator, date, value, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(source, function_name, indicator, date) DO UPDATE SET "
        "value=excluded.value, metadata=excluded.metadata"
    )
    rows = []
    for r in records:
        meta = r.get("metadata")
        meta_json = json.dumps(meta, ensure_ascii=False) if isinstance(meta, dict) else (
            meta if isinstance(meta, str) else None
        )
        rows.append(
            (
                r["source"],
                r["function_name"],
                r["indicator"],
                str(r["date"]),
                str(r["value"]),
                meta_json,
            )
        )
    conn.executemany(sql, rows)
    return {"rows_written": len(rows)}


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def main(argv: list[str]) -> int:
    if not argv:
        print(json.dumps({"error": "usage: --table <t> --keys k1[,k2] --records <json> | --observations <json>"}))
        return 2

    args = argv
    table = None
    keys: list[str] = []
    records_json = None
    observations_json = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--table" and i + 1 < len(args):
            table = args[i + 1]; i += 2
        elif a == "--keys" and i + 1 < len(args):
            keys = [k for k in args[i + 1].split(",") if k]; i += 2
        elif a == "--records" and i + 1 < len(args):
            records_json = args[i + 1]; i += 2
        elif a == "--observations" and i + 1 < len(args):
            observations_json = args[i + 1]; i += 2
        else:
            print(json.dumps({"error": f"unknown arg: {a}"}))
            return 2

    bak = backup()
    conn = connect()
    try:
        if observations_json is not None:
            recs = json.loads(observations_json)
            res = upsert_observations(conn, recs)
        elif table is not None and records_json is not None:
            recs = json.loads(records_json)
            res = upsert_scraw(conn, table, recs, keys)
        else:
            print(json.dumps({"error": "must pass --observations OR --table+--keys+--records"}))
            return 2
        conn.commit()
        print(json.dumps({**res, "backup": str(bak)}, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
