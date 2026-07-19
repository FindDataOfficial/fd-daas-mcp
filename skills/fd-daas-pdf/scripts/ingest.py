#!/usr/bin/env python3
"""ingest.py - thin wrapper that runs pdf_ingest_document via the fd-daas-mcp CLI.

The embedding engine + sqlite-vec live in fd-daas-mcp/pdf-mcp/, so this shells
out to the consolidated CLI rather than reimplementing ingest. Uses
.venv/bin/python (uv run is broken for fd-daas-mcp).

Usage:
  uv run python scripts/ingest.py /path/to/file.pdf [key=value ...]
  uv run python scripts/ingest.py https://example.com/filing.pdf [key=value ...]

Extra key=value pairs are forwarded (e.g. chunk_size=800 name=mydoc).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PY = REPO_ROOT / "fd-daas-mcp" / ".venv" / "bin" / "python"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: ingest.py <path|url> [key=value ...]", file=sys.stderr)
        sys.exit(2)
    target = sys.argv[1]
    extra = sys.argv[2:]
    if target.startswith("http"):
        kv = [f"url={target}"] + extra
    else:
        kv = [f"file_path={target}"] + extra
    cmd = [str(PY), "-m", "fd_daas_mcp.cli", "pdf",
           "ingest_document", *kv, "--json"]
    sys.exit(subprocess.call(cmd, cwd=str(REPO_ROOT)))


if __name__ == "__main__":
    main()
