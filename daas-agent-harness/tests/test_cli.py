"""Smoke tests for DAAS CLI — run with: uv run pytest -v"""
import pytest
import subprocess
import sys


def _cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cli_anything.daas.cli"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_list_sources():
    """list-sources should return all 4 sources."""
    result = _cli(["list-sources"])
    assert result.returncode == 0
    assert "akshare" in result.stdout
    assert "worldbank" in result.stdout
    assert "ckan" in result.stdout
    assert "cnstats" in result.stdout


def test_list_sources_json():
    """list-sources --json should return valid JSON."""
    result = _cli(["list-sources", "--json"])
    assert result.returncode == 0
    import json
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 4
    names = [s["name"] for s in data]
    assert "akshare" in names
    assert "worldbank" in names


def test_search():
    """search should find GDP-related functions."""
    result = _cli(["search", "GDP"])
    assert result.returncode == 0
    assert "gdp" in result.stdout.lower()


def test_search_json():
    """search --json should return valid JSON."""
    result = _cli(["search", "--json", "GDP"])
    assert result.returncode == 0
    import json
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) > 0


def test_categories():
    """categories should list categories from adapters."""
    result = _cli(["categories"])
    assert result.returncode == 0
    # Should have at least one category
    assert len(result.stdout) > 0


def test_describe():
    """describe should show function details."""
    result = _cli(["describe", "worldbank_ny_gdp_mktp_cd"])
    assert result.returncode == 0
    assert "GDP" in result.stdout


def test_help():
    """help command should work."""
    result = _cli(["help"])
    assert result.returncode == 0


@pytest.mark.skipif(
    True,  # Don't call live APIs in CI
    reason="Live API calls require network and optional deps",
)
def test_call_akshare():
    """Integration test: call akshare function."""
    result = _cli(["call", "akshare_stock_zh_a_hist", "symbol=000001", "period=monthly"])
    assert result.returncode == 0
