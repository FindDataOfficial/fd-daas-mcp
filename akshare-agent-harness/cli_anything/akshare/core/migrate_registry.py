"""
Migration runner for importing registry.json into the SQLAlchemy database.

One-shot script: reads the existing registry.json, upserts all functions
and their output columns, then verifies row counts match.

Usage:
    python -m cli_anything.akshare.core.migrate_registry [registry.json path]
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from cli_anything.akshare.core.models import Function, FunctionColumn

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parent.parent / "metadata"
_DEFAULT_REGISTRY_PATH = _DEFAULT_REGISTRY_DIR / "registry.json"


class MigrationRunner:
    """One-shot importer: reads registry.json, upserts into the database.

    Idempotent — safe to run multiple times. Upserts by command name
    (unique). Deletes old columns before inserting new ones for each function.
    """

    def __init__(self, session: Session, registry_path: Optional[str] = None):
        self._session = session
        self._registry_path = registry_path or str(_DEFAULT_REGISTRY_PATH)

    def run(self) -> None:
        """Execute the full migration: parse, upsert, verify."""
        print(f"Reading registry from: {self._registry_path}")
        data = self._parse_registry()
        print(f"Parsed {len(data)} functions from registry.json")

        imported = 0
        skipped = 0
        total_columns = 0

        for command, info in data.items():
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

        ok = self._verify(expected_count=len(data))
        if ok:
            print("Verification PASSED: row counts match")
        else:
            print("Verification FAILED: row counts do not match!")
            sys.exit(1)

    def _parse_registry(self) -> dict[str, dict]:
        """Load and parse the registry.json file."""
        with open(self._registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

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
        description="Migrate registry.json to SQLAlchemy database"
    )
    parser.add_argument(
        "registry_path",
        nargs="?",
        default=str(_DEFAULT_REGISTRY_PATH),
        help="Path to registry.json (default: metadata/registry.json)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (default: from env or SQLite)",
    )
    args = parser.parse_args()

    from cli_anything.akshare.core.database import get_database

    db = get_database(args.database_url)
    session = db.get_session()
    try:
        runner = MigrationRunner(session, args.registry_path)
        runner.run()
        session.commit()
        print("Migration complete.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        db.dispose()
