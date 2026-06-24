"""
World Bank source adapter — uses wbgapi for indicator data.

Provides curated list of ~20 key World Bank indicators even without wbgapi installed.
When wbgapi is available, discovers the full indicator list on demand.
"""
from __future__ import annotations

from typing import Any

from cli_anything.daas.sources.base import SourceAdapter

# Curated key indicators — available even without wbgapi installed
KEY_INDICATORS = [
    ("NY.GDP.MKTP.CD", "GDP (current US$)", "macro"),
    ("NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)", "macro"),
    ("NY.GDP.PCAP.CD", "GDP per capita (current US$)", "macro"),
    ("SP.POP.TOTL", "Population, total", "demographics"),
    ("SP.POP.GROW", "Population growth (annual %)", "demographics"),
    ("SP.URB.TOTL", "Urban population", "demographics"),
    ("SL.UEM.TOTL.ZS", "Unemployment, total (% of labor force)", "labor"),
    ("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)", "macro"),
    ("NE.EXP.GNFS.CD", "Exports of goods and services (current US$)", "trade"),
    ("NE.IMP.GNFS.CD", "Imports of goods and services (current US$)", "trade"),
    ("BX.KLT.DINV.CD.WD", "Foreign direct investment, net inflows", "investment"),
    ("SE.PRM.ENRR", "School enrollment, primary (% gross)", "education"),
    ("SE.SEC.ENRR", "School enrollment, secondary (% gross)", "education"),
    ("SH.XPD.CHEX.GD.ZS", "Health expenditure (% of GDP)", "health"),
    ("SP.DYN.LE00.IN", "Life expectancy at birth, total (years)", "health"),
    ("IT.NET.USER.ZS", "Individuals using the Internet (% of population)", "technology"),
    ("EN.ATM.CO2E.KT", "CO2 emissions (kt)", "environment"),
    ("AG.LND.FRST.ZS", "Forest area (% of land area)", "environment"),
    ("EG.USE.ELEC.KH.PC", "Electric power consumption (kWh per capita)", "energy"),
    ("CM.MKT.LCAP.CD", "Market capitalization of listed companies (current US$)", "finance"),
]


class WorldBankAdapter(SourceAdapter):
    """Adapter for World Bank Open Data via wbgapi."""

    @property
    def name(self) -> str:
        return "worldbank"

    @property
    def label(self) -> str:
        return "World Bank"

    @property
    def description(self) -> str:
        return "World Bank Open Data — GDP, population, trade, education, health (1400+ indicators)"

    @property
    def url(self) -> str:
        return "https://data.worldbank.org/"

    def is_available(self) -> bool:
        try:
            import wbgapi
            return True
        except ImportError:
            return False

    def discover(self) -> list[dict]:
        """Return available World Bank indicator functions."""
        result = []
        for code, desc, category in KEY_INDICATORS:
            name = code.lower().replace(".", "_")
            result.append({
                "name": f"worldbank_{name}",
                "label": desc,
                "description": f"World Bank: {desc} (indicator: {code})",
                "category": category,
                "source": "worldbank",
                "parameters": [
                    {"name": "country", "type": "str", "required": False,
                     "description": "ISO 3-letter country code (e.g., CHN, USA) or 'all'"},
                    {"name": "time", "type": "str", "required": False,
                     "description": "Year or range (e.g., 2020 or 2015:2023)"},
                ],
                "columns": [
                    {"name": "country", "type": "str", "description": "Country name"},
                    {"name": "iso3", "type": "str", "description": "ISO 3-letter code"},
                    {"name": "year", "type": "str", "description": "Year"},
                    {"name": "value", "type": "float64", "description": desc},
                ],
            })
        return result

    def fetch(self, function_name: str, **params: Any) -> Any:
        """Fetch World Bank indicator data via REST API.

        Strips 'worldbank_' prefix, converts function name back to indicator code.
        Uses requests directly — wbgapi's internal API endpoints are unstable.
        """
        import requests
        import pandas as pd

        # Map function name back to indicator code
        local_name = function_name
        if local_name.startswith("worldbank_"):
            local_name = local_name[len("worldbank_"):]

        # Find matching indicator
        indicator_code = None
        for code, desc, category in KEY_INDICATORS:
            if code.lower().replace(".", "_") == local_name:
                indicator_code = code
                break

        if indicator_code is None:
            indicator_code = local_name.upper().replace("_", ".")

        country = params.get("country", "all")
        time = params.get("time", None)

        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator_code}"
        qs = {"format": "json", "per_page": 1000}
        if time:
            qs["date"] = time

        resp = requests.get(url, params=qs, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if len(data) < 2:
            return pd.DataFrame()

        rows = []
        for item in data[1]:
            if item.get("value") is None:
                continue
            rows.append({
                "country": item.get("country", {}).get("value", ""),
                "iso3": item.get("countryiso3code", ""),
                "year": item.get("date", ""),
                "value": float(item.get("value", 0)),
            })
        return pd.DataFrame(rows)

    def columns(self, function_name: str) -> list[dict]:
        """Return standard World Bank output columns."""
        local_name = function_name
        if local_name.startswith("worldbank_"):
            local_name = local_name[len("worldbank_"):]

        for code, desc, category in KEY_INDICATORS:
            if code.lower().replace(".", "_") == local_name:
                return [
                    {"name": "country", "type": "str", "description": "Country name"},
                    {"name": "iso3", "type": "str", "description": "ISO 3-letter code"},
                    {"name": "year", "type": "str", "description": "Year"},
                    {"name": "value", "type": "float64", "description": desc},
                ]
        return [
            {"name": "economy", "type": "str", "description": "Country or region"},
            {"name": "time", "type": "str", "description": "Year"},
            {"name": "value", "type": "float64", "description": "Indicator value"},
        ]
