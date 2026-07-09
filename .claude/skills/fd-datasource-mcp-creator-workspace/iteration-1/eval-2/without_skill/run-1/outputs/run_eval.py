#!/usr/bin/env python3
"""
Extend the canonical indicator vocabulary for an upcoming commodities futures
source, then verify the matcher resolves the three new columns.

Runs ENTIRELY against a throwaway DB (DAAS_DATABASE_URL env var, set below).
Does NOT touch the real mcp/daas.db.

Pipeline (all in-process, using the REAL setup parser + REAL matcher logic
from the fd-datasource-mcp-creator skill scripts):
  1. Bootstrap daas tables via daas_database.Database (creates all daas tables).
  2. Create canonical_indicators + column_indicator_mappings tables (inline
     models, same as setup_indicator_vocabulary.py) + seed the existing
     vocabulary by parsing references/canonical-indicators.md with the setup
     script's own parser.
  3. Insert the 3 new commodity indicators (settle_price, open_interest,
     warehouse_stocks) into canonical_indicators.
  4. Register a throwaway source `commodities_futures` + function
     `futures_daily` with the 3 columns.
  5. Run the matcher (match_columns_to_indicators._match + _load_canonical)
     against the source, upsert into column_indicator_mappings.
  6. Print the resulting mappings + a verification summary.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── 0. Pin the throwaway DB BEFORE any daas import ─────────────────────────
_THROWAWAY_DB = "sqlite:////tmp/fd-dsc-eval/eval2-without/commodities.db"
os.environ["DAAS_DATABASE_URL"] = _THROWAWAY_DB

# Walk up to find the repo root (dir containing both `mcp/` and `.claude/`).
_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / "mcp").is_dir() or not (_REPO_ROOT / ".claude").is_dir():
    if _REPO_ROOT.parent == _REPO_ROOT:
        raise SystemExit("could not locate repo root")
    _REPO_ROOT = _REPO_ROOT.parent
DAAS_MCP = _REPO_ROOT / "mcp" / "daas-mcp"
SKILL = _REPO_ROOT / ".claude" / "skills" / "fd-datasource-mcp-creator"

sys.path.insert(0, str(DAAS_MCP))
sys.path.insert(0, str(SKILL / "scripts"))

# ── 1. Bootstrap daas tables ───────────────────────────────────────────────
from daas_database import Database  # noqa: E402
from models import (  # noqa: E402
    Base, DaasSource, DaasFunction, DaasFunctionColumn,
)

db = Database()  # reads DAAS_DATABASE_URL → throwaway; create_all → daas tables
engine = db.engine
print(f"[1] Bootstrapped daas tables at {_THROWAWAY_DB}")

# ── 2. Create canonical tables + seed existing vocabulary ──────────────────
# Import the inline models (declared on the same Base.metadata) + parser.
import setup_indicator_vocabulary as setup  # noqa: E402

Base.metadata.create_all(engine)  # creates canonical_indicators + column_indicator_mappings
md_path = SKILL / "references" / "canonical-indicators.md"
seed_rows = setup._parse_seed(md_path)
session = db.get_session()
try:
    for row in seed_rows:
        existing = session.execute(
            setup.select(setup.CanonicalIndicator).where(
                setup.CanonicalIndicator.name == row["name"]
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(setup.CanonicalIndicator(**row))
    session.commit()
    n_existing = session.execute(
        setup.select(setup.CanonicalIndicator)
    ).scalars().all()
    print(f"[2] Seeded {len(n_existing)} existing canonical indicators from {md_path.name}")
finally:
    session.close()

# ── 3. Insert the 3 new commodity indicators ───────────────────────────────
NEW_INDICATORS = [
    {
        "name": "settle_price",
        "label": "Settlement price",
        "unit": "currency",
        "semantic_type": "price",
        "category": "market-data",
        "aliases": [
            "settlement_price", "settlement", "settle", "结算价", "结算", "Settle",
        ],
        "description": "Official daily settlement price for a futures/derivatives contract.",
    },
    {
        "name": "open_interest",
        "label": "Open interest",
        "unit": "count",
        "semantic_type": "count",
        "category": "market-data",
        "aliases": [
            "openinterest", "open interest", "OI", "持仓量", "持仓", "OpenInterest",
        ],
        "description": "Number of outstanding (unsettled) derivative contracts.",
    },
    {
        "name": "warehouse_stocks",
        "label": "Warehouse stocks",
        "unit": "count",
        "semantic_type": "count",
        "category": "alternative",
        "aliases": [
            "warehouse_inventory", "inventory", "stocks",
            "库存", "仓单库存", "warehouse_stock",
        ],
        "description": "Physical inventory of a commodity held in registered warehouses.",
    },
]

session = db.get_session()
try:
    for row in NEW_INDICATORS:
        existing = session.execute(
            setup.select(setup.CanonicalIndicator).where(
                setup.CanonicalIndicator.name == row["name"]
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(setup.CanonicalIndicator(**row))
    session.commit()
    total = session.execute(setup.select(setup.CanonicalIndicator)).scalars().all()
    print(f"[3] Inserted {len(NEW_INDICATORS)} new commodity indicators "
          f"(canonical_indicators now {len(total)} rows)")
finally:
    session.close()

# ── 4. Register throwaway source + function + 3 columns ───────────────────
session = db.get_session()
try:
    src = DaasSource(
        name="commodities_futures",
        label="Commodities Futures (throwaway eval)",
        description="Throwaway datasource for vocabulary-extension-commodities eval.",
        url=None,
        enabled=True,
    )
    session.add(src)
    session.flush()  # get src.id
    fn = DaasFunction(
        source_id=src.id,
        name="futures_daily",
        label="Daily futures quote",
        description="Daily settle / open interest / warehouse stocks.",
        category="market-data",
        parameters=[],
        output_type="DataFrame",
    )
    session.add(fn)
    session.flush()  # get fn.id
    for col_name, col_type in [
        ("settle_price", "REAL"),
        ("open_interest", "REAL"),
        ("warehouse_stocks", "REAL"),
    ]:
        session.add(DaasFunctionColumn(
            function_id=fn.id,
            name=col_name,
            label=col_name.replace("_", " ").title(),
            type=col_type,
            description=f"{col_name} column (commodities futures)",
            nullable=True,
        ))
    session.commit()
    src_id = src.id
    fn_id = fn.id
    print(f"[4] Registered source 'commodities_futures' (id={src_id}), "
          f"function 'futures_daily' (id={fn_id}), 3 columns")
finally:
    session.close()

# ── 5. Run the matcher ────────────────────────────────────────────────────
import match_columns_to_indicators as matcher  # noqa: E402

session = db.get_session()
try:
    canonical = matcher._load_canonical(session)
    cols = session.execute(
        __import__("sqlalchemy").text(
            "SELECT f.name AS fn, c.name AS col "
            "FROM daas_function_columns c "
            "JOIN daas_functions f ON f.id = c.function_id "
            "JOIN sources s ON s.id = f.source_id "
            "WHERE s.name = 'commodities_futures' "
            "ORDER BY f.name, c.name"
        )
    ).fetchall()

    print(f"\n[5] Matcher: {len(cols)} columns to match against "
          f"{len(canonical)} canonical indicators\n")
    print(f"  {'column':<20} {'method':<8} {'conf':<6} {'confirmed':<10} → indicator")
    print(f"  {'-'*20} {'-'*8} {'-'*6} {'-'*10}   {'-'*20}")
    confirmed = 0
    for fn_name, col in cols:
        indicator, method, conf = matcher._match(col, canonical)
        is_confirmed = method in ("exact", "alias")
        if is_confirmed:
            confirmed += 1
        # upsert the mapping (mirrors match_columns_to_indicators.run)
        session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO column_indicator_mappings "
                "(source, function_name, column_name, indicator_name, match_method, confidence, confirmed) "
                "VALUES (:src, :fn, :col, :ind, :m, :conf, :confd) "
                "ON CONFLICT(source, function_name, column_name) DO UPDATE SET "
                "  indicator_name=excluded.indicator_name, "
                "  match_method=excluded.match_method, "
                "  confidence=excluded.confidence, "
                "  confirmed=excluded.confirmed"
            ),
            {
                "src": "commodities_futures", "fn": fn_name, "col": col,
                "ind": indicator, "m": method, "conf": conf,
                "confd": 1 if is_confirmed else 0,
            },
        )
        print(f"  {col:<20} {method or '-':<8} {conf:<6.2f} {str(is_confirmed):<10} → {indicator}")
    session.commit()

    # ── 6. Final verification ──────────────────────────────────────────────
    all_maps = session.execute(
        __import__("sqlalchemy").text(
            "SELECT column_name, indicator_name, match_method, confidence, confirmed "
            "FROM column_indicator_mappings WHERE source='commodities_futures' "
            "ORDER BY column_name"
        )
    ).fetchall()
    print(f"\n[6] Verification: {len(all_maps)} mappings in column_indicator_mappings")
    ok = all(m[4] == 1 for m in all_maps) and len(all_maps) == 3
    for col, ind, method, conf, confd in all_maps:
        print(f"    {col:<20} → {ind:<20} [{method} {conf:.2f}] confirmed={confd}")
    print(f"\n  RESULT: {'PASS — all 3 columns matched & confirmed' if ok else 'FAIL'}")
finally:
    session.close()
