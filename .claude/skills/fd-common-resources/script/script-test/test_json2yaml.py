"""Tests for scripts/json2yaml.py."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
JSON2YAML = SCRIPTS_DIR / "json2yaml.py"


def run_cli(*args, stdin_data=None):
    """Run json2yaml.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(JSON2YAML), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=stdin_data,
    )
    return result.returncode, result.stdout, result.stderr


# ---- file input tests ----


def test_file_to_stdout():
    """Convert a JSON file and print YAML to stdout."""
    data = {"key": "value", "list": [1, 2, 3]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        tmp_path = f.name

    try:
        rc, stdout, stderr = run_cli(tmp_path)
        assert rc == 0
        parsed = yaml.safe_load(stdout)
        assert parsed == data
    finally:
        os.unlink(tmp_path)


def test_file_to_file():
    """Convert a JSON file and write YAML to an output file."""
    data = {"nested": {"deep": [{"a": 1}, {"b": 2}]}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        in_path = f.name

    out_path = in_path.replace(".json", ".yaml")

    try:
        rc, stdout, stderr = run_cli(in_path, "-o", out_path)
        assert rc == 0
        assert os.path.exists(out_path)

        with open(out_path) as f:
            parsed = yaml.safe_load(f)
        assert parsed == data
    finally:
        os.unlink(in_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


def test_missing_file():
    """Non-existent file should exit with code 1 and print an error."""
    rc, stdout, stderr = run_cli("nonexistent.json")
    assert rc == 1
    assert "not found" in stderr


# ---- stdin tests ----


def test_stdin_basic():
    """Pipe JSON via stdin and get YAML on stdout."""
    data = {"hello": "world"}
    rc, stdout, stderr = run_cli(stdin_data=json.dumps(data))
    assert rc == 0
    parsed = yaml.safe_load(stdout)
    assert parsed == data


def test_stdin_array():
    """Handle a top-level JSON array."""
    data = [{"id": 1}, {"id": 2}, {"id": 3}]
    rc, stdout, stderr = run_cli(stdin_data=json.dumps(data))
    assert rc == 0
    parsed = yaml.safe_load(stdout)
    assert parsed == data


def test_stdin_primitives():
    """Handle scalar JSON values (string, number, bool, null)."""
    cases = [
        ("hello", "hello"),
        (42, 42),
        (3.14, 3.14),
        (True, True),
        (False, False),
        (None, None),
    ]

    for json_val, expected in cases:
        rc, stdout, stderr = run_cli(stdin_data=json.dumps(json_val))
        assert rc == 0, f"Failed for {json_val}"
        parsed = yaml.safe_load(stdout)
        assert parsed == expected


def test_stdin_invalid_json():
    """Malformed JSON on stdin should cause an error."""
    rc, stdout, stderr = run_cli(stdin_data="{bad json}")
    assert rc != 0


# ---- flag tests ----


def test_compact_flag():
    """--compact should produce inline/flow-style YAML."""
    data = {"a": 1, "b": 2}
    rc, stdout, stderr = run_cli("--compact", stdin_data=json.dumps(data))
    assert rc == 0
    # Compact output uses {} or inline style
    assert "{" in stdout or "a: 1" in stdout


def test_indent_flag():
    """--indent should change the indentation width."""
    data = {"parent": {"child": "val"}}
    rc, stdout, stderr = run_cli("--indent", "4", stdin_data=json.dumps(data))
    assert rc == 0
    # With indent=4, nested keys should be indented by 4 spaces
    lines = stdout.splitlines()
    child_line = [l for l in lines if "child" in l]
    assert child_line
    assert child_line[0].startswith("    ")  # 4 spaces


def test_sort_keys_flag():
    """--sort-keys should output keys in alphabetical order."""
    data = {"z": 3, "a": 1, "m": 2}
    rc, stdout, stderr = run_cli("--sort-keys", stdin_data=json.dumps(data))
    assert rc == 0
    parsed = yaml.safe_load(stdout)
    assert parsed == data

    # Check key ordering in output
    lines = [l for l in stdout.splitlines() if l and not l.startswith(" ")]
    keys = [l.split(":")[0] for l in lines]
    assert keys == sorted(keys)


# ---- round-trip tests ----


def test_round_trip_complex():
    """A complex nested structure should survive JSON→YAML→dict intact."""
    data = {
        "models": {
            "default": "claude-sonnet",
            "providers": {
                "anthropic": {
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "base_url": "https://api.anthropic.com",
                },
            },
            "registry": [
                {
                    "id": "claude-sonnet",
                    "provider": "anthropic",
                    "name": "claude-sonnet-4-6",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                },
                {
                    "id": "deepseek-v4-pro",
                    "provider": "volcengine",
                    "name": "deepseek-v4-pro",
                    "max_tokens": 8192,
                    "temperature": 0.7,
                },
            ],
        },
        "databases": {
            "default": "sqlite-dev",
            "registry": [
                {
                    "id": "sqlite-dev",
                    "driver": "sqlite",
                    "url": "sqlite:///data/dev.db",
                    "pool": {"min_size": 1, "max_size": 5, "timeout_seconds": 30},
                    "auto_migrate": True,
                },
            ],
        },
    }

    rc, stdout, stderr = run_cli(stdin_data=json.dumps(data))
    assert rc == 0
    parsed = yaml.safe_load(stdout)
    assert parsed == data


def test_round_trip_file_to_file():
    """File → YAML file → reload should match original dict."""
    data = {
        "logging": {"level": "debug", "format": "text", "output": "stdout"},
        "runtime": {"workers": 8, "request_timeout": 120},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        in_path = f.name

    out_path = in_path.replace(".json", ".yaml")

    try:
        rc, _, _ = run_cli(in_path, "-o", out_path)
        assert rc == 0

        with open(out_path) as f:
            parsed = yaml.safe_load(f)
        assert parsed == data
    finally:
        os.unlink(in_path)
        if os.path.exists(out_path):
            os.unlink(out_path)
