#!/usr/bin/env python3
"""search.py - thin wrapper that runs pdf_search_documents via the fd-daas-mcp CLI.

Usage:
  uv run python scripts/search.py "revenue growth"
  uv run python scripts/search.py "dividend policy" doc_id=3 top_k=10

Extra key=value pairs are forwarded (e.g. doc_id=3 min_score=0.5 top_k=10).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PY = REPO_ROOT / "fd-daas-mcp" / ".venv" / "bin" / "python"


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: search.py "<query>" [key=value ...]', file=sys.stderr)
        sys.exit(2)
    query = sys.argv[1]
    extra = sys.argv[2:]
    kv = [f"query={query}"] + extra
    cmd = [str(PY), "-m", "daas.fd_daas_mcp.cli", "pdf",
           "search_documents", *kv, "--json"]
    sys.exit(subprocess.call(cmd, cwd=str(REPO_ROOT)))


if __name__ == "__main__":
    main()
