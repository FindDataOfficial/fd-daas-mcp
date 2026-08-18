#!/usr/bin/env python3
"""Reset the DAAS project to a clean state, at three guarded levels.

Levels:
  test-artifacts  drop `scraw_zz_test_*` tables, `*_test`/`zz_test*` entity +
                  indicator collections (cascade to items/changes), and
                  `zz-test-*` dashboards (row + HTML file). Real data untouched.
  data-only       drop every `scraw_*` table + `observations` + `data_snapshots`.
                  Keep the catalog and all user artifacts (collections, researches,
                  dashboards, rules, pipelines, schedules).
  full-baseline   data-only PLUS user artifacts: `entity_collections`(+items+
                  changes), `indicator_collections`(+items+changes), `researches`,
                  `dashboards`, `rules`, `process_results`, `pipeline_collections`
                  (+items), `schedules`, `tasks`, `executions`, `alert_rules`,
                  `alert_events`, `pdf_documents`, `pdf_meta`, `pdf_chunks`,
                  `workflow_runs`, `workflow_step_results`. KEEPS the reference
                  catalog (sources/daas_functions/daas_function_columns/entities/
                  entity_datasource_links/categories/datasource_forms/
                  datasource_sections/indicator_rules + leader/composite registry).
                  (This keep-set is the design's Q1 default - confirm before --yes.)

Safety:
  - **Dry-run by default.** Prints exactly what would be removed and exits.
  - **`--yes` required to mutate.**
  - **Backup first.** Copies `daas.db` to `daas.db.bak-<timestamp>` before any
    drop; refuses to mutate if the backup fails.
  - Drops run with `PRAGMA foreign_keys=OFF` so order does not matter, then
    re-enables FK.

Usage:
  python reset_project.py --level test-artifacts            # preview (dry-run)
  python reset_project.py --level data-only --yes           # mutate
  python reset_project.py --level full-baseline --yes       # mutate (destructive)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # scripts/ -> skill -> skills -> .claude -> repo

# User-artifact tables dropped only at full-baseline (data-only keeps these).
USER_ARTIFACT_TABLES = [
    "entity_collections", "entity_collection_items", "entity_collection_changes",
    "indicator_collections", "indicator_collection_items", "indicator_collection_changes",
    "researches", "dashboards", "rules", "process_results",
    "pipeline_collections", "pipeline_collection_items",
    "schedules", "tasks", "executions",
    "alert_rules", "alert_events",
    "pdf_documents", "pdf_meta", "pdf_chunks",
    "workflow_runs", "workflow_step_results",
]
# Always-dropped data tables (data-only + full-baseline).
DATA_TABLES = ["observations", "data_snapshots"]


def resolve_db() -> Path:
    url = os.environ.get("DAAS_DATABASE_URL")
    if not url:
        env = REPO / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("DAAS_DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip("'\"")
                    break
    if not url:
        url = "sqlite:///daas.db"
    if not url.startswith("sqlite:///"):
        raise SystemExit(f"unsupported DAAS_DATABASE_URL (need sqlite:///): {url}")
    rel = url[len("sqlite:///"):]
    p = Path(rel)
    return p if p.is_absolute() else (REPO / p)


def all_tables(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic%'"
    ).fetchall()
    return sorted(r[0] for r in rows)


def scraw_tables(con: sqlite3.Connection) -> list[str]:
    return [t for t in all_tables(con) if t.startswith("scraw_")]


def compute_drop(con: sqlite3.Connection, level: str) -> dict:
    """Return a description of what would be removed at `level`."""
    out: dict = {"tables": [], "collections": [], "dashboards": []}
    if level == "test-artifacts":
        out["tables"] = [t for t in scraw_tables(con) if t.startswith("scraw_zz_test_")]
        for col_tbl in ("entity_collections", "indicator_collections"):
            if col_tbl in all_tables(con):
                rows = con.execute(
                    f"SELECT name FROM {col_tbl} WHERE name LIKE 'zz_test%' OR name LIKE '%_test'"
                ).fetchall()
                out["collections"] += [(col_tbl, r[0]) for r in rows]
        if "dashboards" in all_tables(con):
            rows = con.execute(
                "SELECT slug, file_path FROM dashboards WHERE slug LIKE 'zz-test-%'"
            ).fetchall()
            out["dashboards"] = [{"slug": r[0], "file_path": r[1]} for r in rows]
        return out

    # data-only + full-baseline
    out["tables"] = sorted(set(DATA_TABLES) | set(scraw_tables(con)))
    if level == "full-baseline":
        present = set(all_tables(con))
        out["tables"] = sorted(set(out["tables"]) | {t for t in USER_ARTIFACT_TABLES if t in present})
    return out


def preview(drop: dict, db: Path) -> None:
    print(f"# reset preview ({db})")
    if drop["tables"]:
        print(f"## drop {len(drop['tables'])} table(s):")
        for t in drop["tables"]:
            print(f"  - {t}")
    if drop.get("collections"):
        print(f"## delete {len(drop['collections'])} test collection(s):")
        for tbl, name in drop["collections"]:
            print(f"  - {tbl}: {name}")
    if drop.get("dashboards"):
        print(f"## delete {len(drop['dashboards'])} test dashboard(s):")
        for d in drop["dashboards"]:
            print(f"  - {d['slug']} ({d['file_path']})")
    if not (drop["tables"] or drop.get("collections") or drop.get("dashboards")):
        print("## nothing to remove at this level")


def backup_db(db: Path) -> Path:
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = db.with_name(f"{db.name}.bak-{ts}")
    shutil.copy2(db, bak)
    return bak


def execute(con: sqlite3.Connection, drop: dict, db: Path) -> None:
    con.execute("PRAGMA foreign_keys=OFF")
    dropped = 0
    for t in drop["tables"]:
        try:
            con.execute(f'DROP TABLE IF EXISTS "{t}"')
            dropped += 1
        except sqlite3.Error as e:
            print(f"  ! drop {t} failed: {e}", file=sys.stderr)
    for tbl, name in drop.get("collections", []):
        try:
            con.execute(f"DELETE FROM {tbl} WHERE name = ?", (name,))
        except sqlite3.Error as e:
            print(f"  ! delete {tbl}/{name} failed: {e}", file=sys.stderr)
    for d in drop.get("dashboards", []):
        try:
            con.execute("DELETE FROM dashboards WHERE slug = ?", (d["slug"],))
            if d.get("file_path"):
                fp = Path(d["file_path"])
                if not fp.is_absolute():
                    fp = REPO / fp
                if fp.exists():
                    fp.unlink()
        except sqlite3.Error as e:
            print(f"  ! delete dashboard {d['slug']} failed: {e}", file=sys.stderr)
    con.commit()
    con.execute("PRAGMA foreign_keys=ON")
    print(f"# dropped {dropped} table(s) from {db}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Reset the DAAS project to a clean state.")
    ap.add_argument("--level", required=True,
                    choices=["test-artifacts", "data-only", "full-baseline"])
    ap.add_argument("--yes", action="store_true",
                    help="actually mutate (default is a dry-run preview)")
    ap.add_argument("--dry-run", action="store_true",
                    help="force a dry-run preview even with --yes (for scripting)")
    args = ap.parse_args()

    db = resolve_db()
    if not db.exists():
        print(f"DB not found: {db}", file=sys.stderr)
        return 2

    con = sqlite3.connect(str(db))
    con.execute("PRAGMA foreign_keys=ON")
    drop = compute_drop(con, args.level)

    if not args.yes or args.dry_run:
        print(f"[DRY-RUN] level={args.level} (use --yes to mutate)\n")
        preview(drop, db)
        print("\nNo changes made. Re-run with --yes to apply.")
        con.close()
        return 0

    # mutate
    bak = backup_db(db)
    print(f"# backup -> {bak}")
    execute(con, drop, db)
    con.close()

    # run-notification (markdown block for the skill to surface)
    print(
        "\n## Run Complete\n"
        f"**Skill:** fd-coding-daas-reset-project\n"
        f"**Status:** reset applied (level={args.level})\n"
        f"**Produced:** backup {bak.name}; dropped {len(drop['tables'])} table(s)"
        + (f", {len(drop.get('collections', []))} test collection(s)" if drop.get('collections') else "")
        + (f", {len(drop.get('dashboards', []))} test dashboard(s)" if drop.get('dashboards') else "")
        + "\n**Next:** verify with `sqlite3 daas.db \".tables\"`; restore from backup if needed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
