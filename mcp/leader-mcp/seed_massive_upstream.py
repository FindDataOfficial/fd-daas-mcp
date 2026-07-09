"""Seed the `massive` leader_upstreams row for the massive-mcp launch shim.

massive-mcp is a launch shim over the upstream `mcp_massive` package
(github.com/massive-com/mcp_massive@v0.10.0), NOT a migrated .mcp.json entry,
so seed_upstreams.py (which reads .mcp.json) does not cover it. This script
upserts the `massive` row directly into leader_upstreams so leader-mcp's
gateway can launch it on demand via
`uv run --directory mcp/massive-mcp python server.py`.

env=NULL: the spawned subprocess inherits leader-mcp's parent env, where
MASSIVE_API_KEY already lives after leader-mcp's own load_dotenv. The key is
never stored in daas.db (which is tracked in git).

Idempotent on name (upsert). Flags: --dry-run (plan, write nothing), --unseed
(delete the row + print a rollback note).

Usage:
    uv run --directory mcp/leader-mcp python seed_massive_upstream.py --dry-run
    uv run --directory mcp/leader-mcp python seed_massive_upstream.py
    uv run --directory mcp/leader-mcp python seed_massive_upstream.py --unseed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # mcp/leader-mcp/
_MCP_ROOT = _HERE.parent  # mcp/
_REPO_ROOT = _MCP_ROOT.parent  # repo root
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_HERE / ".env", override=True)

from gateway_database import get_gateway_db  # noqa: E402

MASSIVE_DIR = _REPO_ROOT / "mcp" / "massive-mcp"

MASSIVE_UPSTREAM = {
    "name": "massive",
    "transport": "stdio",
    "command": "uv",
    "args": ["run", "--directory", str(MASSIVE_DIR), "python", "server.py"],
    "env": None,
    "enabled": True,
    "description": "Massive.com financial data MCP (search_endpoints / call_api / query_data)",
}


def seed(dry_run: bool = False) -> int:
    print(f"Planned upsert: name={MASSIVE_UPSTREAM['name']}")
    print(f"  command: {MASSIVE_UPSTREAM['command']} {' '.join(MASSIVE_UPSTREAM['args'])}")
    print("  env: None (inherits parent env; MASSIVE_API_KEY flows from root .env)")
    print(f"  enabled: {MASSIVE_UPSTREAM['enabled']}")
    if dry_run:
        print("\n[dry-run] No rows written.")
        return 0
    db = get_gateway_db()
    row = db.upsert_upstream(**MASSIVE_UPSTREAM)
    print(
        f"\nSeeded upstream: name={row['name']} enabled={row['enabled']} "
        f"env_json={row.get('env_json')}"
    )
    return 0


def unseed() -> int:
    db = get_gateway_db()
    row = db.get_upstream("massive")
    if row is None:
        print("No leader_upstreams row for 'massive'. Nothing to remove.")
        return 0
    db.delete_upstream("massive")
    print("Deleted leader_upstreams row: name=massive")
    print("Rollback: re-run `python seed_massive_upstream.py` to restore it.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed the massive leader_upstreams row.")
    p.add_argument("--dry-run", action="store_true", help="Print the plan; write nothing.")
    p.add_argument("--unseed", action="store_true", help="Delete the massive upstream row.")
    args = p.parse_args(argv)
    if args.unseed:
        return unseed()
    return seed(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
