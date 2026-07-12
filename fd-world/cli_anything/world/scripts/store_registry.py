#!/usr/bin/env python3
"""
Store registry script for DAAS — discovers all functions from all sources
and persists them to both JSON and SQLite.

Usage:
    python store_registry.py                  # Full discovery + upsert
    python store_registry.py --source ckan    # Single source only
    python store_registry.py --dry-run        # Preview without writing
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure the harness package is importable
_HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _HARNESS_ROOT not in sys.path:
    sys.path.insert(0, _HARNESS_ROOT)

from cli_anything.world.core.database import get_database
from cli_anything.world.core.registry import RegistryService
from cli_anything.world.sources.config import load_sources, get_adapter


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Store DAAS function registry")
    parser.add_argument("--source", "-s", help="Only process a single source")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--output", "-o", help="Output path for registry.json (default: auto-detect)")
    args = parser.parse_args()

    configs = load_sources()
    if args.source:
        configs = [c for c in configs if c.name == args.source]
        if not configs:
            print(f"Source '{args.source}' not found in config")
            sys.exit(1)

    db = get_database()
    session = db.get_session()
    svc = RegistryService(session)

    all_functions = {}
    total_funcs = 0
    total_cols = 0

    try:
        for cfg in configs:
            print(f"\n[{cfg.name}] {cfg.label}")
            if not cfg.enabled:
                print(f"  SKIP: disabled")
                continue

            # Upsert source record
            if not args.dry_run:
                svc.upsert_source({
                    "name": cfg.name,
                    "label": cfg.label,
                    "description": cfg.description,
                    "url": cfg.url,
                    "enabled": cfg.enabled,
                    "config": cfg.config,
                })

            # Get adapter and discover functions
            adapter = get_adapter(cfg.name)
            if adapter is None:
                print(f"  WARN: no adapter registered for '{cfg.name}'")
                continue

            print(f"  Installed: {'yes' if adapter.is_available() else 'no'}")
            if not adapter.is_available():
                print(f"  Hint: {cfg.install_hint()}")

            try:
                funcs = adapter.discover()
            except Exception as e:
                print(f"  ERROR discovering: {e}")
                continue

            print(f"  Discovered: {len(funcs)} functions")

            if not args.dry_run:
                for func_data in funcs:
                    svc.upsert_function(cfg.name, func_data)
                    all_functions[func_data["name"]] = func_data
                    total_funcs += 1
                    total_cols += len(func_data.get("columns", []))
            else:
                for func_data in funcs:
                    all_functions[func_data["name"]] = func_data
                    total_funcs += 1
                    total_cols += len(func_data.get("columns", []))

        if not args.dry_run:
            session.commit()
            print(f"\nCommitted: {total_funcs} functions, {total_cols} columns")

        # Write registry.json
        metadata_dir = Path(_HARNESS_ROOT) / "cli_anything" / "daas" / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        json_path = args.output or str(metadata_dir / "registry.json")

        if not args.dry_run:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(all_functions, f, ensure_ascii=False, indent=2, default=str)
            print(f"Registry JSON written to: {json_path}")
        else:
            print(f"\n[DRY RUN] Would write {len(all_functions)} functions to {json_path}")
            # Show sample
            sample_keys = list(all_functions.keys())[:5]
            for k in sample_keys:
                info = all_functions[k]
                print(f"  {k}: {info.get('category', '')} — {info.get('description', '')[:60]}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
