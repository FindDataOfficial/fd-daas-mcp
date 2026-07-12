"""
AKShare source adapter — wraps the existing akshare registry + library.

discover() delegates to the akshare harness registry.
fetch() calls akshare functions directly.
columns() returns column metadata from the registry.
"""
from __future__ import annotations

from typing import Any

from cli_anything.world.sources.base import SourceAdapter


class AKShareAdapter(SourceAdapter):
    """Adapter for AKShare Chinese financial data library."""

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def label(self) -> str:
        return "AKShare"

    @property
    def description(self) -> str:
        return "Chinese financial data — stocks, funds, futures, macro, bonds (673+ functions)"

    @property
    def url(self) -> str:
        return "https://github.com/akfamily/akshare"

    def is_available(self) -> bool:
        try:
            import akshare
            return True
        except ImportError:
            return False

    def discover(self) -> list[dict]:
        """Return all AKShare functions from the existing registry."""
        try:
            from cli_anything.akshare.core.registry import list_functions as akshare_list

            funcs = akshare_list()
            if not funcs:
                return self._stub_functions()
            result = []
            for name, info in funcs.items():
                result.append({
                    "name": f"akshare_{name}",
                    "label": info.get("description", name),
                    "description": info.get("description", ""),
                    "category": info.get("category", "未分类"),
                    "parameters": info.get("parameters", []),
                    "columns": info.get("columns", []),
                    "source": "akshare",
                })
            return result
        except ImportError:
            # akshare harness not installed — return curated stub
            return self._stub_functions()

    def _stub_functions(self) -> list[dict]:
        """Curated stub when akshare harness is not available."""
        return [
            {
                "name": "akshare_stock_zh_a_hist",
                "label": "A-Share Historical Data",
                "description": "Daily historical data for Chinese A-share stocks",
                "category": "stock",
                "source": "akshare",
                "parameters": [
                    {"name": "symbol", "type": "str", "required": True, "description": "Stock code, e.g. 000001"},
                    {"name": "period", "type": "str", "required": False, "description": "daily, weekly, monthly"},
                    {"name": "start_date", "type": "str", "required": False, "description": "YYYYMMDD"},
                    {"name": "end_date", "type": "str", "required": False, "description": "YYYYMMDD"},
                ],
                "columns": [
                    {"name": "日期", "type": "datetime64", "description": "Trade date"},
                    {"name": "开盘", "type": "float64", "description": "Open price"},
                    {"name": "收盘", "type": "float64", "description": "Close price"},
                    {"name": "最高", "type": "float64", "description": "High price"},
                    {"name": "最低", "type": "float64", "description": "Low price"},
                    {"name": "成交量", "type": "int64", "description": "Volume"},
                    {"name": "成交额", "type": "float64", "description": "Turnover"},
                ],
            },
        ]

    def fetch(self, function_name: str, **params: Any) -> Any:
        """Execute an AKShare function.

        Strips 'akshare_' prefix from function name before calling akshare.
        """
        from cli_anything.world.core.exceptions import SourceUnavailableError, FunctionNotFoundError

        if not self.is_available():
            raise SourceUnavailableError("akshare", "Install: pip install akshare")

        import akshare
        import pandas as pd

        # Strip namespace prefix
        local_name = function_name
        if local_name.startswith("akshare_"):
            local_name = local_name[len("akshare_"):]

        func = getattr(akshare, local_name, None)
        if func is None:
            raise FunctionNotFoundError(function_name)

        # Handle akshare's weird pattern: some functions return None if params are wrong
        result = func(**params)
        if result is None:
            return pd.DataFrame()
        return result

    def columns(self, function_name: str) -> list[dict]:
        """Return column metadata from the registry."""
        try:
            from cli_anything.akshare.core.registry import get_function_info as akshare_info

            local_name = function_name
            if local_name.startswith("akshare_"):
                local_name = local_name[len("akshare_"):]

            info = akshare_info(local_name)
            if info:
                return info.get("columns", [])
        except ImportError:
            pass
        return []
