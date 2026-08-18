from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_scope(path: str | None = None) -> dict:
    """Load the curated crawl scope from config/scope.yaml (or override path)."""
    path = path or os.environ.get("SCOPE_CONFIG", "config/scope.yaml")
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
