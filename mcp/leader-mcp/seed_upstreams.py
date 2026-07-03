"""Seed the leader_upstreams registry from .mcp.json.

Reads the 10 data-fetch MCP entries from the repo-root `.mcp.json` and
upserts them into the `leader_upstreams` table, so leader-mcp can launch
them on demand after they are removed from `.mcp.json`.

Idempotent: re-running updates existing rows by name, never duplicates.

Usage (from anywhere, via uv):
    uv run --directory mcp/leader-mcp python seed_upstreams.py --dry-run
    uv run --directory mcp/leader-mcp python seed_upstreams.py
    uv run --directory mcp/leader-mcp python seed_upstreams.py --unseed

The 10 data-fetch MCPs (`.mcp.json` key → leader_upstreams.name, with the
`-mcp` suffix stripped):
    akshare-mcp → akshare      yfinance-mcp → yfinance
    edgartools-mcp → edgar tools   edinet-mcp → edinet
    dartlab-mcp → dartlab      cnreport-mcp → cnreport
    hkreport-mcp → hkreport    ckan-mcp → ckan
    cnstats-mcp → cnstats      worldbank-mcp → worldbank
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

# `.mcp.json` key → leader_upstreams.name
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
        "description": f"Data-fetch MCP {key} (migrated from .mcp.json)",
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
    missing: list[str] = []
    for key, short_name in DATA_FETCH_MCPS.items():
        entry = servers.get(key)
        if entry is None:
            missing.append(key)
            continue
        planned.append(_entry_to_upstream(key, short_name, entry))

    if missing:
        print(f"Note: {len(missing)} data-fetch MCP(s) not present in .mcp.json "
              f"(already removed?): {', '.join(missing)}")

    print(f"Planned upserts: {len(planned)} upstream(s)")
    for p in planned:
        print(f"  - {p['name']:<12} {p['command']} {' '.join(p['args'])}")

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
    db = get_gateway_db()
    rows = []
    for short_name in DATA_FETCH_MCPS.values():
        row = db.get_upstream(short_name)
        if row is not None:
            rows.append(row)
    if not rows:
        print("No leader_upstreams rows found for the 10 data-fetch MCPs. Nothing to remove.")
        return 0

    # Print the .mcp.json snippet for rollback BEFORE deleting.
    snippet: dict = {}
    # invert short_name → key
    short_to_key = {v: k for k, v in DATA_FETCH_MCPS.items()}
    for row in rows:
        key = short_to_key.get(row["name"], row["name"] + "-mcp")
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
