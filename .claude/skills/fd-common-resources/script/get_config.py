#!/usr/bin/env python3
"""Read default.yaml and print the resolved default settings for each section.

Usage:
    get_defaults.py [OPTIONS] [SECTION...]

Examples:
    get_defaults.py                     # all defaults as YAML
    get_defaults.py models              # only models default
    get_defaults.py models databases    # models + databases defaults
    get_defaults.py --json              # output as JSON
    get_defaults.py --file custom.yaml  # use a different YAML file
    get_defaults.py --list              # list available sections
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "default.yaml"


def resolve_defaults(config: dict) -> dict:
    """Walk top-level keys, resolve each `default` against its `registry`."""
    resolved = {}

    for section, body in config.items():
        if not isinstance(body, dict):
            continue

        default_id = body.get("default")
        registry = body.get("registry", [])

        if default_id is None:
            continue

        entry = next((r for r in registry if r.get("id") == default_id), None)

        if entry is None:
            print(
                f"Warning: default '{default_id}' not found in {section}.registry",
                file=sys.stderr,
            )
            continue

        resolved[section] = {
            "default": default_id,
            "config": entry,
        }

    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve default registry entries from a YAML config file.",
    )
    parser.add_argument(
        "sections",
        nargs="*",
        metavar="SECTION",
        help="Sections to show (e.g. models, databases). Omit to show all.",
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to the YAML config file (default: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of YAML",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available section names and exit",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file) as f:
        config = yaml.safe_load(f)

    if args.list:
        sections = [k for k, v in config.items() if isinstance(v, dict) and "registry" in v]
        print("\n".join(sections))
        return

    resolved = resolve_defaults(config)

    # Filter by requested sections
    if args.sections:
        resolved = {k: v for k, v in resolved.items() if k in args.sections}

    if not resolved:
        print("No matching defaults found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(resolved, indent=2))
    else:
        print(yaml.dump(resolved, default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
