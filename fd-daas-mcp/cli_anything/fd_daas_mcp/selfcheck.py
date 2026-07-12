"""Offline self-check for the consolidated fd-daas-mcp server.

No network, no LLM. Verifies:
  1. registered tools (>= 170 baseline; 6 core groups always present)
  2. the known collisions are namespaced (present as bare names in 2+ groups)
  3. colliding leaf modules (registry_service, database) resolve to distinct files
  4. no APScheduler thread started (cron suppression worked)

Run: ``uv run --directory fd-daas-mcp python -m cli_anything.fd_daas_mcp.selfcheck``
"""
from __future__ import annotations

import os
import sys
import threading
from collections import Counter
from pathlib import Path

from cli_anything.fd_daas_mcp import registry

# Load the repo .env so DAAS_DATABASE_URL is set before any group loads (cron's
# init_db opens the DB at import). cwd may be fd-daas-mcp/ under `uv run
# --directory`, so resolve the repo root from this file's location and make a
# relative sqlite URL absolute against it.
_REPO = Path(__file__).resolve().parents[3]
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO / ".env")
except ImportError:
    pass
_u = os.environ.get("DAAS_DATABASE_URL", "")
if _u.startswith("sqlite:///") and not _u.startswith("sqlite:////"):
    _rel = _u[len("sqlite:///"):]
    if not os.path.isabs(_rel):
        os.environ["DAAS_DATABASE_URL"] = f"sqlite:///{_REPO}/{_rel}"

CORE = {"alerts", "cron", "composite", "daas", "dashboard", "leader"}
OPTIONAL = {"pdf", "scrapling", "firecrawl", "cnreport", "massive"}
EXPECTED_COLLISIONS = {
    "search_functions", "run_rule",
    "list_datasources", "list_categories", "get_function_detail",
}


def main() -> int:
    registry.reset_cache()
    tools = registry.build()

    counts = Counter(g for g, _, _ in tools)
    print(f"[1] registered tools: {len(tools)}")
    for g in ["alerts", "cron", "composite", "daas", "dashboard", "leader",
              "pdf", "scrapling", "firecrawl", "cnreport", "massive"]:
        n = counts.get(g, 0)
        suffix = ""
        if g in OPTIONAL:
            suffix = f" (optional, {'installed' if n else 'absent'})"
        print(f"    {g}: {n}{suffix}")

    missing_core = CORE - set(counts.keys())
    assert not missing_core, f"missing core groups: {missing_core}"
    assert len(tools) >= 170, f"too few tools: {len(tools)} (expected >= 170, 6-core baseline)"

    print("[2] collisions")
    coll = registry.collisions()
    print(f"    {len(coll)} collisions: {sorted(coll.keys())}")
    missing_coll = EXPECTED_COLLISIONS - set(coll.keys())
    assert not missing_coll, f"missing expected collisions: {missing_coll}"

    print("[3] leaf-module isolation")
    leaf = registry.leaf_isolation_check()
    for name, files in leaf.items():
        paths = set(files.values())
        ok = len(paths) == len(files) and len(paths) >= 2
        print(f"    {name}: {len(paths)} distinct file(s) ({'OK' if ok else 'FAIL'})")
        assert ok, f"{name} not isolated: {files}"

    print("[4] scheduler threads after load")
    threads = [t.name for t in threading.enumerate()
               if "apscheduler" in t.name.lower() or "scheduler" in t.name.lower()]
    print(f"    {threads or 'none'}")
    assert not threads, f"scheduler thread started: {threads}"

    print(f"\n[5] total: {len(tools)} tools across {len(counts)} groups")
    print("\n=== SELF-CHECK PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
