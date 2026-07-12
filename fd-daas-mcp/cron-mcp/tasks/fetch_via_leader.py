"""cron task bridge: fetch historical data THROUGH leader-mcp.

Importing leader_tools.save_snapshot (not daas-mcp.fetch_data) is deliberate:
save_snapshot is leader-mcp's own fetch-and-store path — it calls the live
function, parses rows, upserts into data_snapshots, and updates last_fetched_at
on the Function row. So the fetch genuinely goes through leader-mcp.

Run (from repo root):
    uv run --directory mcp/leader-mcp python /abs/path/to/fetch_via_leader.py \
        --harness akshare --command stock_zh_a_hist \
        --params '{"symbol":"000001","period":"daily","start_date":"20250601","end_date":"20250630"}'

Exit code is non-zero on error so cron-mcp records the run as FAILED.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Make leader-mcp + shared models importable regardless of cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "mcp", "leader-mcp"))
sys.path.insert(0, os.path.join(_REPO, "mcp", "models"))

# leader_database reads DAAS_DATABASE_URL; default is mcp/daas.db.
os.environ.setdefault(
    "DAAS_DATABASE_URL", f"sqlite:///{os.path.join(_REPO, 'mcp', 'daas.db')}"
)

from leader_tools import save_snapshot  # noqa: E402  (after sys.path tweak)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch data through leader-mcp.save_snapshot.")
    ap.add_argument("--harness", required=True, help="Harness name, e.g. 'akshare'")
    ap.add_argument("--command", required=True, help="Function command, e.g. 'stock_zh_a_hist'")
    ap.add_argument(
        "--params",
        default="{}",
        help='JSON params for the function, e.g. \'{"symbol":"000001","period":"daily"}\'',
    )
    ap.add_argument(
        "--note", default="", help="Optional human note stored in the run log alongside the result"
    )
    args = ap.parse_args()

    # Validate params JSON early — save_snapshot would otherwise bury the error.
    try:
        json.loads(args.params)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"bad --params JSON: {e}"}))
        return 2

    try:
        result = save_snapshot(args.harness, args.command, args.params)
        ok = result.lower().startswith("snapshot saved") and "status=success" in result.lower()
        print(json.dumps(
            {
                "ok": ok,
                "harness": args.harness,
                "command": args.command,
                "params": json.loads(args.params),
                "note": args.note,
                "leader_result": result,
            },
            ensure_ascii=False,
        ))
        return 0 if ok else 1
    except Exception as e:
        print(json.dumps(
            {"ok": False, "harness": args.harness, "command": args.command, "error": str(e)},
            ensure_ascii=False,
        ))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
