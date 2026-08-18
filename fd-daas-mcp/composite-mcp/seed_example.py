"""Seed an idempotent 'example' composite in mcp/daas.db so the shipped
.mcp.json entry (COMPOSITE=example) serves something out of the box.

Run:  cd mcp/composite-mcp && uv run python seed_example.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from composite_database import get_composite_db  # noqa: E402

AKSHARE_VENV = "~/code/daas/mcp/akshare-mcp/.venv/bin/fastmcp"
AKSHARE_CWD = "~/code/daas/mcp/akshare-mcp"


def main() -> None:
    db = get_composite_db()

    comp = db.get_composite_by_name("example")
    if comp is None:
        comp_row = db.create_composite("example", "Shipped example: a few akshare tools, proxied.")
        comp = db.get_composite_by_name("example")
        print(f"created composite 'example' (id={comp.id})")
    else:
        print(f"composite 'example' exists (id={comp.id})")

    upstreams = {u["key"] for u in db.list_upstreams(comp.id)}
    if "akshare" not in upstreams:
        db.add_upstream(
            comp.id, "akshare", "stdio",
            command=AKSHARE_VENV, args=["run", "server.py", "--no-banner"],
            cwd=AKSHARE_CWD,
        )
        print("added upstream 'akshare'")

    existing_tools = {(t["upstream_key"], t["tool_name"]) for t in db.list_composite_tools(comp.id)}
    for tool in ("list_categories", "list_functions", "search_functions"):
        if ("akshare", tool) not in existing_tools:
            db.add_tool(comp.id, "akshare", tool)
            print(f"added tool akshare/{tool}")

    print("\nexample composite now serves (on next composite-mcp start):")
    for t in db.list_composite_tools(comp.id):
        print(f"  - {t['upstream_key']}_{t['tool_name']}")


if __name__ == "__main__":
    main()
