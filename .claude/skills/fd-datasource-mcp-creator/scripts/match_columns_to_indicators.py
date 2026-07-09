#!/usr/bin/env python3
"""
match_columns_to_indicators.py — auto-map a source's columns to canonical indicators.

Reads `daas_function_columns` joined to `daas_functions` for <source>, matches
each column against `canonical_indicators` by:

  1. exact  — lower(column) == lower(canonical name)            → conf 1.0  (auto-confirmed)
  2. alias  — lower(column) in lower(aliases)                   → conf 0.95 (auto-confirmed)
  3. fuzzy  — difflib ratio ≥ 0.85 vs names+aliases             → conf = ratio (PROPOSED)

`exact` + `alias` auto-confirm (confirmed=1). `fuzzy` lands as a proposal
(confirmed=0) for human review. Unmatched columns are listed, not inserted.

Upserts on (source, function_name, column_name) — re-runnable.

Run from within mcp/daas-mcp/:

    uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/scripts/match_columns_to_indicators.py --source yfinance
    ... --source yfinance --dry-run
    ... --source yfinance --confirm-all      # mark every proposal confirmed
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent.parent.parent  # scripts/ → skill → .claude/skills/ → .claude → repo root
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

sys.path.insert(0, str(_REPO_ROOT / "mcp" / "daas-mcp"))

from sqlalchemy import text  # noqa: E402
from daas_database import Database  # noqa: E402


def _norm(s: str) -> str:
    """Normalize a column/alias for matching: lowercase, strip, drop punctuation.

    Keeps Unicode word chars (so Chinese names like 收盘 match their aliases).
    In Python 3, ``\\w`` is Unicode-aware by default for str patterns, so this
    preserves CJK characters while dropping spaces/underscores/punctuation.
    """
    return re.sub(r"[\W_]+", "", (s or "").lower(), flags=re.UNICODE)


def _load_canonical(session) -> list[dict]:
    rows = session.execute(text(
        "SELECT name, label, aliases FROM canonical_indicators"
    )).fetchall()
    out = []
    for name, label, aliases_json in rows:
        aliases = json.loads(aliases_json) if aliases_json else []
        out.append({
            "name": name,
            "label": label,
            "aliases": aliases,
            "norm_name": _norm(name),
            "norm_aliases": [_norm(a) for a in aliases],
        })
    return out


def _match(column: str, canonical: list[dict]) -> tuple[str | None, str | None, float]:
    """Return (indicator_name, method, confidence) or (None, None, 0.0)."""
    norm = _norm(column)
    if not norm:
        return None, None, 0.0

    # 1. exact
    for c in canonical:
        if norm == c["norm_name"]:
            return c["name"], "exact", 1.0
    # 2. alias
    for c in canonical:
        if norm in c["norm_aliases"]:
            return c["name"], "alias", 0.95
    # 3. fuzzy (best ratio across name + aliases)
    best_name, best_ratio = None, 0.0
    for c in canonical:
        candidates = [c["norm_name"]] + c["norm_aliases"]
        for cand in candidates:
            if not cand:
                continue
            r = SequenceMatcher(None, norm, cand).ratio()
            if r > best_ratio:
                best_ratio, best_name = r, c["name"]
    if best_ratio >= 0.85:
        return best_name, "fuzzy", round(best_ratio, 3)
    return None, None, 0.0


def run(source: str, dry_run: bool = False, confirm_all: bool = False) -> None:
    db = Database()
    session = db.get_session()
    try:
        canonical = _load_canonical(session)
        if not canonical:
            print("canonical_indicators is empty — run setup_indicator_vocabulary.py first.")
            sys.exit(1)

        cols = session.execute(text(
            "SELECT f.name AS fn, c.name AS col "
            "FROM daas_function_columns c "
            "JOIN daas_functions f ON f.id = c.function_id "
            "JOIN sources s ON s.id = f.source_id "
            "WHERE s.name = :src "
            "ORDER BY f.name, c.name"
        ), {"src": source}).fetchall()

        if not cols:
            print(f"No daas_function_columns rows found for source='{source}'. "
                  f"Register functions+columns for the source first (Step 3).")
            sys.exit(1)

        confirmed_count = proposed_count = 0
        proposals: list[tuple] = []
        unmatched: list[str] = []

        for fn, col in cols:
            indicator, method, conf = _match(col, canonical)
            if indicator is None:
                unmatched.append(f"{fn}.{col}")
                continue
            confirmed = method in ("exact", "alias") or confirm_all
            if confirmed:
                confirmed_count += 1
            else:
                proposed_count += 1
                proposals.append((fn, col, indicator, method, conf))

            session.execute(text(
                "INSERT INTO column_indicator_mappings "
                "(source, function_name, column_name, indicator_name, match_method, confidence, confirmed) "
                "VALUES (:src, :fn, :col, :ind, :m, :conf, :confd) "
                "ON CONFLICT(source, function_name, column_name) DO UPDATE SET "
                "  indicator_name=excluded.indicator_name, "
                "  match_method=excluded.match_method, "
                "  confidence=excluded.confidence, "
                "  confirmed=excluded.confirmed"
            ), {
                "src": source, "fn": fn, "col": col, "ind": indicator,
                "m": method, "conf": conf, "confd": 1 if confirmed else 0,
            })

        if dry_run:
            session.rollback()
            verb = "would"
        else:
            session.commit()
            verb = "did"

        print(f"\n{source}: {len(cols)} columns — {verb} map "
              f"{confirmed_count + proposed_count} "
              f"({confirmed_count} confirmed, {proposed_count} proposed), "
              f"{len(unmatched)} unmatched.")

        if proposals:
            print("\n── PROPOSALS (needs review) ──")
            for fn, col, ind, m, conf in proposals:
                print(f"  [{m} {conf:.2f}] {fn}.{col}  →  {ind}")
            print("Review with: sqlite3 mcp/daas.db "
                  f"\"SELECT * FROM column_indicator_mappings WHERE source='{source}' AND confirmed=0;\"")
            print("Confirm all with: --confirm-all. Confirm one: edit the row's confirmed=1.")

        if unmatched:
            print(f"\n── UNMATCHED ({len(unmatched)}) ──")
            for u in unmatched[:30]:
                print(f"  {u}")
            if len(unmatched) > 30:
                print(f"  ...and {len(unmatched) - 30} more.")
            print("To map one, add a canonical indicator (references/canonical-indicators.md) "
                  "or insert a manual mapping (match_method='manual').")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Auto-map a source's columns to canonical indicators.")
    p.add_argument("--source", required=True, help="sources.name to match columns for.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-all", action="store_true",
                   help="Mark every match (incl. fuzzy) confirmed=1. Use only after review.")
    args = p.parse_args()
    run(source=args.source, dry_run=args.dry_run, confirm_all=args.confirm_all)
