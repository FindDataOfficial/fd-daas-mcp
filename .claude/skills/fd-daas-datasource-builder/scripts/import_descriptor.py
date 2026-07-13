#!/usr/bin/env python3
"""Import a daas.descriptor.json into daas.db (idempotent upserts).

Inserts (INSERT OR IGNORE, so re-runs are safe):
  - sources
  - daas_functions
  - daas_function_columns
  - indicator_rules  (skipped when dedup_status == "exists")

Entity links are NOT auto-created (they need concrete entity_ids + identifiers
the descriptor doesn't carry). Unmatched entities are printed for manual linking
via the daas MCP tools (daas_link_entity_datasource) or sqlite.

Usage:
    python import_descriptor.py <descriptor.json> [--db <path>] [--dry-run]
"""
from __future__ import annotations

import argparse
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("descriptor")
    ap.add_argument("--db", default=None)
    ap.add_argument("--dry-run", action="store_true", help="rollback after counting")
    args = ap.parse_args()

    desc = json.loads(Path(args.descriptor).read_text(encoding="utf-8"))
    db = args.db or _db_path()
    if not Path(db).exists():
        sys.exit(f"daas.db not found (resolved {db}). Set DAAS_DATABASE_URL in .env.")
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")

    src = desc["source"]
    conn.execute(
        "INSERT OR IGNORE INTO sources(name, label, description, url, enabled, score) "
        "VALUES(?, ?, ?, ?, 1, ?)",
        (src["name"], src.get("label", ""), src.get("description", ""),
         src.get("url", ""), src.get("score")),
    )
    (sid,) = conn.execute("SELECT id FROM sources WHERE name=?", (src["name"],)).fetchone()

    counts = {"functions": 0, "columns": 0, "indicators_new": 0,
              "indicators_skipped_existing": 0, "indicators_new_concept": 0}
    unmatched_entities: list[dict] = []

    for f in desc.get("daas_functions", []):
        conn.execute(
            "INSERT OR IGNORE INTO daas_functions"
            "(source_id, name, label, description, category, parameters, output_type, frequency) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, f["name"], f.get("label"), f.get("description"), f.get("category", "未分类"),
             json.dumps(f.get("parameters", []), ensure_ascii=False),
             f.get("output_type"), f.get("frequency")),
        )
        (fid,) = conn.execute(
            "SELECT id FROM daas_functions WHERE source_id=? AND name=?", (sid, f["name"])
        ).fetchone()
        counts["functions"] += 1

        for col in f.get("columns", []):
            conn.execute(
                "INSERT OR IGNORE INTO daas_function_columns"
                "(function_id, name, label, type, description, nullable) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (fid, col["name"], col.get("label"), col.get("type"),
                 col.get("description"), col.get("nullable")),
            )
            counts["columns"] += 1

        # proposed_indicator_rules are nested under each column in the descriptor
        for col in f.get("columns", []):
            for ind in col.get("proposed_indicator_rules", []):
                ds = ind.get("dedup_status", "new")
                if ds == "exists":
                    counts["indicators_skipped_existing"] += 1
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO indicator_rules"
                    "(name, datasource, function_name, source_table, date_column, "
                    " value_column, op, params_json, indicator_name, enabled, score) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                    (ind["name"], ind.get("datasource", src["name"]),
                     ind.get("function_name", f["name"]), ind.get("source_table"),
                     ind["date_column"], ind["value_column"], ind["op"],
                     json.dumps(ind.get("params", {}), ensure_ascii=False),
                     ind["indicator_name"], ind.get("score")),
                )
                if ds == "new_concept":
                    counts["indicators_new_concept"] += 1
                else:
                    counts["indicators_new"] += 1

        for e in f.get("entities", []):
            if not e.get("matched_existing"):
                unmatched_entities.append({
                    "function": f["name"],
                    "entity_type": e.get("entity_type"),
                    "identifier_shape": e.get("identifier_shape"),
                    "note": e.get("note", ""),
                })

    if args.dry_run:
        conn.rollback()
        print(f"[dry-run] would import into {db}: {counts}")
    else:
        conn.commit()
        print(f"imported into {db}: {counts}  (source id={sid})")

    if unmatched_entities:
        print(f"\n{len(unmatched_entities)} entity link(s) need manual creation "
              f"(descriptor carries no concrete entity ids):")
        for u in unmatched_entities:
            print(f"  - {u['function']}: entity_type={u['entity_type']} "
                  f"shape={u['identifier_shape']} note={u['note']}")
        print("Use daas_link_entity_datasource (MCP) or INSERT INTO entity_datasource_links.")


if __name__ == "__main__":
    main()
