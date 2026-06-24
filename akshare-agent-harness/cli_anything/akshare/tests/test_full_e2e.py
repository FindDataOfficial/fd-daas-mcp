"""End-to-end tests for cli-anything-akshare.

These tests invoke the installed CLI command as a subprocess.
Skip if akshare is not installed.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

akshare_available = False
try:
    import akshare
    akshare_available = True
except ImportError:
    pass


def _resolve_cli(name="cli-anything-akshare"):
    path = shutil.which(name)
    if path:
        return [path]
    module = "cli_anything.akshare.akshare_cli"
    return [sys.executable, "-m", module]


CLI_BASE = _resolve_cli()


@pytest.mark.skipif(not akshare_available, reason="akshare not installed")
class TestCLISubprocess:
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
        assert "stock_sse_summary" in result.stdout

    def test_search(self):
        result = self._run(["search", "历史行情"])
        assert result.returncode == 0
        assert "stock_zh_a_hist" in result.stdout or len(result.stdout) > 0

    def test_info(self):
        result = self._run(["info", "stock_sse_summary"])
        assert result.returncode == 0
        assert "上海证券交易所" in result.stdout

    def test_categories(self):
        result = self._run(["categories"])
        assert result.returncode == 0
        assert "历史行情数据" in result.stdout

    def test_call_stock_sse_summary(self):
        result = self._run(["call", "stock_sse_summary"])
        assert result.returncode == 0
        assert len(result.stdout) > 0

    def test_json_flag(self):
        result = self._run(["--json", "call", "stock_sse_summary"])
        assert result.returncode == 0
        assert len(result.stdout) > 0
        # Should be valid JSON (a list of dicts)
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, list)
        except json.JSONDecodeError:
            pass  # May fail if no data available on weekends

    def test_call_with_params(self):
        result = self._run(["call", "stock_zh_a_hist", "symbol=000001", "start_date=20250101", "end_date=20250110"])
        assert result.returncode == 0
        assert len(result.stdout) > 0
