#!/usr/bin/env python3
"""AST-analyze a Python project for data-fetching functions.

Discovers functions that look like data fetchers and flags which already have a
CLI (Click/typer/argparse decorator detected on the def). Output: JSON on stdout.

Each candidate carries: function, module, qualname, params (name+annotation+
default+required), return_type, docstring, signals, signal_score,
has_existing_cli, file, lineno. Drop candidates with signal_score < min-score.

Usage:
    python analyze_project.py <project-root> [--package <pkg>] [--min-score 0.3]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

NETWORK_MODULES = {"requests", "httpx", "urllib", "urllib3", "aiohttp"}
# name prefixes / substrings that signal a data fetcher
FETCH_NAME_HINTS = (
    "get_", "fetch_", "list_", "query_", "download_", "load_", "fetch", "get",
    "historical_", "realtime_", "real_time_", "snapshot_", "history_", "quote_",
    "kline", "bar_", "price_", "news_", "macro_", "stock_", "fund_", "bond_",
    "hist_", "series_", "data_",
)
# return-type annotations that look like data containers
DATA_RETURN_HINTS = (
    "DataFrame", "Series", "list", "dict", "tuple", "np.array", "ndarray",
    "List", "Dict", "Tuple", "pd.", "np.",
)
# docstring keywords (CN + EN) hinting at data retrieval
DOC_KEYWORDS = (
    "数据", "行情", "历史", "获取", "查询", "下载", "接口", "实时", "序列",
    "data", "fetch", "history", "quote", "series", "records", "realtime",
    "retrieve", "download",
)
SKIP_DIR_NAMES = {
    "tests", "test", "__pycache__", "migrations", "venv", ".venv", "env",
    "build", "dist", ".git", "node_modules", "examples", "docs", ".tox",
    "site-packages",
}


def _qualified_module(file_path: Path, project_root: Path) -> str:
    try:
        rel = file_path.relative_to(project_root).with_suffix("")
    except ValueError:
        return file_path.stem
    parts = rel.parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    # strip a leading "src/" if present (src-layout projects)
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _has_network_call(fn_node: ast.FunctionDef) -> bool:
    """True if the function body calls a network module or a .get/.post/.request method."""
    for node in ast.walk(fn_node):
        if isinstance(node, ast.Attribute):
            # requests.get / httpx.post / session.get
            if node.attr in {"get", "post", "request", "put", "delete", "head"}:
                if isinstance(node.value, ast.Name) and node.value.id in NETWORK_MODULES:
                    return True
                # session/client object .get(...) - heuristic: any attribute access
                # of these methods counts as a network signal unless it's clearly not.
                # Keep it conservative: only count if the value looks like a client.
                if isinstance(node.value, ast.Name) and node.value.id.lower().endswith(
                    ("session", "client", "conn", "http")
                ):
                    return True
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in NETWORK_MODULES:
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in NETWORK_MODULES:
                return True
    return False


def _is_data_fetcher(fn_node: ast.FunctionDef) -> tuple[float, dict]:
    signals = {"name": False, "network": False, "return": False, "doc": False}
    name = fn_node.name
    if name.startswith("_"):
        return 0.0, signals

    lname = name.lower()
    if any(h in lname for h in FETCH_NAME_HINTS):
        signals["name"] = True

    if _has_network_call(fn_node):
        signals["network"] = True

    ret = ast.unparse(fn_node.returns) if fn_node.returns else ""
    if ret and any(h in ret for h in DATA_RETURN_HINTS):
        signals["return"] = True

    doc = (ast.get_docstring(fn_node) or "").lower()
    if any(k in doc for k in (d.lower() for d in DOC_KEYWORDS)):
        signals["doc"] = True

    score = (
        (0.35 if signals["name"] else 0.0)
        + (0.30 if signals["network"] else 0.0)
        + (0.20 if signals["return"] else 0.0)
        + (0.15 if signals["doc"] else 0.0)
    )
    return round(score, 3), signals


def _extract_params(fn_node: ast.FunctionDef) -> list[dict]:
    params: list[dict] = []
    args = fn_node.args
    posargs = [a for a in (args.posonlyargs + args.args) if a.arg not in ("self", "cls")]
    defaults = args.defaults
    n_without = len(posargs) - len(defaults)
    for i, a in enumerate(posargs):
        has_default = i >= n_without
        params.append({
            "name": a.arg,
            "annotation": ast.unparse(a.annotation) if a.annotation else "",
            "required": not has_default,
            "default": ast.unparse(defaults[i - n_without]) if has_default else None,
        })
    for i, a in enumerate(args.kwonlyargs):
        d = args.kw_defaults[i]
        params.append({
            "name": a.arg,
            "annotation": ast.unparse(a.annotation) if a.annotation else "",
            "required": d is None,
            "default": ast.unparse(d) if d is not None else None,
        })
    # **kwargs / *args - record but not as typed params
    return params


def _find_cli_exposed_names(tree: ast.Module) -> set[str]:
    """Names of functions already exposed via Click/typer/argparse-style decorators."""
    exposed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                d = ast.unparse(dec)
                if any(k in d for k in (
                    ".command", "click.command", "click.group", "typer.",
                    "app.command", "app.route", "ArgumentParser", "add_parser",
                    "parser.add_argument",
                )):
                    exposed.add(node.name)
    return exposed


def analyze(project_root: Path, package: str | None, min_score: float) -> dict:
    py_files = [
        p for p in project_root.rglob("*.py")
        if not any(part in SKIP_DIR_NAMES for part in p.relative_to(project_root).parts)
    ]
    candidates: list[dict] = []
    for pf in py_files:
        try:
            source = pf.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(pf))
        except (SyntaxError, UnicodeDecodeError):
            continue
        cli_exposed = _find_cli_exposed_names(tree)
        module = _qualified_module(pf, project_root)
        if package and not module.startswith(package):
            # still keep; package hint is informational
            pass
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if isinstance(node, ast.AsyncFunctionDef):
                continue
            score, signals = _is_data_fetcher(node)
            if score < min_score:
                continue
            candidates.append({
                "function": node.name,
                "module": module,
                "qualname": f"{module}.{node.name}" if module else node.name,
                "params": _extract_params(node),
                "return_type": ast.unparse(node.returns) if node.returns else "",
                "docstring": ast.get_docstring(node) or "",
                "signals": signals,
                "signal_score": score,
                "has_existing_cli": node.name in cli_exposed,
                "file": str(pf.relative_to(project_root)),
                "lineno": node.lineno,
            })
    candidates.sort(key=lambda c: c["signal_score"], reverse=True)
    return {
        "project_root": str(project_root),
        "package": package,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project_root")
    ap.add_argument("--package", default=None, help="expected import root, e.g. akshare")
    ap.add_argument("--min-score", type=float, default=0.3)
    args = ap.parse_args()
    root = Path(args.project_root).resolve()
    if not root.exists():
        sys.exit(f"project root not found: {root}")
    print(json.dumps(analyze(root, args.package, args.min_score), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
