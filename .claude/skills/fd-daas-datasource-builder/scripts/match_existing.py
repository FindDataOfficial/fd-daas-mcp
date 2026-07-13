#!/usr/bin/env python3
"""Pull existing indicator_names / sources / entity samples from daas.db.

Used by the skill to dedup proposed indicators against indicator_rules.indicator_name,
to avoid source-name collisions, and to check whether an entity type is already
populated. Output: JSON on stdout.

Reads DAAS_DATABASE_URL from repo-root .env (or walks up to find daas.db).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".env").exists() or (parent / "daas.db").exists():
            return parent
    return p.parents[-1]


def _db_path() -> str:
    url = os.environ.get("DAAS_DATABASE_URL", "").strip()
    if url:
        return url.replace("sqlite:///", "")
    envf = _repo_root() / ".env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            if line.startswith("DAAS_DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                return url.replace("sqlite:///", "")
    for cand in (_repo_root() / "daas.db", _repo_root() / "mcp" / "daas.db"):
        if cand.exists():
            return str(cand)
    return str(_repo_root() / "daas.db")


def main() -> None:
    db = _db_path()
    if not Path(db).exists():
        sys.exit(f"daas.db not found (resolved {db}). Set DAAS_DATABASE_URL in .env.")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    indicator_names = [r[0] for r in conn.execute(
        "SELECT DISTINCT indicator_name FROM indicator_rules ORDER BY indicator_name"
    )]
    sources = [r[0] for r in conn.execute("SELECT name FROM sources ORDER BY name")]

    entity_types: dict[str, int] = {
        r[0]: r[1] for r in conn.execute(
            "SELECT entity_type, count(*) FROM entities GROUP BY entity_type"
        )
    }
    entity_sample: dict[str, list[dict]] = {}
    for et in entity_types:
        rows = conn.execute(
            "SELECT code, name, ticker, exchange, country_code FROM entities "
            "WHERE entity_type=? LIMIT 50",
            (et,),
        ).fetchall()
        entity_sample[et] = [dict(r) for r in rows]

    # existing indicator (value_column, op) pairs - helps the agent see what
    # metric/op combos already exist, beyond just the indicator_name string.
    existing_pairs = [
        {"value_column": r[0], "op": r[1]}
        for r in conn.execute(
            "SELECT DISTINCT value_column, op FROM indicator_rules"
        )
    ]

    print(json.dumps({
        "db_path": db,
        "indicator_names": indicator_names,
        "indicator_count": len(indicator_names),
        "sources": sources,
        "entity_types": entity_types,
        "entity_sample": entity_sample,
        "existing_value_op_pairs": existing_pairs,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
