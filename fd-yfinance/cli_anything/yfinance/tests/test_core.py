"""Unit tests for the yfinance core registry (no yfinance dependency required).

Seeds a temp SQLite DB from core.seed.REGISTRY and exercises the
RegistryService query API.
"""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cli_anything.yfinance.core.models import Base, Function, FunctionColumn
from cli_anything.yfinance.core.registry import RegistryService
from cli_anything.yfinance.core.seed import REGISTRY
from cli_anything.yfinance.core.migrate_registry import MigrationRunner


@pytest.fixture
def seeded_session():
    """A session over a temp DB seeded from the curated registry."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    MigrationRunner(session).run()
    session.commit()
    yield session
    session.close()
    engine.dispose()
    Path(tmp.name).unlink(missing_ok=True)


class TestRegistryService:
    def test_list_functions_count(self, seeded_session):
        svc = RegistryService(seeded_session)
        result = svc.list_functions()
        assert len(result) == len(REGISTRY)
        assert "ticker_history" in result
        assert "download" in result

    def test_search_by_name(self, seeded_session):
        svc = RegistryService(seeded_session)
        # "ohlcv" appears only in ticker_history's description
        result = svc.search_functions("ohlcv")
        assert "ticker_history" in result
        assert "ticker_dividends" not in result
        assert "download" not in result

    def test_search_by_category(self, seeded_session):
        svc = RegistryService(seeded_session)
        result = svc.search_functions("fundamentals")
        assert "ticker_info" in result
        assert "ticker_financials" in result
        assert "ticker_history" not in result

    def test_get_function_info(self, seeded_session):
        svc = RegistryService(seeded_session)
        info = svc.get_function_info("ticker_history")
        assert info is not None
        assert info["category"] == "price-history"
        params = info["parameters"]
        names = [p["name"] for p in params]
        assert "symbol" in names
        assert "period" in names

    def test_get_function_info_missing(self, seeded_session):
        svc = RegistryService(seeded_session)
        assert svc.get_function_info("does_not_exist") is None

    def test_get_categories(self, seeded_session):
        svc = RegistryService(seeded_session)
        cats = svc.get_categories()
        assert "price-history" in cats
        assert "fundamentals" in cats
        # fundamentals has 4 entries
        assert cats["fundamentals"] == 4

    def test_get_category_functions(self, seeded_session):
        svc = RegistryService(seeded_session)
        funcs = svc.get_category_functions("holders")
        assert "ticker_holders" in funcs
        assert len(funcs) == 1

    def test_ticker_convention(self, seeded_session):
        """All ticker_* entries have a 'symbol' required parameter."""
        svc = RegistryService(seeded_session)
        all_funcs = svc.list_functions()
        for name, info in all_funcs.items():
            if name.startswith("ticker_"):
                params = {p["name"]: p for p in info["parameters"]}
                assert "symbol" in params, f"{name} missing symbol param"
                assert params["symbol"].get("required") is True


class TestOutput:
    def test_format_dataframe(self):
        from cli_anything.yfinance.utils.output import format_output
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        out = format_output(df, json_output=False)
        assert out is None  # prints to stdout

    def test_format_dict(self):
        from cli_anything.yfinance.utils.output import format_output
        out = format_output({"key": "value"}, json_output=True)
        assert out is None  # prints to stdout
