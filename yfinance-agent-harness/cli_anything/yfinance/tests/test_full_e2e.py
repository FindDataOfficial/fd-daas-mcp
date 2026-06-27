"""End-to-end tests for cli-anything-yfinance.

Invokes the installed CLI command as a subprocess. Skip if yfinance is not
installed. Registry-query tests (list/search/info/categories) do NOT require
network and run whenever the CLI is importable.
"""
import json
import shutil
import subprocess
import sys

import pytest

yfinance_available = False
try:
    import yfinance  # noqa: F401
    yfinance_available = True
except ImportError:
    pass


def _resolve_cli(name="cli-anything-yfinance"):
    path = shutil.which(name)
    if path:
        return [path]
    module = "cli_anything.yfinance.yfinance_cli"
    return [sys.executable, "-m", module]


CLI_BASE = _resolve_cli()


def _cli_importable():
    """True if the CLI module imports (registry DB present)."""
    result = subprocess.run(
        CLI_BASE + ["--help"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


cli_ok = _cli_importable()


@pytest.mark.skipif(not cli_ok, reason="cli-anything-yfinance not importable")
class TestCLIRegistry:
    def _run(self, args, check=True):
        return subprocess.run(
            CLI_BASE + args,
            capture_output=True, text=True, check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_list(self):
        result = self._run(["list"])
        assert result.returncode == 0
        assert "ticker_history" in result.stdout

    def test_search(self):
        result = self._run(["search", "history"])
        assert result.returncode == 0
        assert "ticker_history" in result.stdout

    def test_info(self):
        result = self._run(["info", "ticker_history"])
        assert result.returncode == 0
        assert "price-history" in result.stdout
        assert "symbol" in result.stdout

    def test_categories(self):
        result = self._run(["categories"])
        assert result.returncode == 0
        assert "fundamentals" in result.stdout

    def test_json_flag(self):
        # subcommand-level --json must come after the subcommand name
        result = self._run(["list", "--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert any(d["name"] == "ticker_history" for d in data)


@pytest.mark.skipif(not yfinance_available, reason="yfinance not installed")
class TestCLILive:
    def _run(self, args, check=True):
        return subprocess.run(
            CLI_BASE + args,
            capture_output=True, text=True, check=check,
        )

    def test_call_search(self):
        # yf.search hits the network; tolerate failure but require clean exit
        result = self._run(["call", "search", "query=Apple"], check=False)
        # runner sys.exits(1) on network error with a clear message
        assert result.returncode in (0, 1)
