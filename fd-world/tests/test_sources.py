"""Tests for DAAS source adapters."""
import pytest

from cli_anything.daas.sources.base import SourceAdapter


class DummySource(SourceAdapter):
    """Test adapter that returns fixed data."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def label(self) -> str:
        return "Dummy Source"

    @property
    def description(self) -> str:
        return "A dummy test source"

    def discover(self) -> list[dict]:
        return [
            {
                "name": "dummy_hello",
                "label": "Hello Function",
                "description": "Returns hello data",
                "category": "greeting",
                "source": "dummy",
                "parameters": [{"name": "name", "type": "str", "required": False}],
                "columns": [
                    {"name": "greeting", "type": "str", "description": "The greeting"},
                ],
            },
        ]

    def fetch(self, function_name: str, **params):
        import pandas as pd
        name = params.get("name", "world")
        return pd.DataFrame([{"greeting": f"Hello, {name}!"}])

    def columns(self, function_name: str) -> list[dict]:
        return [
            {"name": "greeting", "type": "str", "description": "The greeting"},
        ]


def test_source_adapter_abc():
    """SourceAdapter should require abstract methods."""
    with pytest.raises(TypeError):
        SourceAdapter()  # Can't instantiate ABC


def test_dummy_adapter():
    """Dummy adapter should implement all methods."""
    adapter = DummySource()
    assert adapter.name == "dummy"
    assert adapter.label == "Dummy Source"

    funcs = adapter.discover()
    assert len(funcs) == 1
    assert funcs[0]["name"] == "dummy_hello"

    cols = adapter.columns("dummy_hello")
    assert len(cols) == 1
    assert cols[0]["name"] == "greeting"


def test_dummy_adapter_fetch():
    """Dummy adapter should return a DataFrame."""
    adapter = DummySource()
    result = adapter.fetch("dummy_hello", name="test")
    import pandas as pd
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["greeting"] == "Hello, test!"


def test_dummy_adapter_is_available():
    """Dummy adapter should always be available."""
    adapter = DummySource()
    assert adapter.is_available() is True


def test_akshare_adapter_discover():
    """AKShare adapter should return curated stubs even without akshare."""
    from cli_anything.daas.sources.akshare_source import AKShareAdapter
    adapter = AKShareAdapter()
    funcs = adapter.discover()
    assert len(funcs) > 0
    # All function names should have akshare_ prefix
    for f in funcs:
        assert f["name"].startswith("akshare_")


def test_worldbank_adapter_discover():
    """World Bank adapter should return 20 key indicators."""
    from cli_anything.daas.sources.worldbank_source import WorldBankAdapter
    adapter = WorldBankAdapter()
    funcs = adapter.discover()
    assert len(funcs) == 20
    for f in funcs:
        assert f["name"].startswith("worldbank_")
        assert "parameters" in f
        assert "columns" in f


def test_ckan_adapter_discover():
    """CKAN adapter should return 5 function stubs."""
    from cli_anything.daas.sources.ckan_source import CKANAdapter
    adapter = CKANAdapter()
    funcs = adapter.discover()
    assert len(funcs) == 5
    for f in funcs:
        assert f["name"].startswith("ckan_")


def test_cnstats_adapter_discover():
    """CNStats adapter should return 8 NBS functions."""
    from cli_anything.daas.sources.cnstats_source import CNStatsAdapter
    adapter = CNStatsAdapter()
    funcs = adapter.discover()
    assert len(funcs) == 8
    for f in funcs:
        assert f["name"].startswith("cnstats_")
