#!/usr/bin/env python3
"""Read-only sqlite3 listing of ingested pdf documents.

Reads DAAS_DATABASE_URL from the repo-root .env (resolves relative sqlite:///
paths against the repo root, mirroring skill-based-data-fetch/scripts/db.py).
Stdlib only - no MCP, no embedding deps.

Usage:
  uv run python scripts/db.py            # list all pdf documents
  uv run python scripts/db.py --doc 3    # one document + its chunks
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# scripts/db.py -> scripts(0) -> fd-daas-pdf(1) -> skills(2) -> .claude(3) -> repo root(4)
REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_dotenv() -> None:
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _db_path() -> str:
    _load_dotenv()
    url = os.environ.get("DAAS_DATABASE_URL", f"sqlite:///{REPO_ROOT / 'mcp' / 'daas.db'}")
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if path == ":memory:":
            return path
        # sqlite:////abs/path -> "/abs/path" (absolute); sqlite:///rel/path -> repo-rooted.
        if os.path.isabs(path):
            return path
        return str((REPO_ROOT / path).resolve())
    raise SystemExit(f"unsupported DAAS_DATABASE_URL (expected sqlite:///...): {url}")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def list_docs() -> None:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, name, source_type, source_ref, page_count, chunk_count, "
            "status, created_at FROM pdf_documents ORDER BY created_at DESC"
        ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"no pdf_documents table yet (ingest a document first): {e}", file=sys.stderr)
        return
    if not rows:
        print("(no pdf documents ingested yet)")
        return
    for r in rows:
        print(f"[{r['id']}] {r['name']}  type={r['source_type']}  "
              f"pages={r['page_count']}  chunks={r['chunk_count']}  "
              f"status={r['status']}  created={r['created_at']}")
        if r["source_ref"]:
            print(f"    source_ref: {r['source_ref']}")


def show_doc(doc_id: int) -> None:
    conn = _connect()
    try:
        d = conn.execute("SELECT * FROM pdf_documents WHERE id=?", (doc_id,)).fetchone()
    except sqlite3.OperationalError as e:
        print(f"no pdf_documents table: {e}", file=sys.stderr)
        return
    if d is None:
        print(f"document {doc_id} not found")
        return
    print(f"doc {d['id']}: {d['name']}")
    print(f"  source: {d['source_type']}  ref={d['source_ref']}  url={d['url']}")
    print(f"  pages={d['page_count']}  chunks={d['chunk_count']}  status={d['status']}")
    print(f"  embedding: {d['embedding_model']} (dim {d['embedding_dim']})  hash={d['file_hash']}")
    print("  chunks:")
    for c in conn.execute(
        "SELECT chunk_index, page_number, substr(text,1,120) AS preview "
        "FROM pdf_chunks WHERE doc_id=? ORDER BY chunk_index",
        (doc_id,),
    ):
        print(f"    [{c['chunk_index']}] p{c['page_number']}: {c['preview']}...")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--doc":
        show_doc(int(sys.argv[2]))
    else:
        list_docs()
