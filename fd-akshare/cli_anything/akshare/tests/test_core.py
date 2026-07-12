"""Unit tests for core modules (no AKShare dependency required for registry tests)."""

import json
import os
import sys
import tempfile

import pytest

from cli_anything.akshare.core import registry


# Fixture: minimal fake registry
@pytest.fixture
def fake_registry():
    data = {
        "stock_sse_summary": {
            "category": "股票市场总貌",
            "description": "上海证券交易所-股票数据总貌",
            "source": "http://www.sse.com.cn",
            "parameters": [{"name": "date", "type": "str", "required": False}],
            "columns": [{"name": "单日情况", "type": "object"}],
        },
        "stock_szse_summary": {
            "category": "股票市场总貌",
            "description": "深圳证券交易所-市场总貌",
            "source": "http://www.szse.cn",
            "parameters": [{"name": "date", "type": "str", "required": False}],
        },
        "stock_zh_a_hist": {
            "category": "历史行情数据",
            "description": "A股历史行情",
            "parameters": [
                {"name": "symbol", "type": "str", "required": True},
                {"name": "start_date", "type": "str", "required": False},
                {"name": "end_date", "type": "str", "required": False},
            ],
        },
        "fund_etf_hist_em": {
            "category": "ETF基金历史",
            "description": "ETF基金历史行情",
            "parameters": [{"name": "symbol", "type": "str", "required": True}],
        },
    }
    # Temporarily replace the global registry
    old_registry = registry._registry
    registry._registry = data
    yield data
    registry._registry = old_registry


class TestRegistry:
    def test_list_functions(self, fake_registry):
        result = registry.list_functions()
        assert len(result) == 4
        assert "stock_sse_summary" in result
        assert "fund_etf_hist_em" in result

    def test_search_by_name(self, fake_registry):
        result = registry.search_functions("stock_sse")
        assert "stock_sse_summary" in result
        assert "fund_etf_hist_em" not in result

    def test_search_by_category(self, fake_registry):
        result = registry.search_functions("股票市场")
        assert "stock_sse_summary" in result
        assert "stock_szse_summary" in result
        assert "stock_zh_a_hist" not in result

    def test_search_by_description(self, fake_registry):
        result = registry.search_functions("证券交易所")
        assert "stock_sse_summary" in result
        assert "stock_szse_summary" in result

    def test_get_function_info(self, fake_registry):
        info = registry.get_function_info("stock_zh_a_hist")
        assert info is not None
        assert info["category"] == "历史行情数据"
        assert len(info["parameters"]) == 3

    def test_get_function_info_missing(self, fake_registry):
        info = registry.get_function_info("nonexistent")
        assert info is None

    def test_get_categories(self, fake_registry):
        cats = registry.get_categories()
        assert "股票市场总貌" in cats
        assert cats["股票市场总貌"] == 2
        assert cats["历史行情数据"] == 1

    def test_category_functions(self, fake_registry):
        funcs = registry.get_category_functions("股票市场总貌")
        assert len(funcs) == 2
        assert "stock_sse_summary" in funcs


class TestOutput:
    def test_format_dataframe(self):
        from cli_anything.akshare.utils.output import format_output
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        # Should not raise
        out = format_output(df, json_output=False)
        assert out is None  # prints to stdout

    def test_format_dict(self):
        from cli_anything.akshare.utils.output import format_output
        data = {"key": "value", "num": 42}
        out = format_output(data, json_output=True)
        assert out is None  # prints to stdout
