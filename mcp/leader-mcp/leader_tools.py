"""
Database tools for the Leader MCP — plain Python functions that query
the unified multi-harness database.

These are designed to work as CrewAI tools (via @tool decorator) but are
also callable directly without CrewAI for testing and scripting.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import func, or_

from leader_database import get_leader_db, reset_leader_db
from unified_models import Function, FunctionColumn


def list_harnesses() -> str:
    """List all harness names in the unified database, with function counts."""
    db = get_leader_db()
    session = db.get_session()
    try:
        rows = (
            session.query(
                Function.harness,
                func.count(Function.id).label("cnt"),
            )
            .group_by(Function.harness)
            .order_by(Function.harness)
            .all()
        )
        if not rows:
            return "No harnesses found in the database."
        lines = [f"{row.harness}: {row.cnt} functions" for row in rows]
        return "\n".join(lines)
    finally:
        session.close()


def search_functions(query: str, harness: Optional[str] = None) -> str:
    """Search functions across all harnesses (or filter by harness).

    Multi-word queries are split and each term is OR-matched against
    command, category, and description. E.g., 'stock market' becomes
    'stock' OR 'market'.

    Args:
        query: Search term(s) — matches command, category, and description.
        harness: Optional harness name to limit scope.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        # Split multi-word queries into OR-ed LIKE clauses for each term
        terms = [t.strip() for t in query.split() if t.strip()]
        if not terms:
            terms = [query]

        q_obj = session.query(Function)
        if harness:
            q_obj = q_obj.filter(Function.harness == harness)

        # Build OR across terms and fields
        conditions = []
        for term in terms:
            pattern = f"%{term}%"
            conditions.append(Function.command.like(pattern))
            conditions.append(Function.category.like(pattern))
            conditions.append(Function.description.like(pattern))

        rows = (
            q_obj.filter(or_(*conditions))
            .order_by(Function.harness, Function.command)
            .limit(50)
            .all()
        )
        if not rows:
            scope = f"in '{harness}'" if harness else "across all harnesses"
            return f"No functions found matching '{query}' {scope}."
        lines = [f"[{r.harness}] {r.command} | {r.category} | {r.description or ''}" for r in rows]
        return "\n".join(lines)
    finally:
        session.close()


def get_function_detail(harness: str, command: str) -> str:
    """Get full details for a function, including parameters and output columns."""
    db = get_leader_db()
    session = db.get_session()
    try:
        func = (
            session.query(Function)
            .filter(Function.harness == harness, Function.command == command)
            .first()
        )
        if func is None:
            return f"Function '{command}' not found in harness '{harness}'."
        d = func.to_dict()
        params = d.get("parameters", [])
        cols = d.get("columns", [])
        lines = [
            f"Harness:     {d['harness']}",
            f"Command:     {d['command']}",
            f"Category:    {d['category']}",
            f"Source:      {d.get('source', 'N/A')}",
            f"Description: {d['description'] or 'N/A'}",
            f"Parameters ({len(params)}):",
        ]
        for p in params[:10]:
            req = "required" if p.get("required") else "optional"
            lines.append(f"  --{p['name']} ({p.get('type', 'str')}, {req})")
        lines.append(f"Output Columns ({len(cols)}):")
        for c in cols[:15]:
            lines.append(f"  {c['name']} ({c.get('type', 'N/A')})")
        if len(cols) > 15:
            lines.append(f"  ... and {len(cols) - 15} more columns")
        return "\n".join(lines)
    finally:
        session.close()


def list_categories(harness: Optional[str] = None) -> str:
    """List all categories with function counts, optionally filtered by harness."""
    db = get_leader_db()
    session = db.get_session()
    try:
        q = session.query(
            Function.harness,
            Function.category,
            func.count(Function.id).label("cnt"),
        )
        if harness:
            q = q.filter(Function.harness == harness)
        rows = (
            q.group_by(Function.harness, Function.category)
            .order_by(Function.harness, func.count(Function.id).desc())
            .all()
        )
        if not rows:
            scope = f"in '{harness}'" if harness else "in any harness"
            return f"No categories found {scope}."
        lines = []
        current_harness = None
        for row in rows:
            if row.harness != current_harness:
                current_harness = row.harness
                lines.append(f"\n[{current_harness}]")
            lines.append(f"  {row.cnt:4d}  {row.category}")
        return "\n".join(lines)
    finally:
        session.close()


def find_functions_by_column(column_name: str, harness: Optional[str] = None) -> str:
    """Find all functions that have a specific output column name."""
    db = get_leader_db()
    session = db.get_session()
    try:
        q = (
            session.query(Function)
            .join(FunctionColumn)
            .filter(FunctionColumn.column_name == column_name)
        )
        if harness:
            q = q.filter(Function.harness == harness)
        rows = q.order_by(Function.harness, Function.command).limit(30).all()
        if not rows:
            scope = f"in '{harness}'" if harness else "across all harnesses"
            return f"No functions found with column '{column_name}' {scope}."
        lines = [f"[{r.harness}] {r.command} → {r.category}" for r in rows]
        return "\n".join(lines)
    finally:
        session.close()


def import_harness_registry(harness: str, registry_json_path: str) -> str:
    """Import a harness's registry.json into the unified database.

    Idempotent — safe to run multiple times. Upserts by (harness, command).

    Args:
        harness: Harness name (e.g., 'akshare').
        registry_json_path: Absolute path to registry.json.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        path = Path(registry_json_path)
        if not path.exists():
            return f"Error: file not found: {registry_json_path}"

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        imported = 0
        skipped = 0
        total_columns = 0

        for command, info in data.items():
            if not command:
                skipped += 1
                continue

            func = (
                session.query(Function)
                .filter(Function.harness == harness, Function.command == command)
                .first()
            )
            if func is None:
                func = Function(harness=harness, command=command)

            func.category = info.get("category", "未分类")
            func.source = info.get("source", "")
            func.description = info.get("description", "")
            func.parameters = info.get("parameters", [])
            session.add(func)
            session.flush()

            # Replace columns
            (
                session.query(FunctionColumn)
                .filter(FunctionColumn.function_id == func.id)
                .delete()
            )
            for col_data in info.get("columns", []):
                col = FunctionColumn(
                    function_id=func.id,
                    column_name=col_data.get("name", ""),
                    column_type=col_data.get("type", ""),
                    column_description=col_data.get("description", ""),
                )
                session.add(col)
                total_columns += 1
            imported += 1

        session.commit()
        return (
            f"Imported harness '{harness}': {imported} functions, "
            f"{total_columns} columns" + (f", {skipped} skipped" if skipped else "")
        )
    except Exception as e:
        session.rollback()
        return f"Error importing harness '{harness}': {e}"
    finally:
        session.close()


# ============================================
# CrewAI tool wrappers (only if crewai is available)
# ============================================

def _get_crewai_tools():
    """Return CrewAI @tool-decorated versions of these functions.
    Call this only when you need CrewAI integration — it imports crewai lazily.
    """
    try:
        from crewai.tools import tool as crewai_tool
    except ImportError:
        raise ImportError(
            "crewai is required for agent tools. Install: pip install crewai"
        )

    return [
        crewai_tool("list_harnesses")(list_harnesses),
        crewai_tool("search_functions")(search_functions),
        crewai_tool("get_function_detail")(get_function_detail),
        crewai_tool("list_categories")(list_categories),
        crewai_tool("find_functions_by_column")(find_functions_by_column),
        crewai_tool("import_harness_registry")(import_harness_registry),
    ]
