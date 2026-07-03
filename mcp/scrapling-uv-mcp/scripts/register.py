#!/usr/bin/env python3
"""One-shot registrar for scraw scraper scripts.

Usage:
  python3 register.py <name>
  python3 register.py <name> --check          # show what WOULD be written, no DB writes

Loads `<name>.py` (must live next to this file), reads its module-level
`MANIFEST = ScrawManifest(...)`, then writes the daas database idempotently:

  • datasource_columns — N rows for the source's columns.
    Looks up the parent id in `sources` (NOT `datasources` — `datasources` is
    combine-mcp's legacy MCP-server table). Runs with `PRAGMA foreign_keys=OFF`
    because `datasource_columns.datasource_id` declares a stale FK to
    `datasources` that the real parent (`sources`) doesn't satisfy for ids ≥ 5.

  • scraw_configs — upserts the simple {name, type, description} column list.

The `sources` row itself is NOT created here — call
`mcp__daas-mcp__create_datasource` first (it manages categories and the
full self-describing `config` blob).

Stdlib only: sqlite3 + importlib. Run with plain `python3` from anywhere
in the repo.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def resolve_db_path() -> str:
    """Find daas.db: prefer DAAS_DATABASE_URL, else walk up to mcp/daas.db."""
    url = os.environ.get("DAAS_DATABASE_URL", "").strip()
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///"):]
        if os.path.isabs(p) and os.path.exists(p):
            return p
        if os.path.exists(p):
            return os.path.abspath(p)
    cur = Path.cwd()
    for _ in range(8):
        cand = cur / "mcp" / "daas.db"
        if cand.exists():
            return str(cand)
        if cur.parent == cur:
            break
        cur = cur.parent
    # also try relative to this file's grandparent (mcp/)
    cand = SCRIPTS_DIR.parent.parent / "daas.db"
    if cand.exists():
        return str(cand)
    return "mcp/daas.db"


def load_manifest(name: str):
    """Import scripts/<name>.py and return its MANIFEST attribute."""
    script = SCRIPTS_DIR / f"{name}.py"
    if not script.exists():
        sys.exit(f"error: {script} not found")
    # make sibling modules (scraw_contract) importable
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(name, script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    manifest = getattr(mod, "MANIFEST", None)
    if manifest is None:
        sys.exit(f"error: {script} has no module-level MANIFEST (see scraw_contract.ScrawManifest)")
    if manifest.name != name:
        sys.exit(f"error: MANIFEST.name='{manifest.name}' must equal script basename '{name}'")
    return manifest


def write_datasource_columns(conn: sqlite3.Connection, manifest, dry: bool) -> tuple[int, int]:
    """Idempotently write N datasource_columns rows. Returns (source_id, n_written)."""
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id FROM sources WHERE name = ?", (manifest.name,)
    ).fetchone()
    if not row:
        sys.exit(
            f"error: source '{manifest.name}' not found in `sources` table. "
            f"Run mcp__daas-mcp__create_datasource first."
        )
    source_id = row[0]
    cols = manifest.to_columns_json()
    if dry:
        return source_id, len(cols)

    # bypass the stale FK -> datasources (real parent is `sources`)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur.execute(
        "DELETE FROM datasource_columns WHERE datasource_id=? AND table_name=?",
        (source_id, manifest.name),
    )
    for c in cols:
        cur.execute(
            """INSERT INTO datasource_columns
               (datasource_id, table_name, column_name, column_type,
                is_primary_key, is_nullable, description, source_field,
                unit, semantic_type)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id, c["table_name"], c["column_name"], c["column_type"],
                c["is_primary_key"], c["is_nullable"], c["description"],
                c["source_field"], c["unit"], c["semantic_type"],
            ),
        )
    return source_id, len(cols)


def write_scraw_config(conn: sqlite3.Connection, manifest, dry: bool) -> str:
    """Upsert scraw_configs row by name. Returns 'inserted'|'updated'|'(dry)'."""
    cur = conn.cursor()
    cols_json = json.dumps(manifest.to_scraw_columns(), ensure_ascii=False)
    existing = cur.execute(
        "SELECT id FROM scraw_configs WHERE name = ?", (manifest.name,)
    ).fetchone()
    if dry:
        return "would-update" if existing else "would-insert"
    if existing:
        cur.execute(
            "UPDATE scraw_configs SET url=?, columns_json=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
            (manifest.url, cols_json, manifest.name),
        )
        return "updated"
    cur.execute(
        "INSERT INTO scraw_configs (name, url, columns_json) VALUES (?,?,?)",
        (manifest.name, manifest.url, cols_json),
    )
    return "inserted"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name", help="scraper script basename (no .py)")
    ap.add_argument("--check", action="store_true",
                    help="print what would be written; do not commit")
    args = ap.parse_args()

    manifest = load_manifest(args.name)
    db_path = resolve_db_path()
    if not os.path.exists(db_path):
        sys.exit(f"error: daas.db not found at {db_path} (set DAAS_DATABASE_URL?)")

    conn = sqlite3.connect(db_path)
    source_id, n_cols = write_datasource_columns(conn, manifest, args.check)
    scraw_state = write_scraw_config(conn, manifest, args.check)
    if not args.check:
        conn.commit()
    # totals after write
    total = conn.execute(
        "SELECT COUNT(*) FROM datasource_columns WHERE datasource_id=?", (source_id,)
    ).fetchone()[0]
    conn.close()

    mark = "(dry-run) " if args.check else ""
    print(f"{mark}name={manifest.name} | sources.id={source_id}")
    print(f"{mark}datasource_columns: {n_cols} rows written | {total} total on this source")
    print(f"{mark}scraw_configs: {scraw_state}")
    print(f"db: {db_path}")


if __name__ == "__main__":
    main()
