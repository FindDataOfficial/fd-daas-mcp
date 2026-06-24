#!/usr/bin/env python3
"""Convert JSON to YAML.

Usage:
    json2yaml.py [OPTIONS] [INPUT]

Examples:
    json2yaml.py config.json              # print YAML to stdout
    json2yaml.py config.json -o out.yaml  # write to file
    cat config.json | json2yaml.py        # read from stdin
    echo '{"key": "value"}' | json2yaml.py
    json2yaml.py --compact config.json    # compact YAML output
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert JSON to YAML.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Path to a JSON file. Reads from stdin if omitted.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Write YAML to a file instead of stdout.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Use compact YAML output (default_flow_style=True).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indentation width (default: 2).",
    )
    parser.add_argument(
        "--sort-keys",
        action="store_true",
        help="Sort mapping keys alphabetically.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Read input
    if args.input:
        if not args.input.exists():
            print(f"Error: file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # Convert to YAML
    yaml_str = yaml.dump(
        data,
        default_flow_style=args.compact,
        indent=args.indent,
        allow_unicode=True,
        sort_keys=args.sort_keys,
    )

    # Write output
    if args.output:
        args.output.write_text(yaml_str, encoding="utf-8")
    else:
        sys.stdout.write(yaml_str)


if __name__ == "__main__":
    main()
