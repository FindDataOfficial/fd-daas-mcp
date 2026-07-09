#!/usr/bin/env python3
"""Load the FULL World Bank indicator catalog (~16k indicators) into the daas
database as `wbdata_*` functions under the `wbdata` source.

Unlike load_registry_json.py (which reads a static JSON seed), this script
fetches the live indicator catalog via world_bank_data.get_indicators() and
bulk-upserts one daas_function per indicator. Run it once on a machine with
network access to api.worldbank.org; it is idempotent (re-runs update in place).

Prerequisite: the `wbdata` source must already exist in the DB. Load the seed
first via load_registry_json.py (which also registers entities + indicator
rules), then run this to expand the function catalog:

    uv run --directory mcp/daas-mcp \\
      python <repo>/.trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py \\
      <repo>/.trae/skills/fd-daas-data-fetch/references/wbdata.registry.json

    uv run --directory mcp/daas-mcp \\
      python <repo>/.trae/skills/fd-daas-data-fetch/scripts/load_wbdata_catalog.py [--dry-run]

The DB URL is read from DAAS_DATABASE_URL (root .env, default sqlite:///mcp/daas.db).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

# --- make daas-mcp + models + harness importable regardless of cwd ----------
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[4]  # scripts/ -> skill -> skills -> .trae -> repo
for _p in (
    _REPO_ROOT / "mcp" / "daas-mcp",
    _REPO_ROOT / "mcp",
    _REPO_ROOT / "daas-agent-harness",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dotenv import load_dotenv  # noqa: E402

from daas_database import get_database  # noqa: E402
from models.models import DaasSource, DaasFunction  # noqa: E402
from load_registry_json import _load_env, _upsert_function  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Load the full wbdata indicator catalog into the daas DB.")
    ap.add_argument("--env", help="Path to a .env file (default: repo root .env).")
    ap.add_argument("--dry-run", action="store_true", help="Fetch + print, do not write.")
    args = ap.parse_args()

    _load_env(args.env)
    db_url = os.environ.get("DAAS_DATABASE_URL", "(unset → default mcp/daas.db)")
    print(f"DB URL: {db_url}")

    # Lazy import so the script can still print help without the package.
    from cli_anything.daas.sources.wbdata_source import WbDataAdapter

    adapter = WbDataAdapter()
    if not adapter.is_available():
        print("ERROR: world_bank_data is not installed. Run `uv pip install world_bank_data`.")
        return 2

    print("Fetching full indicator catalog via world_bank_data.get_indicators() ...")
    try:
        functions = adapter.discover_full()
    except Exception as e:
        print(f"ERROR fetching catalog (network required): {type(e).__name__}: {e}")
        return 1
    print(f"Fetched {len(functions)} indicators.")

    db = get_database()
    session = db.get_session()
    new_count = 0
    try:
        src = session.query(DaasSource).filter(DaasSource.name == "wbdata").first()
        if src is None:
            print("ERROR: source 'wbdata' not in DB. Run load_registry_json.py with "
                  "wbdata.registry.json first to register the source + entities.")
            return 2

        for fn_data in functions:
            if _upsert_function(session, src.id, fn_data):
                new_count += 1

        cats = Counter(f["category"] for f in functions)
        print(f"functions: {len(functions)} processed ({new_count} new)")
        print("category distribution:")
        for cat, n in cats.most_common():
            print(f"  {cat:14s} {n}")

        if args.dry_run:
            session.rollback()
            print("[DRY RUN] rolled back, no changes committed.")
        else:
            session.commit()
            print("committed.")

        # Show total wbdata functions now in the DB.
        total = (session.query(DaasFunction)
                 .filter(DaasFunction.source_id == src.id).count())
        print(f"total wbdata functions in DB: {total}")
    except Exception as e:
        session.rollback()
        print(f"ERROR: {type(e).__name__}: {e}")
        return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
