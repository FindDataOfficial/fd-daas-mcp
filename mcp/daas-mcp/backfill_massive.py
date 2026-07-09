"""Backfill Massive.com Economy endpoints into scraw_massive_* tables in daas.db.

Standalone script (run via `uv run --directory mcp/daas-mcp python backfill_massive.py`).
Builds a PERSISTENT fastmcp.Client against the `massive` upstream (the gateway's
per-call spawn tears down the subprocess, so store_as tables don't survive a
second call — a persistent client is required), then for each Economy endpoint:

  1. call_api(path, store_as=<slug>)         — fetch + store in-memory (DuckDB)
  2. query_data("SELECT * FROM <slug>")       — returns CSV text (header + rows)
  3. CREATE TABLE IF NOT EXISTS scraw_massive_<slug> (date TEXT, <col> REAL, ...)
  4. INSERT OR REPLACE rows keyed on `date`   — idempotent re-run

Routes around the known-broken daas-mcp pipeline-bridge (server-context
_cron_call fails; add_pipeline_item/sync_pipeline_cron silently fail) by being
a standalone process with its own fastmcp.Client — no daas-mcp server context.

Auth: MASSIVE_API_KEY is loaded from the repo-root .env (the massive-mcp shim
inherits it; the persistent client inherits this process's env).

Usage:
    uv run --directory mcp/daas-mcp python backfill_massive.py                # all Economy endpoints
    uv run --directory mcp/daas-mcp python backfill_massive.py --only treasury_yields
    uv run --directory mcp/daas-mcp python backfill_massive.py --drop          # drop scraw_massive_* tables
    uv run --directory mcp/daas-mcp python backfill_massive.py --dry-run       # fetch + print, no writes
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import os
import re
import sys
from pathlib import Path

from sqlalchemy import text

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent
sys.path.insert(0, str(_THIS.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from daas_database import Database  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402

_MASSIVE_DIR = _REPO_ROOT / "mcp" / "massive-mcp"
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# Economy endpoints to backfill. slug → (daas_function name, path, fetch params).
# These are the indicator-bearing endpoints (all entitlement-confirmed, all
# `date` + numeric columns).
ENDPOINTS: dict[str, tuple] = {
    "treasury_yields": ("economy_treasury_yields", "/fed/v1/treasury-yields", {"limit": 5000}),
    "inflation": ("economy_inflation", "/fed/v1/inflation", {"limit": 1000}),
    "inflation_expectations": ("economy_inflation_expectations", "/fed/v1/inflation-expectations", {"limit": 1000}),
    "labor_market": ("economy_labor_market", "/fed/v1/labor-market", {"limit": 1000}),
}


def _build_transport() -> StdioTransport:
    return StdioTransport(
        command="uv",
        args=["run", "--directory", str(_MASSIVE_DIR), "python", "server.py"],
    )


async def _fetch_csv(client: Client, store_as: str, path: str, params: dict) -> tuple[list[str], list[list[str]]]:
    """call_api (store) then query_data (SELECT *) → (columns, rows)."""
    await client.call_tool("call_api", {"path": path, "params": params, "store_as": store_as})
    res = await client.call_tool("query_data", {"sql": f"SELECT * FROM {store_as}"})
    csv_text = res.content[0].text
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _create_table(engine, table: str, columns: list[str]) -> None:
    for c in columns:
        if not _IDENT_RE.match(c):
            raise ValueError(f"unsafe column name: {c!r}")
    if not _IDENT_RE.match(table):
        raise ValueError(f"unsafe table name: {table!r}")
    col_defs = ["date TEXT PRIMARY KEY"]
    for c in columns:
        if c == "date":
            continue
        col_defs.append(f"{c} REAL")
    ddl = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})"
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _upsert(engine, table: str, columns: list[str], rows: list[list[str]]) -> int:
    if not rows:
        return 0
    cols = [c for c in columns]
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    payload = []
    for r in rows:
        if len(r) < len(cols):
            r = r + [""] * (len(cols) - len(r))
        elif len(r) > len(cols):
            r = r[: len(cols)]
        d = {}
        for i, c in enumerate(cols):
            v = r[i]
            if c != "date" and v == "":
                v = None
            d[c] = v
        payload.append(d)
    with engine.begin() as conn:
        conn.execute(text(sql), payload)
    return len(payload)


async def backfill(engine, transport: StdioTransport, only: str | None, dry_run: bool) -> None:
    async with Client(transport) as client:
        for slug, (fn_name, path, params) in ENDPOINTS.items():
            if only and slug != only:
                continue
            table = f"scraw_massive_{slug}"
            print(f"== {slug} ({path}) → {table} ==")
            columns, rows = await _fetch_csv(client, slug, path, params)
            if not columns:
                print("  no columns returned — skipping")
                continue
            print(f"  fetched {len(rows)} rows, columns: {columns}")
            if dry_run:
                print("  [dry-run] no writes")
                continue
            if "date" not in columns:
                print("  WARNING: no 'date' column in response — skipping (upsert key)")
                continue
            # order columns: date first, then the rest in response order
            ordered = ["date"] + [c for c in columns if c != "date"]
            _create_table(engine, table, ordered)
            n = _upsert(engine, table, ordered, rows)
            print(f"  upserted {n} rows into {table}")


def _drop(engine) -> None:
    for slug in ENDPOINTS:
        table = f"scraw_massive_{slug}"
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        print(f"  dropped {table}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backfill Massive.com Economy endpoints into scraw_massive_* tables.")
    p.add_argument("--only", help="Only backfill this slug (e.g. treasury_yields)")
    p.add_argument("--drop", action="store_true", help="Drop the scraw_massive_* tables and exit")
    p.add_argument("--dry-run", action="store_true", help="Fetch + print; no writes")
    args = p.parse_args(argv)

    Database._instance = None
    db = Database()
    engine = db._engine

    if args.drop:
        print("Dropping scraw_massive_* tables...")
        _drop(engine)
        print("Done.")
        return 0

    if not os.environ.get("MASSIVE_API_KEY"):
        print("WARNING: MASSIVE_API_KEY not set — the massive subprocess will fail to start.", file=sys.stderr)

    print("Starting persistent massive client (one-time endpoint-index build ~3s)...")
    asyncio.run(backfill(engine, _build_transport(), args.only, args.dry_run))
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
