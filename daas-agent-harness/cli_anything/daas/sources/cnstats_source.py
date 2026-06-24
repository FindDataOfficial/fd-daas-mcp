"""
Chinese National Statistics source adapter.

Uses akshare macro functions for NBS data: CPI, PMI, industrial output,
fixed asset investment, retail sales, etc.
"""
from __future__ import annotations

from typing import Any

from cli_anything.daas.sources.base import SourceAdapter

# Curated NBS macro indicators
CNSTATS_FUNCTIONS = [
    {
        "name": "cnstats_cpi",
        "label": "CPI — Consumer Price Index",
        "description": "Monthly CPI year-over-year change for China",
        "category": "macro",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "全国同比", "type": "float64", "description": "National YoY %"},
            {"name": "全国环比", "type": "float64", "description": "National MoM %"},
            {"name": "城市同比", "type": "float64", "description": "Urban YoY %"},
            {"name": "农村同比", "type": "float64", "description": "Rural YoY %"},
        ],
    },
    {
        "name": "cnstats_pmi",
        "label": "PMI — Purchasing Managers Index",
        "description": "Monthly manufacturing and non-manufacturing PMI for China",
        "category": "macro",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "制造业", "type": "float64", "description": "Manufacturing PMI"},
            {"name": "非制造业", "type": "float64", "description": "Non-manufacturing PMI"},
            {"name": "综合", "type": "float64", "description": "Composite PMI"},
        ],
    },
    {
        "name": "cnstats_industrial_output",
        "label": "Industrial Output Growth",
        "description": "Monthly industrial added value growth rate for China",
        "category": "industry",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "工业增加值同比", "type": "float64", "description": "Industrial output YoY %"},
            {"name": "累计同比", "type": "float64", "description": "Cumulative YoY %"},
        ],
    },
    {
        "name": "cnstats_fixed_asset_investment",
        "label": "Fixed Asset Investment",
        "description": "Monthly fixed asset investment growth for China",
        "category": "investment",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "固定资产投资同比", "type": "float64", "description": "FAI YoY %"},
            {"name": "民间投资同比", "type": "float64", "description": "Private investment YoY %"},
        ],
    },
    {
        "name": "cnstats_retail_sales",
        "label": "Retail Sales Growth",
        "description": "Monthly total retail sales of consumer goods growth rate",
        "category": "consumption",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "社会消费品零售总额同比", "type": "float64", "description": "Retail sales YoY %"},
            {"name": "限额以上同比", "type": "float64", "description": "Above-designated-size YoY %"},
        ],
    },
    {
        "name": "cnstats_gdp_quarterly",
        "label": "GDP Quarterly Growth",
        "description": "Quarterly GDP growth rates for China",
        "category": "macro",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Quarter"},
            {"name": "GDP同比", "type": "float64", "description": "GDP YoY %"},
            {"name": "GDP环比", "type": "float64", "description": "GDP QoQ %"},
            {"name": "第一产业同比", "type": "float64", "description": "Primary industry YoY %"},
            {"name": "第二产业同比", "type": "float64", "description": "Secondary industry YoY %"},
            {"name": "第三产业同比", "type": "float64", "description": "Tertiary industry YoY %"},
        ],
    },
    {
        "name": "cnstats_trade_balance",
        "label": "Trade Balance",
        "description": "Monthly import/export data for China",
        "category": "trade",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "出口金额", "type": "float64", "description": "Export value (USD)"},
            {"name": "进口金额", "type": "float64", "description": "Import value (USD)"},
            {"name": "贸易差额", "type": "float64", "description": "Trade balance (USD)"},
        ],
    },
    {
        "name": "cnstats_money_supply",
        "label": "Money Supply",
        "description": "Monthly M0, M1, M2 money supply data for China",
        "category": "finance",
        "parameters": [],
        "columns": [
            {"name": "日期", "type": "datetime64", "description": "Date"},
            {"name": "M0", "type": "float64", "description": "M0 money supply"},
            {"name": "M1", "type": "float64", "description": "M1 money supply"},
            {"name": "M2", "type": "float64", "description": "M2 money supply"},
        ],
    },
]


class CNStatsAdapter(SourceAdapter):
    """Adapter for Chinese National Bureau of Statistics data via akshare."""

    @property
    def name(self) -> str:
        return "cnstats"

    @property
    def label(self) -> str:
        return "Chinese Statistics"

    @property
    def description(self) -> str:
        return "National Bureau of Statistics macro indicators — CPI, PMI, industrial output, retail sales"

    @property
    def url(self) -> str:
        return "https://data.stats.gov.cn/"

    def is_available(self) -> bool:
        try:
            import akshare
            return True
        except ImportError:
            return False

    def discover(self) -> list[dict]:
        """Return curated NBS macro indicator functions."""
        result = []
        for func in CNSTATS_FUNCTIONS:
            result.append({**func, "source": "cnstats"})
        return result

    def fetch(self, function_name: str, **params: Any) -> Any:
        """Fetch Chinese statistics data via akshare macro functions.

        Maps cnstats function names to akshare functions:
          cnstats_cpi -> macro_china_cpi_yearly
          cnstats_pmi -> macro_china_pmi
          cnstats_industrial_output -> macro_china_industrial_production
          etc.
        """
        from cli_anything.daas.core.exceptions import SourceUnavailableError, FunctionNotFoundError

        if not self.is_available():
            raise SourceUnavailableError("cnstats", "Install: pip install akshare")

        import akshare as ak
        import pandas as pd

        # Strip namespace prefix
        local_name = function_name
        if local_name.startswith("cnstats_"):
            local_name = local_name[len("cnstats_"):]

        # Map to akshare function names
        mapping = {
            "cpi": "macro_china_cpi_yearly",
            "pmi": "macro_china_pmi",
            "industrial_output": "macro_china_industrial_production_yoy",
            "fixed_asset_investment": "macro_china_fixed_asset_investment",
            "retail_sales": "macro_china_consumer_goods_retail",
            "gdp_quarterly": "macro_china_gdp_yearly",
            "trade_balance": "macro_china_trade_balance",
            "money_supply": "macro_china_money_supply",
        }

        ak_func_name = mapping.get(local_name)
        if ak_func_name is None:
            raise FunctionNotFoundError(function_name)

        func = getattr(ak, ak_func_name, None)
        if func is None:
            raise FunctionNotFoundError(function_name)

        try:
            return func()
        except Exception:
            # Some akshare macro functions need specific params
            return func

    def columns(self, function_name: str) -> list[dict]:
        """Return column metadata from curated definitions."""
        local_name = function_name
        if local_name.startswith("cnstats_"):
            local_name = local_name[len("cnstats_"):]

        for func in CNSTATS_FUNCTIONS:
            if func["name"] == f"cnstats_{local_name}":
                return func.get("columns", [])
        return []
