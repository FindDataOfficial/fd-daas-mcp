#!/usr/bin/env python3
"""run_indicator.py - compute deterministic math indicators over a daas.db
source table and upsert the series into the `observations` table.

Standalone port of `fd-daas-mcp/daas-mcp/indicator_tools.py` +
`process_database.py`'s `run_indicator` path. No MCP, no SQLAlchemy - stdlib
sqlite3 + pandas. Backs up daas.db before writing.

Usage:
  uv run python scripts/run_indicator.py <rule_name>
  uv run python scripts/run_indicator.py --calc <source_table> <date_column> <value_column> <op> [key=value ...]
  uv run python scripts/run_indicator.py --list-ops
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect, backup  # noqa: E402

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class IndicatorError(Exception):
    """Validation error surfaced as a JSON result, not a crash."""


# ── op catalog (ported verbatim from indicator_tools.py) ──────────
def _pct_change(df, vc, p):
    return df[vc].pct_change()


def _log_return(df, vc, p):
    prev = df[vc].shift(1)
    return np.log(df[vc] / prev)


def _diff(df, vc, p):
    return df[vc].diff()


def _sma(df, vc, p):
    return df[vc].rolling(int(p["window"])).mean()


def _ema(df, vc, p):
    return df[vc].ewm(span=int(p["span"]), adjust=False).mean()


def _rolling_std(df, vc, p):
    return df[vc].rolling(int(p["window"])).std()


def _rolling_min(df, vc, p):
    return df[vc].rolling(int(p["window"])).min()


def _rolling_max(df, vc, p):
    return df[vc].rolling(int(p["window"])).max()


def _rsi(df, vc, p):
    window = int(p["window"])
    delta = df[vc].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _zscore(df, vc, p):
    window = int(p["window"])
    mean = df[vc].rolling(window).mean()
    std = df[vc].rolling(window).std()
    return (df[vc] - mean) / std


def _ratio(df, vc, p):
    other = p["other_column"]
    if other not in df.columns:
        raise IndicatorError(f"other_column not found in source table: {other}")
    return df[vc] / df[other]


def _level(df, vc, p):
    return df[vc].astype(float)


_OPS = {
    "pct_change": {"fn": _pct_change, "required_params": []},
    "log_return": {"fn": _log_return, "required_params": []},
    "diff": {"fn": _diff, "required_params": []},
    "sma": {"fn": _sma, "required_params": ["window"]},
    "ema": {"fn": _ema, "required_params": ["span"]},
    "rolling_std": {"fn": _rolling_std, "required_params": ["window"]},
    "rolling_min": {"fn": _rolling_min, "required_params": ["window"]},
    "rolling_max": {"fn": _rolling_max, "required_params": ["window"]},
    "rsi": {"fn": _rsi, "required_params": ["window"]},
    "zscore": {"fn": _zscore, "required_params": ["window"]},
    "ratio": {"fn": _ratio, "required_params": ["other_column"]},
    "level": {"fn": _level, "required_params": []},
}


def list_ops() -> dict:
    return {
        "ops": [
            {"name": n, "required_params": s["required_params"]} for n, s in _OPS.items()
        ]
    }


def validate_op(op: str, params) -> None:
    spec = _OPS.get(op)
    if spec is None:
        raise IndicatorError(f"unknown op: {op}")
    params = params or {}
    for p in spec["required_params"]:
        if p not in params:
            raise IndicatorError(f"op '{op}' requires param '{p}'")


def validate_identifier(name: str) -> None:
    if not name or not _IDENT_RE.match(name):
        raise IndicatorError(f"invalid identifier: {name!r}")


def table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def column_exists(conn, table: str, column: str) -> bool:
    validate_identifier(table)
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def compute_series(df: pd.DataFrame, value_column: str, op: str, params) -> pd.Series:
    validate_op(op, params)
    if value_column not in df.columns:
        raise IndicatorError(f"value_column not found in source table: {value_column}")
    series = pd.to_numeric(df[value_column], errors="coerce")
    work = df.copy()
    work[value_column] = series
    return _OPS[op]["fn"](work, value_column, params or {})


def fetch_series(conn, source_table, date_column, value_column):
    for x in (source_table, date_column, value_column):
        validate_identifier(x)
    if not table_exists(conn, source_table):
        raise IndicatorError(f"source table not found: {source_table}")
    if not column_exists(conn, source_table, date_column):
        raise IndicatorError(f"date_column not found: {source_table}.{date_column}")
    if not column_exists(conn, source_table, value_column):
        raise IndicatorError(f"value_column not found: {source_table}.{value_column}")
    rows = conn.execute(
        f'SELECT "{date_column}", "{value_column}" FROM "{source_table}" '
        f'ORDER BY "{date_column}"'
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def upsert_observations(conn, source, function_name, indicator, rows, metadata) -> int:
    if not rows:
        return 0
    meta_json = json.dumps(metadata, ensure_ascii=False)
    sql = (
        "INSERT INTO observations "
        "(source, function_name, indicator, date, value, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(source, function_name, indicator, date) DO UPDATE SET "
        "value=excluded.value, metadata=excluded.metadata"
    )
    records = [
        (source, function_name, indicator, str(d), str(v), meta_json) for d, v in rows
    ]
    conn.executemany(sql, records)
    return len(records)


def run_indicator(name: str) -> dict:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM indicator_rules WHERE name=?", (name,)
        ).fetchone()
        if row is None:
            return {"error": f"indicator not found: {name}"}
        if not row["enabled"]:
            return {"error": f"indicator disabled: {name}"}
        params = json.loads(row["params_json"]) if row["params_json"] else None
        try:
            rows = fetch_series(
                conn, row["source_table"], row["date_column"], row["value_column"]
            )
        except IndicatorError as e:
            return {"error": str(e)}
        if not rows:
            return {"rule": name, "rows_written": 0, "up_to_date": True}

        df = pd.DataFrame(rows, columns=[row["date_column"], row["value_column"]])
        try:
            computed = compute_series(df, row["value_column"], row["op"], params)
        except IndicatorError as e:
            return {"error": str(e)}

        metadata = {
            "rule_name": row["name"],
            "op": row["op"],
            "params": params or {},
            "value_column": row["value_column"],
        }
        out: list[tuple] = []
        for d, v in zip(df[row["date_column"]].tolist(), computed.tolist()):
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if np.isnan(fv):
                continue
            out.append((d, fv))

        bak = backup()
        written = upsert_observations(
            conn,
            row["datasource"],
            row["function_name"],
            row["indicator_name"],
            out,
            metadata,
        )
        conn.commit()
        return {
            "rule": name,
            "rows_written": written,
            "up_to_date": True,
            "backup": str(bak),
        }
    finally:
        conn.close()


def calc(args: list[str]) -> dict:
    if len(args) < 4:
        return {
            "error": "--calc requires: <source_table> <date_column> <value_column> <op> [key=value ...]"
        }
    source_table, date_column, value_column, op = args[:4]
    params: dict = {}
    for kv in args[4:]:
        if "=" not in kv:
            return {"error": f"bad param {kv!r}, expected key=value"}
        k, _, v = kv.partition("=")
        try:
            v = json.loads(v)
        except Exception:
            pass
        params[k] = v
    conn = connect()
    try:
        try:
            rows = fetch_series(conn, source_table, date_column, value_column)
        except IndicatorError as e:
            return {"error": str(e)}
        if not rows:
            return {"indicator": op, "dates": [], "values": [], "count": 0}
        df = pd.DataFrame(rows, columns=[date_column, value_column])
        try:
            computed = compute_series(df, value_column, op, params)
        except IndicatorError as e:
            return {"error": str(e)}
        dates = df[date_column].tolist()
        values = [
            None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)
            for v in computed.tolist()
        ]
        return {"indicator": op, "dates": dates, "values": values, "count": len(dates)}
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    if not argv:
        print(json.dumps({"error": "usage: <rule_name> | --calc ... | --list-ops"}))
        return 2
    if argv[0] == "--list-ops":
        print(json.dumps(list_ops(), ensure_ascii=False, indent=2))
        return 0
    if argv[0] == "--calc":
        print(json.dumps(calc(argv[1:]), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(run_indicator(argv[0]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
