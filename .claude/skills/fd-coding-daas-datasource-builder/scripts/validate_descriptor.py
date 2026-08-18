#!/usr/bin/env python3
"""Validate a daas.descriptor.json against the mirrored daas.db schema.

This is the gate before gen_cli.py and import_descriptor.py. Exits non-zero with
a list of errors on failure; prints OK + function count on success.

Usage:
    python validate_descriptor.py <descriptor.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_SOURCE = {"name", "label"}
REQUIRED_FUNC = {"name", "category"}
REQUIRED_PARAM = {"name", "required"}
REQUIRED_COLUMN = {"name"}
REQUIRED_INDICATOR = {"name", "indicator_name", "op", "value_column", "date_column"}
REQUIRED_ENTITY = {"entity_type"}

VALID_FREQ = {
    "realtime", "intraday", "daily", "weekly", "monthly", "quarterly",
    "annual", "irregular", "",
}
VALID_OPS = {
    "sma", "ema", "rsi", "pct_change", "log_return", "diff", "rolling_std",
    "rolling_min", "rolling_max", "zscore", "ratio", "level",
}
VALID_DEDUP = {"exists", "new", "new_concept"}
VALID_MATCH = {"candidate_new_metric", "not_a_metric", "existing_metric", ""}


def _err(errs: list[str], msg: str) -> None:
    errs.append(msg)


def validate(desc: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(desc, dict):
        return ["top-level: descriptor is not a JSON object"]

    src = desc.get("source")
    if not isinstance(src, dict):
        _err(errs, "source: missing or not an object")
    else:
        for k in REQUIRED_SOURCE:
            if not src.get(k):
                _err(errs, f"source.{k}: missing or empty")
        c = src.get("score")
        if c is not None and not (0.0 <= float(c) <= 1.0):
            _err(errs, f"source.score: out of range [0,1]: {c}")

    funcs = desc.get("daas_functions")
    if not isinstance(funcs, list):
        _err(errs, "daas_functions: missing or not a list")
        return errs

    seen_funcs: set[str] = set()
    for i, f in enumerate(funcs):
        ctx = f"daas_functions[{i}] ({f.get('name', '?')})"
        for k in REQUIRED_FUNC:
            if not f.get(k):
                _err(errs, f"{ctx}.{k}: missing or empty")
        if f.get("name") in seen_funcs:
            _err(errs, f"{ctx}.name: duplicate function name '{f.get('name')}'")
        seen_funcs.add(f.get("name"))

        if f.get("frequency", "") not in VALID_FREQ:
            _err(errs, f"{ctx}.frequency: invalid '{f.get('frequency')}' "
                  f"(must be one of {sorted(VALID_FREQ - {''})})")

        c = f.get("confidence")
        if c is not None and not (0.0 <= float(c) <= 1.0):
            _err(errs, f"{ctx}.confidence: out of range [0,1]: {c}")
        if c is not None and not f.get("confidence_reasoning"):
            _err(errs, f"{ctx}.confidence_reasoning: required when confidence is set")

        for j, p in enumerate(f.get("parameters", [])):
            pctx = f"{ctx}.parameters[{j}]"
            for k in REQUIRED_PARAM:
                if k not in p:
                    _err(errs, f"{pctx}.{k}: missing")

        for j, col in enumerate(f.get("columns", [])):
            cctx = f"{ctx}.columns[{j}]"
            for k in REQUIRED_COLUMN:
                if not col.get(k):
                    _err(errs, f"{cctx}.{k}: missing or empty")
            m = col.get("indicator_match", "")
            if m and m not in VALID_MATCH:
                _err(errs, f"{cctx}.indicator_match: invalid '{m}'")
            for k, ind in enumerate(col.get("proposed_indicator_rules", [])):
                ictx = f"{cctx}.proposed_indicator_rules[{k}]"
                for rk in REQUIRED_INDICATOR:
                    if not ind.get(rk):
                        _err(errs, f"{ictx}.{rk}: missing or empty")
                if ind.get("op") not in VALID_OPS:
                    _err(errs, f"{ictx}.op: invalid '{ind.get('op')}'")
                ds = ind.get("dedup_status", "")
                if ds and ds not in VALID_DEDUP:
                    _err(errs, f"{ictx}.dedup_status: invalid '{ds}'")

        for j, e in enumerate(f.get("entities", [])):
            ectx = f"{ctx}.entities[{j}]"
            for k in REQUIRED_ENTITY:
                if not e.get(k):
                    _err(errs, f"{ectx}.{k}: missing or empty")

    return errs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("descriptor")
    args = ap.parse_args()
    try:
        desc = json.loads(Path(args.descriptor).read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"descriptor not found: {args.descriptor}")
    except json.JSONDecodeError as e:
        sys.exit(f"descriptor is not valid JSON: {e}")

    errs = validate(desc)
    if errs:
        for e in errs:
            print("ERROR:", e, file=sys.stderr)
        sys.exit(f"\n{len(errs)} error(s); descriptor is NOT import-ready.")
    n = len(desc.get("daas_functions", []))
    nind = sum(len(c.get("proposed_indicator_rules", []))
               for f in desc.get("daas_functions", []) for c in f.get("columns", []))
    print(f"OK: {n} function(s), {nind} proposed indicator rule(s). Descriptor is import-ready.")


if __name__ == "__main__":
    main()
