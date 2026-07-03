"""Thin CLI sidecar used by the dashboard's Next.js API routes to write to
`daas.db`. One process per call — slow but simple, and writes are infrequent.

Usage:
  python collection_writer.py <command> --json '{"...": "..."}'

Commands:
  create        : {"name": "...", "description": "..."}
  rename        : {"old_name": "...", "new_name": "..."}
  update        : {"name": "...", "new_name"?: "...", "description"?: "..."}
  delete        : {"name": "..."}
  add-item      : {"collection_name": "...", "source_name": "...", "section_name": "..." | null}
  remove-item   : {"collection_name": "...", "source_name": "...", "section_name": "..." | null}
  reorder       : {"collection_name": "...", "ordered_item_ids": [int, ...]}

Output: one JSON line on stdout. On error, exit code != 0 and `{"error": "..."}`
on stderr (also mirrored to stdout for callers that don't separate streams).
ponytail: single-file CLI, no click, no fancy dispatch.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling modules importable when invoked via `uv run ... python collection_writer.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load .env exactly like server.py does so DAAS_DATABASE_URL is set.
# The repo-root .env (cli-anything/.env) is where DAAS_DATABASE_URL is
# actually defined; parent.parent is mcp/ (whose .env doesn't exist), so use
# parents[2] to reach the repo root. Per-MCP .env still overrides.
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]  # cli-anything/
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

from daas_database import get_database  # noqa: E402
from registry_service import RegistryService  # noqa: E402


def _service() -> RegistryService:
    return RegistryService(get_database().get_session())


def _fail(msg: str) -> None:
    payload = json.dumps({"error": msg})
    print(payload, file=sys.stderr)
    print(payload)  # mirror for naive callers
    sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["create", "rename", "update", "delete", "add-item", "remove-item", "reorder"],
    )
    parser.add_argument(
        "--json",
        dest="json_args",
        default="{}",
        help="JSON object of arguments for the command",
    )
    ns = parser.parse_args(argv)

    try:
        args = json.loads(ns.json_args)
    except json.JSONDecodeError as e:
        _fail(f"Invalid --json payload: {e}")
        return 1

    svc = _service()
    try:
        if ns.command == "create":
            out = svc.create_collection(
                name=args["name"],
                description=args.get("description"),
            )
        elif ns.command == "rename":
            out = svc.rename_collection(
                old_name=args["old_name"],
                new_name=args["new_name"],
            )
        elif ns.command == "update":
            out = svc.update_collection(
                name=args["name"],
                new_name=args.get("new_name"),
                description=args.get("description"),
            )
        elif ns.command == "delete":
            out = svc.delete_collection(name=args["name"])
        elif ns.command == "add-item":
            out = svc.add_to_collection(
                collection_name=args["collection_name"],
                source_name=args["source_name"],
                section_name=args.get("section_name"),
            )
        elif ns.command == "remove-item":
            out = svc.remove_from_collection(
                collection_name=args["collection_name"],
                source_name=args["source_name"],
                section_name=args.get("section_name"),
            )
        elif ns.command == "reorder":
            out = svc.reorder_collection_items(
                collection_name=args["collection_name"],
                ordered_item_ids=list(args["ordered_item_ids"]),
            )
        else:
            _fail(f"Unknown command: {ns.command}")
            return 1
    except KeyError as e:
        _fail(f"Missing required arg: {e}")
        return 1
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")
        return 1

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
