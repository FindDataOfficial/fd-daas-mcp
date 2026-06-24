"""Output formatting utilities for DAAS CLI."""
from __future__ import annotations

import json
import sys


def format_output(result, json_mode: bool = False):
    """Format a result (DataFrame, dict, list) for CLI output.

    json_mode: output as JSON string
    Default: pretty-print DataFrame as table, dicts/lists as formatted text
    """
    try:
        import pandas as pd
    except ImportError:
        # No pandas — just print as JSON or repr
        if json_mode:
            print(json.dumps(_to_serializable(result), ensure_ascii=False, indent=2))
        else:
            print(result)
        return

    if isinstance(result, pd.DataFrame):
        if json_mode:
            clean = result.where(result.notna(), None)
            data = clean.to_dict(orient="records")
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            # Pretty table via pandas
            with pd.option_context(
                "display.max_rows", 50,
                "display.max_columns", 20,
                "display.width", 160,
            ):
                print(result.to_string())
    elif isinstance(result, pd.Series):
        if json_mode:
            clean = result.where(result.notna(), None)
            print(json.dumps(clean.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            print(result.to_string())
    elif isinstance(result, (dict, list)):
        if json_mode:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            _pretty_print_dict(result)
    else:
        if json_mode:
            print(json.dumps({"result": str(result)}, ensure_ascii=False))
        else:
            print(result)


def _pretty_print_dict(obj, indent: int = 0):
    """Pretty-print a dict or list to the terminal."""
    prefix = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                print(f"{prefix}{k}:")
                _pretty_print_dict(v, indent + 1)
            else:
                print(f"{prefix}{k}: {v}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                _pretty_print_dict(item, indent)
                print()
            else:
                print(f"{prefix}- {item}")


def _to_serializable(obj):
    """Recursively convert objects to JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    elif hasattr(obj, "dtype"):
        return str(obj)
    return obj
