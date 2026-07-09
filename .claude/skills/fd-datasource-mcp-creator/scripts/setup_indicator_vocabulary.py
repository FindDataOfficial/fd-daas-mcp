#!/usr/bin/env python3
"""
setup_indicator_vocabulary.py — create + seed the canonical indicator tables.

Idempotent. Parses references/canonical-indicators.md (the human-readable source
of truth) and upserts each row into `canonical_indicators`. Creates both
`canonical_indicators` and `column_indicator_mappings` via Base.metadata.create_all
(additive — no Alembic, mirrors every other daas table).

Run from within mcp/daas-mcp/ (so `import models` + `import daas_database` work):

    uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/scripts/setup_indicator_vocabulary.py
    uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/scripts/setup_indicator_vocabulary.py --dry-run
    uv run --directory mcp/daas-mcp python ../../.claude/skills/fd-datasource-mcp-creator/scripts/setup_indicator_vocabulary.py --unseed

The two ORM classes are declared inline on the shared `Base.metadata` so the
tables are created even before they're pasted into mcp/models/models.py. Once
pasted there (see references/daas-concepts.md §6), this script's inline copies
are redundant but harmless — `create_all` is idempotent. Keep the two in sync.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parent.parent.parent.parent.parent  # scripts/ → skill → .claude/skills/ → .claude → repo root
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

sys.path.insert(0, str(_REPO_ROOT / "mcp" / "daas-mcp"))

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint, select  # noqa: E402
from sqlalchemy.orm import declarative_base  # noqa: E402

from models import Base  # noqa: E402  — the shared Base; tables attach to its metadata
from daas_database import Database  # noqa: E402


# ════════════════════════════════════════════════════════════════════════
# Inline model declarations (mirror references/daas-concepts.md §6)
# ════════════════════════════════════════════════════════════════════════
class CanonicalIndicator(Base):
    __tablename__ = "canonical_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(128), nullable=False)
    description = Column(String, nullable=True)
    unit = Column(String(32), nullable=True)
    semantic_type = Column(String(32), nullable=True)
    category = Column(String(64), nullable=True)
    aliases = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ColumnIndicatorMapping(Base):
    __tablename__ = "column_indicator_mappings"
    __table_args__ = (
        UniqueConstraint("source", "function_name", "column_name",
                         name="uq_column_indicator_mapping"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False, index=True)
    function_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    indicator_name = Column(String(64), nullable=False, index=True)
    match_method = Column(String(16), nullable=True)
    confidence = Column(Float, nullable=True)
    confirmed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ════════════════════════════════════════════════════════════════════════
# Markdown table parser
# ════════════════════════════════════════════════════════════════════════
_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
_SEP_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


def _parse_seed(md_path: Path) -> list[dict]:
    rows: list[dict] = []
    in_table = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        if not _ROW_RE.match(line):
            in_table = False
            continue
        if _SEP_RE.match(line):
            continue
        cells = [c.strip() for c in _ROW_RE.match(line).group(1).split("|")]
        if len(cells) < 7:
            continue
        name = cells[0]
        # Skip the header row
        if name.lower() == "name" or not name:
            in_table = True
            continue
        aliases_raw = cells[5].strip()
        aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else []
        rows.append({
            "name": name,
            "label": cells[1],
            "unit": cells[2] or None,
            "semantic_type": cells[3] or None,
            "category": cells[4] or None,
            "aliases": aliases,
            "description": cells[6] or None,
        })
    return rows


# ════════════════════════════════════════════════════════════════════════
# Run
# ════════════════════════════════════════════════════════════════════════
def run(dry_run: bool = False, unseed: bool = False) -> None:
    db = Database()
    engine = db.engine
    md_path = _THIS.parent.parent / "references" / "canonical-indicators.md"

    if unseed:
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS column_indicator_mappings;")
            conn.exec_driver_sql("DROP TABLE IF EXISTS canonical_indicators;")
        print("Dropped canonical_indicators + column_indicator_mappings.")
        return

    Base.metadata.create_all(engine)  # idempotent — creates both tables
    seed = _parse_seed(md_path)
    if not seed:
        print(f"No rows parsed from {md_path} — check the table format.")
        sys.exit(1)

    session = db.get_session()
    try:
        inserted = updated = 0
        for row in seed:
            existing = session.execute(
                select(CanonicalIndicator).where(CanonicalIndicator.name == row["name"])
            ).scalar_one_or_none()
            if existing is None:
                session.add(CanonicalIndicator(**row))
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(existing, k, v)
                updated += 1
        if dry_run:
            session.rollback()
            print(f"DRY RUN — would upsert {len(seed)} indicators "
                  f"({inserted} new, {updated} updated). No changes committed.")
        else:
            session.commit()
            print(f"Seeded {len(seed)} canonical indicators: "
                  f"{inserted} new, {updated} updated.")
            # Sanity check
            n = session.execute(select(CanonicalIndicator)).scalars().all()
            print(f"canonical_indicators now holds {len(n)} rows.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Create + seed canonical indicator vocabulary.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--unseed", action="store_true", help="Drop both tables and exit.")
    args = p.parse_args()
    run(dry_run=args.dry_run, unseed=args.unseed)
