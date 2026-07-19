#!/usr/bin/env python3
"""register_dashboard.py - standalone port of dashboard-mcp's dashboard registry.

CRUD over the `dashboards` table in daas.db + regeneration of `index.html` and
`daas.md` from the DB on every write (idempotent - no drift). No MCP, no
SQLAlchemy - stdlib sqlite3. Replaces `mcp__dashboard-mcp__register_dashboard`
/ `list_dashboards` / `get_dashboard` / `search_dashboards` / `update_dashboard`
/ `delete_dashboard`.

Dashboard HTML files live at the repo-root `dashboards/` dir (configurable via
`DASHBOARDS_DIR`). When `fd-daas-mcp/` is removed, move the existing
`fd-daas-mcp/dashboard-mcp/dashboards/*.html` there and repoint each row's
`file_path`/`file_url`.

Usage:
  uv run python scripts/register_dashboard.py register --slug my --name "My" \\
      --intro "..." --source-tables '["scraw_x"]' --refresh-cadence manual \\
      --file-path dashboards/my.html --file-url file://$PWD/dashboards/my.html
  uv run python scripts/register_dashboard.py list
  uv run python scripts/register_dashboard.py get --slug my
  uv run python scripts/register_dashboard.py search --keyword byd
  uv run python scripts/register_dashboard.py update --slug my --intro "new"
  uv run python scripts/register_dashboard.py delete --slug my
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# scripts/register_dashboard.py -> scripts(0) -> fd-daas-dashboard-creator(1) -> skills(2) -> .claude(3) -> repo root(4)
REPO_ROOT = Path(__file__).resolve().parents[4]
_DB_PATH: Path | None = None


def _load_dotenv() -> None:
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


def _resolve_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is not None:
        return _DB_PATH
    _load_dotenv()
    url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{REPO_ROOT / 'daas.db'}")
    if url.startswith("sqlite:///"):
        raw = url[len("sqlite:///"):]
        if raw and raw != ":memory:" and not os.path.isabs(raw):
            p = (REPO_ROOT / raw).resolve()
        else:
            p = Path(raw)
    else:
        p = (REPO_ROOT / "daas.db").resolve()
    _DB_PATH = p
    return p


def connect() -> sqlite3.Connection:
    p = _resolve_db_path()
    if not p.exists():
        raise FileNotFoundError(f"daas.db not found at {p} (DAAS_DATABASE_URL)")
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _dash_dir() -> Path:
    env = os.environ.get("DASHBOARDS_DIR")
    if env:
        p = Path(env)
        return p if p.is_absolute() else (REPO_ROOT / env).resolve()
    return (REPO_ROOT / "dashboards").resolve()


def _parse_json(value, field, default):
    if value is None or value == "":
        return default, None
    if isinstance(value, (list, dict)):
        return value, None
    if isinstance(value, str):
        try:
            return json.loads(value), None
        except json.JSONDecodeError as e:
            return None, f"{field} is not valid JSON: {e}"
    return None, f"{field} must be JSON string/list/dict"


def _row_to_dict(row) -> dict:
    d = dict(row)
    for k in ("source_tables", "entity_coverage", "time_range", "chart_config"):
        v = d.get(k)
        if isinstance(v, str) and v:
            try:
                d[k] = json.loads(v)
            except json.JSONDecodeError:
                pass
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── regen index.html + daas.md ─────────────────────────────────────
def _esc_html(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _esc_attr(s) -> str:
    return str(s).replace('"', "&quot;").replace("<", "&lt;")


def _md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def regenerate() -> dict:
    ddir = _dash_dir()
    ddir.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT slug, name, intro, file_url FROM dashboards ORDER BY created_at"
        ).fetchall()]
        full = [dict(r) for r in conn.execute(
            "SELECT slug, name, intro, source_tables, refresh_cadence FROM dashboards ORDER BY created_at"
        ).fetchall()]
    finally:
        conn.close()

    if rows:
        items = "\n".join(
            f'<li><a href="{_esc_attr(r["slug"])}.html">{_esc_html(r["name"] or r["slug"])}</a>'
            + (f'<br><small>{_esc_html(r["intro"])}</small>' if r.get("intro") else "")
            + "</li>"
            for r in rows
        )
    else:
        items = '<li class="empty">No dashboards yet.</li>'
    index_html = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Dashboards</title>\n<style>\n'
        '  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;'
        ' max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }\n'
        '  h1 { font-size: 1.6rem; }\n  ul#dashboards { list-style: none; padding: 0; }\n'
        '  ul#dashboards li { padding: 0.6rem 0; border-bottom: 1px solid #eee; }\n'
        '  ul#dashboards a { color: #2563eb; text-decoration: none; font-weight: 500; }\n'
        '  ul#dashboards a:hover { text-decoration: underline; }\n'
        '  ul#dashboards small { color: #666; font-size: 12px; }\n  .empty { color: #888; }\n'
        '</style>\n</head>\n<body>\n<h1>Dashboards</h1>\n'
        f'<ul id="dashboards">{items}</ul>\n</body>\n</html>\n'
    )
    (ddir / "index.html").write_text(index_html, encoding="utf-8")

    lines = ["# Dashboards", "", "| Title | Intro | URL | Source | Refresh |",
             "|---|---|---|---|---|"]
    for r in full:
        src_tables = r.get("source_tables")
        try:
            src_list = json.loads(src_tables) if isinstance(src_tables, str) else src_tables
        except json.JSONDecodeError:
            src_list = []
        src = ", ".join(src_list) if src_list else ""
        lines.append(
            f"| {_md_cell(r['name'])} | {_md_cell(r.get('intro') or '')} | "
            f"[{r['slug']}.html]({r['slug']}.html) | {src} | {r.get('refresh_cadence') or ''} |"
        )
    (ddir / "daas.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"regenerated": str(ddir), "count": len(rows)}


# ── CRUD ───────────────────────────────────────────────────────────
def register(args: dict) -> dict:
    slug = args.get("slug")
    if not slug or not _SLUG_RE.match(slug):
        return {"error": f"slug must match ^[A-Za-z0-9_-]+$ (got {slug!r})"}
    if not args.get("name"):
        return {"error": "name is required"}
    if not args.get("file_path") or not args.get("file_url"):
        return {"error": "file_path and file_url are required"}
    src, err = _parse_json(args.get("source_tables"), "source_tables", [])
    if err:
        return {"error": err}
    ent, err = _parse_json(args.get("entity_coverage"), "entity_coverage", None)
    if err:
        return {"error": err}
    tr, err = _parse_json(args.get("time_range"), "time_range", None)
    if err:
        return {"error": err}
    cc, err = _parse_json(args.get("chart_config"), "chart_config", [])
    if err:
        return {"error": err}

    conn = connect()
    try:
        existing = conn.execute("SELECT id FROM dashboards WHERE slug=?", (slug,)).fetchone()
        action = "updated" if existing else "inserted"
        if existing:
            conn.execute(
                "UPDATE dashboards SET name=?, intro=?, source_tables=?, entity_coverage=?, "
                "time_range=?, refresh_cadence=?, chart_config=?, file_path=?, file_url=?, updated_at=? "
                "WHERE slug=?",
                (args["name"], args.get("intro"), json.dumps(src, ensure_ascii=False),
                 json.dumps(ent, ensure_ascii=False) if ent is not None else None,
                 json.dumps(tr, ensure_ascii=False) if tr is not None else None,
                 args.get("refresh_cadence"), json.dumps(cc, ensure_ascii=False),
                 args["file_path"], args["file_url"], _now(), slug),
            )
        else:
            conn.execute(
                "INSERT INTO dashboards (slug, name, intro, source_tables, entity_coverage, "
                "time_range, refresh_cadence, chart_config, file_path, file_url, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (slug, args["name"], args.get("intro"), json.dumps(src, ensure_ascii=False),
                 json.dumps(ent, ensure_ascii=False) if ent is not None else None,
                 json.dumps(tr, ensure_ascii=False) if tr is not None else None,
                 args.get("refresh_cadence"), json.dumps(cc, ensure_ascii=False),
                 args["file_path"], args["file_url"], _now(), _now()),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM dashboards WHERE slug=?", (slug,)).fetchone()
        result = _row_to_dict(row)
        result["action"] = action
    finally:
        conn.close()
    regenerate()
    return result


def list_all() -> list:
    conn = connect()
    try:
        return [
            {"slug": r["slug"], "name": r["name"], "intro": r["intro"], "file_url": r["file_url"]}
            for r in conn.execute(
                "SELECT slug, name, intro, file_url FROM dashboards ORDER BY created_at"
            ).fetchall()
        ]
    finally:
        conn.close()


def get(slug: str) -> dict:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM dashboards WHERE slug=?", (slug,)).fetchone()
        if row is None:
            return {"error": f"dashboard {slug!r} not found"}
        return _row_to_dict(row)
    finally:
        conn.close()


def search(keyword: str) -> list:
    if not keyword:
        return []
    kw = keyword.lower()
    conn = connect()
    try:
        out = []
        for r in conn.execute(
            "SELECT slug, name, intro, source_tables, refresh_cadence FROM dashboards ORDER BY created_at"
        ).fetchall():
            hay = " ".join(str(x) for x in [r["name"], r["intro"], r["refresh_cadence"]] if x).lower()
            try:
                src = json.loads(r["source_tables"]) if r["source_tables"] else []
            except json.JSONDecodeError:
                src = []
            hay += " " + " ".join(src)
            if kw in hay:
                out.append({"slug": r["slug"], "name": r["name"], "intro": r["intro"]})
        return out
    finally:
        conn.close()


def update(args: dict) -> dict:
    slug = args.get("slug")
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM dashboards WHERE slug=?", (slug,)).fetchone()
        if row is None:
            return {"error": f"dashboard {slug!r} not found"}
        sets, params = [], []
        for k, json_field in [("name", None), ("intro", None), ("refresh_cadence", None),
                              ("file_path", None), ("file_url", None)]:
            if args.get(k) is not None:
                sets.append(f"{k}=?"); params.append(args[k])
        for k in ["source_tables", "entity_coverage", "time_range", "chart_config"]:
            if args.get(k) is not None:
                v, err = _parse_json(args[k], k, None)
                if err:
                    return {"error": err}
                sets.append(f"{k}=?")
                params.append(json.dumps(v, ensure_ascii=False) if v is not None else None)
        if not sets:
            return {"error": "no fields to update"}
        sets.append("updated_at=?"); params.append(_now())
        params.append(slug)
        conn.execute(f"UPDATE dashboards SET {', '.join(sets)} WHERE slug=?", params)
        conn.commit()
        row = conn.execute("SELECT * FROM dashboards WHERE slug=?", (slug,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()
    regenerate()


def delete(slug: str) -> dict:
    conn = connect()
    try:
        row = conn.execute("SELECT id FROM dashboards WHERE slug=?", (slug,)).fetchone()
        if row is None:
            return {"error": f"dashboard {slug!r} not found"}
        conn.execute("DELETE FROM dashboards WHERE slug=?", (slug,))
        conn.commit()
    finally:
        conn.close()
    regenerate()
    return {"deleted": slug}


# ── CLI ────────────────────────────────────────────────────────────
def _kv_args(argv):
    d = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                d[key] = argv[i + 1]; i += 2
            else:
                d[key] = True; i += 1
        else:
            i += 1
    return d


def main(argv) -> int:
    if not argv:
        print(json.dumps({"error": "usage: <register|list|get|search|update|delete> ..."}))
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "register":
        print(json.dumps(register(_kv_args(rest)), ensure_ascii=False, indent=2))
    elif cmd == "list":
        print(json.dumps(list_all(), ensure_ascii=False, indent=2))
    elif cmd == "get":
        print(json.dumps(get(_kv_args(rest).get("slug", "")), ensure_ascii=False, indent=2))
    elif cmd == "search":
        print(json.dumps(search(_kv_args(rest).get("keyword", "")), ensure_ascii=False, indent=2))
    elif cmd == "update":
        print(json.dumps(update(_kv_args(rest)), ensure_ascii=False, indent=2))
    elif cmd == "delete":
        print(json.dumps(delete(_kv_args(rest).get("slug", "")), ensure_ascii=False, indent=2))
    elif cmd == "regenerate":
        print(json.dumps(regenerate(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": f"unknown command: {cmd}"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
