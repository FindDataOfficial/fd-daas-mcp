"""Seed the leader_upstreams registry from .mcp.json.

Reads every non-`leader-mcp` entry from the repo-root `.mcp.json` and
upserts it into the `leader_upstreams` table, so leader-mcp can launch
them on demand as the single client-facing entry point.

The 10 data-fetch MCPs keep their short names (via `DATA_FETCH_MCPS`)
for back-compat with `ask_data_crew` / the crewai-data-workflow; all
other non-leader MCPs use their full `.mcp.json` key as `name`.

Idempotent: re-running updates existing rows by name, never duplicates.

Usage (from anywhere, via uv):
    uv run --directory mcp/leader-mcp python seed_upstreams.py --dry-run
    uv run --directory mcp/leader-mcp python seed_upstreams.py
    uv run --directory mcp/leader-mcp python seed_upstreams.py --unseed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the shared schema package (`models`) importable, mirroring server.py.
_HERE = Path(__file__).resolve().parent
_MCP_ROOT = _HERE.parent  # mcp/
if str(_MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCP_ROOT))

from dotenv import load_dotenv

load_dotenv(_MCP_ROOT / ".env")
load_dotenv(_HERE / ".env", override=True)

from gateway_database import get_gateway_db, reset_gateway_db  # noqa: E402

# Short-name map for the 10 data-fetch MCPs (`.mcp.json` key → leader_upstreams.name).
# Used so `ask_data_crew` / the crewai-data-workflow keep resolving by short name.
# All other non-leader MCPs use their full `.mcp.json` key as `name`.
DATA_FETCH_MCPS: dict[str, str] = {
    "akshare-mcp": "akshare",
    "yfinance-mcp": "yfinance",
    "edgartools-mcp": "edgartools",
    "edinet-mcp": "edinet",
    "dartlab-mcp": "dartlab",
    "cnreport-mcp": "cnreport",
    "hkreport-mcp": "hkreport",
    "ckan-mcp": "ckan",
    "cnstats-mcp": "cnstats",
    "worldbank-mcp": "worldbank",
}

# The gateway itself — never seeded as an upstream (would self-recurse).
SELF_NAME = "leader-mcp"

_REPO_ROOT = _MCP_ROOT.parent
_MCP_JSON = _REPO_ROOT / ".mcp.json"


def _load_mcp_json() -> dict:
    if not _MCP_JSON.exists():
        raise FileNotFoundError(f".mcp.json not found at {_MCP_JSON}")
    with open(_MCP_JSON) as f:
        return json.load(f)


def _entry_to_upstream(key: str, short_name: str, entry: dict) -> dict:
    """Map a .mcp.json mcpServers entry to a leader_upstreams row dict."""
    return {
        "name": short_name,
        "transport": entry.get("type", "stdio"),
        "command": entry.get("command"),
        "args": entry.get("args") or [],
        "env": entry.get("env") or None,
        "cwd": entry.get("cwd"),
        "enabled": True,
        "description": f"MCP upstream {key} (seeded from .mcp.json)",
    }


def _upstream_to_mcpjson_entry(row: dict) -> dict:
    """Reconstruct a .mcp.json mcpServers entry from a leader_upstreams row."""
    entry: dict = {"type": row.get("transport") or "stdio"}
    if row.get("command"):
        entry["command"] = row["command"]
    if row.get("args"):
        entry["args"] = row["args"]
    if row.get("env"):
        entry["env"] = row["env"]
    if row.get("cwd"):
        entry["cwd"] = row["cwd"]
    return entry


def seed(dry_run: bool = False) -> int:
    data = _load_mcp_json()
    servers = data.get("mcpServers", {})
    planned: list[dict] = []
    for key, entry in servers.items():
        if key == SELF_NAME:
            continue  # the gateway itself — never seed as an upstream
        # data-fetch MCPs keep their short names; others use the full .mcp.json key
        short_name = DATA_FETCH_MCPS.get(key, key)
        planned.append(_entry_to_upstream(key, short_name, entry))

    print(f"Planned upserts: {len(planned)} upstream(s)")
    for p in planned:
        print(f"  - {p['name']:<22} {p['command']} {' '.join(p['args'])}")

    if dry_run:
        print("\n[dry-run] No rows written.")
        return 0

    db = get_gateway_db()
    written = 0
    for p in planned:
        db.upsert_upstream(**p)
        written += 1
    print(f"\nSeeded {written} upstream(s) into leader_upstreams.")
    return 0


def unseed() -> int:
    """Delete every seeded upstream and print the .mcp.json snippet for rollback.

    Reads rows from the DB (not .mcp.json) so it still works after .mcp.json has
    been reduced to the single leader-mcp entry. The snippet reconstructs each
    row's .mcp.json key: data-fetch short names invert via DATA_FETCH_MCPS, all
    other names are their own key.
    """
    db = get_gateway_db()
    rows = db.list_upstreams(include_disabled=True)
    if not rows:
        print("No leader_upstreams rows found. Nothing to remove.")
        return 0

    # Print the .mcp.json snippet for rollback BEFORE deleting.
    snippet: dict = {}
    short_to_key = {v: k for k, v in DATA_FETCH_MCPS.items()}
    for row in rows:
        # data-fetch short name → original .mcp.json key; full-key name → itself
        key = short_to_key.get(row["name"], row["name"])
        snippet[key] = _upstream_to_mcpjson_entry(row)
    print("# ── .mcp.json mcpServers snippet for rollback ──")
    print(json.dumps(snippet, indent=2))

    for row in rows:
        db.delete_upstream(row["name"])
    print(f"\nDeleted {len(rows)} row(s) from leader_upstreams.")
    print("Restore direct connection by pasting the snippet above into .mcp.json mcpServers.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed leader_upstreams from .mcp.json")
    parser.add_argument("--dry-run", action="store_true", help="Print planned upserts, write nothing.")
    parser.add_argument("--unseed", action="store_true", help="Delete seeded rows and print the .mcp.json snippet for rollback.")
    args = parser.parse_args(argv)

    if args.unseed:
        return unseed()
    return seed(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
