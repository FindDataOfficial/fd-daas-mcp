"""
Migration runner for importing the curated seed registry into the SQLAlchemy DB.

One-shot script: reads cli_anything.yfinance.core.seed.REGISTRY, upserts all
functions and their output columns, then verifies row counts match.

Mirrors the akshare harness migrate_registry.py, but sources from a Python
dict (seed.py) instead of a JSON file — yfinance's registry is hand-curated.

Usage:
    python -m cli_anything.yfinance.core.migrate_registry
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from sqlalchemy.orm import Session

from cli_anything.yfinance.core.models import Function, FunctionColumn
from cli_anything.yfinance.core.seed import REGISTRY

logger = logging.getLogger(__name__)


class MigrationRunner:
    """One-shot importer: reads seed.REGISTRY, upserts into the database.

    Idempotent — safe to run multiple times. Upserts by command name
    (unique). Deletes old columns before inserting new ones for each function.
    """

    def __init__(self, session: Session, registry: Optional[dict] = None):
        self._session = session
        self._registry = registry if registry is not None else REGISTRY

    def run(self) -> None:
        """Execute the full migration: upsert, verify."""
        print(f"Loaded {len(self._registry)} functions from seed registry")

        imported = 0
        skipped = 0
        total_columns = 0

        for command, info in self._registry.items():
            func = self._upsert_function(command, info)
            if func is None:
                skipped += 1
                continue
            col_count = self._upsert_columns(func, info.get("columns", []))
            total_columns += col_count
            imported += 1

        self._session.flush()
        print(f"Imported: {imported} functions, {total_columns} columns")
        if skipped:
            print(f"Skipped: {skipped} functions")

        ok = self._verify(expected_count=len(self._registry))
        if ok:
            print("Verification PASSED: row counts match")
        else:
            print("Verification FAILED: row counts do not match!")
            sys.exit(1)

    def _upsert_function(self, command: str, data: dict) -> Optional[Function]:
        """Insert or update a Function row by command name. Returns the Function."""
        if not command:
            return None

        func = (
            self._session.query(Function)
            .filter(Function.command == command)
            .first()
        )

        if func is None:
            func = Function(command=command)

        func.category = data.get("category", "未分类")
        func.source = data.get("source", "")
        func.description = data.get("description", "")
        func.parameters = data.get("parameters", [])

        self._session.add(func)
        self._session.flush()
        return func

    def _upsert_columns(self, func: Function, columns: list[dict]) -> int:
        """Replace all columns for a function. Returns count inserted."""
        (
            self._session.query(FunctionColumn)
            .filter(FunctionColumn.function_id == func.id)
            .delete()
        )

        count = 0
        for col_data in columns:
            col = FunctionColumn(
                function_id=func.id,
                column_name=col_data.get("name", ""),
                column_type=col_data.get("type", ""),
                column_description=col_data.get("description", ""),
            )
            self._session.add(col)
            count += 1

        return count

    def _verify(self, expected_count: int) -> bool:
        """Verify the database function count matches expected."""
        db_count = self._session.query(Function).count()
        db_col_count = self._session.query(FunctionColumn).count()
        print(f"Database: {db_count} functions, {db_col_count} columns")
        print(f"Expected: {expected_count} functions")
        return db_count == expected_count


# ============================================
# CLI entry point
# ============================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate seed registry to SQLAlchemy database"
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (default: from env or SQLite)",
    )
    args = parser.parse_args()

    from cli_anything.yfinance.core.database import get_database

    db = get_database(args.database_url)
    session = db.get_session()
    try:
        runner = MigrationRunner(session)
        runner.run()
        session.commit()
        print("Migration complete.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        db.dispose()
