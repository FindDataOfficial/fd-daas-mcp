"""
Database tools for the Leader MCP — plain Python functions that query
the harness-based registry in daas.db (shared `mcp/models` schema).

Each function row is keyed by (harness, command) — e.g. harness='akshare',
command='stock_zh_a_hist'. `harness` is the source/harness name; `command`
is the function name. There is no separate `sources` table dependency here.

Designed to work as CrewAI tools (via @tool decorator) but also callable
directly without CrewAI for testing and scripting.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func, or_

from leader_database import get_leader_db, reset_leader_db
from models import Function, FunctionColumn, DataSnapshot


def _find_function(session, harness: str, command: str):
    """Look up a function by (harness, command)."""
    return (
        session.query(Function)
        .filter(Function.harness == harness, Function.command == command)
        .first()
    )


def list_harnesses() -> str:
    """List all harness names in the registry, with function counts."""
    db = get_leader_db()
    session = db.get_session()
    try:
        rows = (
            session.query(
                Function.harness.label("harness"),
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
    function command, category, and description. E.g., 'stock market' becomes
    'stock' OR 'market'.

    Args:
        query: Search term(s) — matches command, category, and description.
        harness: Optional harness name to limit scope (e.g. 'akshare', 'yfinance').
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        terms = [t.strip() for t in query.split() if t.strip()]
        if not terms:
            terms = [query]

        q_obj = session.query(Function)
        if harness:
            q_obj = q_obj.filter(Function.harness == harness)

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
        lines = [
            f"[{r.harness}] {r.command} | {r.category} | {r.description or ''}"
            for r in rows
        ]
        return "\n".join(lines)
    finally:
        session.close()


def get_function_detail(harness: str, command: str) -> str:
    """Get full details for a function, including parameters and output columns.

    Args:
        harness: Harness name (e.g. 'akshare', 'yfinance', 'ckan').
        command: Function name (e.g. 'stock_zh_a_hist').
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        f = _find_function(session, harness, command)
        if f is None:
            return f"Function '{command}' not found in harness '{harness}'."
        d = f.to_dict()
        params = d.get("parameters", [])
        cols = d.get("columns", [])
        lines = [
            f"Harness:     {d['harness']}",
            f"Command:     {d['command']}",
            f"Source URL:  {d.get('source') or 'N/A'}",
            f"Category:    {d['category']}",
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
    """List all categories with function counts, optionally filtered by harness.

    Args:
        harness: Optional harness name to filter by.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        q = session.query(
            Function.harness.label("harness"),
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
    """Find all functions that have a specific output column name.

    Args:
        column_name: Output column name to search for.
        harness: Optional harness name to filter by.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        q = (
            session.query(Function)
            .join(FunctionColumn, FunctionColumn.function_id == Function.id)
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

            f = (
                session.query(Function)
                .filter(Function.harness == harness, Function.command == command)
                .first()
            )
            if f is None:
                f = Function(harness=harness, command=command)

            f.category = info.get("category", "未分类")
            f.source = info.get("source", "")
            f.description = info.get("description", "")
            f.parameters = info.get("parameters", [])
            session.add(f)
            session.flush()

            (
                session.query(FunctionColumn)
                .filter(FunctionColumn.function_id == f.id)
                .delete()
            )
            for col_data in info.get("columns", []):
                col = FunctionColumn(
                    function_id=f.id,
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
# Datasource management tools
# ============================================


def list_datasources(harness: Optional[str] = None) -> str:
    """List all functions marked as datasources, grouped by harness.

    Args:
        harness: Optional harness name to filter by.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        q = session.query(Function).filter(Function.is_datasource == True)  # noqa: E712
        if harness:
            q = q.filter(Function.harness == harness)
        rows = q.order_by(Function.harness, Function.command).all()

        if not rows:
            scope = f"in '{harness}'" if harness else "across all harnesses"
            return f"No datasources configured {scope}. Use toggle_datasource to mark functions as datasources."

        lines = []
        current_harness = None
        for r in rows:
            if r.harness != current_harness:
                current_harness = r.harness
                lines.append(f"\n[{current_harness}]")
            enabled_str = "✓" if r.enabled else "✗"
            fetched = r.last_fetched_at.strftime("%Y-%m-%d %H:%M") if r.last_fetched_at else "never"
            lines.append(f"  [{enabled_str}] {r.command} | {r.category} | last: {fetched}")
        return "\n".join(lines)
    finally:
        session.close()


def toggle_datasource(
    harness: str,
    command: str,
    enabled: Optional[bool] = None,
    is_datasource: Optional[bool] = None,
) -> str:
    """Mark/unmark a function as a datasource and toggle its enabled state.

    Args:
        harness: Harness name (e.g., 'akshare').
        command: Function name.
        enabled: Set the enabled state (True/False). Omit to leave unchanged.
        is_datasource: Set is_datasource flag (True/False). Omit to leave unchanged.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        f = _find_function(session, harness, command)
        if f is None:
            return f"Function '{command}' not found in harness '{harness}'."

        changes = []
        if is_datasource is not None:
            f.is_datasource = is_datasource
            changes.append(f"is_datasource={is_datasource}")
        if enabled is not None:
            f.enabled = enabled
            changes.append(f"enabled={enabled}")

        if not changes:
            return f"No changes requested for '{command}'."

        session.commit()
        return (
            f"Updated '{harness}/{command}': {', '.join(changes)}. "
            f"Current state: is_datasource={f.is_datasource}, enabled={f.enabled}"
        )
    except Exception as e:
        session.rollback()
        return f"Error toggling datasource: {e}"
    finally:
        session.close()


def save_snapshot(harness: str, command: str, params: str = "{}") -> str:
    """Save structured row data from a function call as a snapshot.

    Calls the function with given params, parses the result into JSON rows,
    and upserts into data_snapshots. Updates last_fetched_at on the function.
    Caps at 10000 rows.

    Only the 'akshare' harness supports live function calls here.

    Args:
        harness: Harness name (e.g., 'akshare').
        command: Function name.
        params: JSON string of parameters (e.g., '{"symbol":"000001"}').
    """
    import importlib

    MAX_ROWS = 10000

    db = get_leader_db()
    session = db.get_session()
    try:
        f = _find_function(session, harness, command)
        if f is None:
            return f"Function '{command}' not found in harness '{harness}'."

        params_dict = json.loads(params) if isinstance(params, str) else params

        data_json = None
        row_count = 0
        status = "error"
        error_msg = None

        try:
            if harness == "akshare":
                mod = importlib.import_module("akshare")
                fn = getattr(mod, command, None)
                if fn is None:
                    return f"Function '{command}' not found in akshare module."
                result = fn(**params_dict)
            else:
                return (
                    f"Harness '{harness}' does not support live function calls yet. "
                    f"Only 'akshare' is supported for save_snapshot."
                )

            if hasattr(result, "to_dict"):
                data = result.to_dict(orient="records")
            elif hasattr(result, "to_json"):
                data = json.loads(result.to_json(orient="records"))
            elif isinstance(result, list):
                data = result
            else:
                return f"Unsupported result type: {type(result).__name__}"

            # Normalize non-JSON-native types (datetime.date, Decimal, numpy
            # scalars) so the JSON column serialization below doesn't fail.
            data = json.loads(json.dumps(data, default=str))

            if len(data) > MAX_ROWS:
                return (
                    f"Result has {len(data)} rows, exceeds max {MAX_ROWS}. "
                    f"Add filters to reduce row count."
                )

            data_json = data
            row_count = len(data)
            status = "success"
        except Exception as e:
            error_msg = str(e)
            data_json = [{"error": error_msg}]
            status = "error"

        snap = (
            session.query(DataSnapshot)
            .filter(
                DataSnapshot.function_id == f.id,
                DataSnapshot.params_json == params_dict,
            )
            .first()
        )
        if snap is None:
            snap = DataSnapshot(function_id=f.id, params_json=params_dict)
            session.add(snap)

        snap.data_json = data_json
        snap.row_count = row_count
        snap.status = status
        snap.fetched_at = datetime.now(timezone.utc)

        f.last_fetched_at = snap.fetched_at

        session.commit()
        return (
            f"Snapshot saved for '{harness}/{command}': "
            f"{row_count} rows, status={status}"
            + (f", error: {error_msg}" if error_msg else "")
        )
    except Exception as e:
        session.rollback()
        return f"Error saving snapshot: {e}"
    finally:
        session.close()


def list_snapshots(
    harness: Optional[str] = None, command: Optional[str] = None
) -> str:
    """List all stored data snapshots with metadata.

    Args:
        harness: Optional harness name filter.
        command: Optional function name filter (requires harness).
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        q = (
            session.query(DataSnapshot, Function)
            .join(Function, DataSnapshot.function_id == Function.id)
        )
        if harness:
            q = q.filter(Function.harness == harness)
        if command:
            q = q.filter(Function.command == command)
        rows = q.order_by(DataSnapshot.fetched_at.desc()).limit(100).all()

        if not rows:
            return "No snapshots found."

        lines = []
        for snap, f in rows:
            fetched = snap.fetched_at.strftime("%Y-%m-%d %H:%M") if snap.fetched_at else "?"
            lines.append(
                f"[{snap.id}] {f.harness}/{f.command} | "
                f"{snap.row_count} rows | {snap.status} | {fetched}"
            )
        return "\n".join(lines)
    finally:
        session.close()


def query_snapshots(
    snapshot_id: int, limit: int = 50, offset: int = 0
) -> str:
    """Return paginated data rows for a specific snapshot.

    Args:
        snapshot_id: ID of the snapshot to query.
        limit: Max rows to return (default 50).
        offset: Row offset for pagination (default 0).
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        snap = session.query(DataSnapshot).filter(DataSnapshot.id == snapshot_id).first()
        if snap is None:
            return f"Snapshot {snapshot_id} not found."

        if snap.data_json is None:
            return f"Snapshot {snapshot_id} has no data (status: {snap.status})."

        rows = snap.data_json
        total = len(rows)
        page = rows[offset : offset + limit]

        lines = [
            f"Snapshot {snapshot_id} | {snap.status} | {total} rows total",
            f"Showing rows {offset + 1}-{min(offset + limit, total)}:",
            "",
        ]
        if page:
            headers = list(page[0].keys()) if page else []
            lines.append(" | ".join(headers))
            lines.append("-" * 80)
            for row in page:
                vals = [str(row.get(h, "")) for h in headers]
                lines.append(" | ".join(vals))
        else:
            lines.append("(no rows)")

        return "\n".join(lines)
    finally:
        session.close()


# ============================================
# Column provenance tools
# ============================================


def get_column_provenance(harness: str, command: str) -> str:
    """Get all columns for a function with provenance fields.

    Args:
        harness: Harness name (e.g., 'akshare').
        command: Function name.
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        f = _find_function(session, harness, command)
        if f is None:
            return f"Function '{command}' not found in harness '{harness}'."

        cols = (
            session.query(FunctionColumn)
            .filter(FunctionColumn.function_id == f.id)
            .order_by(FunctionColumn.id)
            .all()
        )
        if not cols:
            return f"No columns defined for '{harness}/{command}'."

        lines = [
            f"Columns for {harness}/{command}:",
            f"{'Name':<20} {'Type':<12} {'Source Field':<20} {'Unit':<10} {'Semantic':<12} Description",
            "-" * 100,
        ]
        for c in cols:
            lines.append(
                f"{(c.column_name or ''):<20} "
                f"{(c.column_type or ''):<12} "
                f"{(c.source_field or ''):<20} "
                f"{(c.unit or ''):<10} "
                f"{(c.semantic_type or ''):<12} "
                f"{c.column_description or ''}"
            )
        return "\n".join(lines)
    finally:
        session.close()


def update_column_meta(
    harness: str,
    command: str,
    column_name: str,
    source_field: Optional[str] = None,
    unit: Optional[str] = None,
    semantic_type: Optional[str] = None,
) -> str:
    """Update provenance metadata for a specific column.

    Only provided fields are updated; omitted fields are left unchanged.

    Args:
        harness: Harness name (e.g., 'akshare').
        command: Function name.
        column_name: Name of the column to update.
        source_field: API field name this column maps to.
        unit: Unit of measurement (CNY, %, shares, etc.).
        semantic_type: Semantic role (price, volume, date, name, code, etc.).
    """
    db = get_leader_db()
    session = db.get_session()
    try:
        f = _find_function(session, harness, command)
        if f is None:
            return f"Function '{command}' not found in harness '{harness}'."

        col = (
            session.query(FunctionColumn)
            .filter(
                FunctionColumn.function_id == f.id,
                FunctionColumn.column_name == column_name,
            )
            .first()
        )
        if col is None:
            return f"Column '{column_name}' not found for '{harness}/{command}'."

        changes = []
        if source_field is not None:
            col.source_field = source_field if source_field else None
            changes.append(f"source_field={source_field}")
        if unit is not None:
            col.unit = unit if unit else None
            changes.append(f"unit={unit}")
        if semantic_type is not None:
            col.semantic_type = semantic_type if semantic_type else None
            changes.append(f"semantic_type={semantic_type}")

        if not changes:
            return f"No changes requested for column '{column_name}'."

        session.commit()
        return f"Updated column '{column_name}' in '{harness}/{command}': {', '.join(changes)}"
    except Exception as e:
        session.rollback()
        return f"Error updating column meta: {e}"
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
