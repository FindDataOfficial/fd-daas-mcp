"""
World Bank data source adapter — uses the `world_bank_data` PyPI package.

Distinct from worldbank_source.py (which uses wbgapi / REST). This adapter wraps
`world_bank_data.get_series`, which returns a pandas Series with a MultiIndex
whose level names come from the World Bank API's `dimension.id` field
(typically `country`, `date`, `series`). We normalize that to a flat DataFrame
with columns [country, year, value].
"""
from __future__ import annotations

from typing import Any

from cli_anything.daas.sources.base import SourceAdapter
from cli_anything.daas.sources.worldbank_source import KEY_INDICATORS


def _func_name(indicator_code: str) -> str:
    """Indicator code → namespaced function name. NY.GDP.MKTP.CD → wbdata_ny_gdp_mktp_cd."""
    return "wbdata_" + indicator_code.lower().replace(".", "_")


def _code_from_func(function_name: str) -> str:
    """Inverse of _func_name: wbdata_ny_gdp_mktp_cd → NY.GDP.MKTP.CD."""
    local = function_name
    if local.startswith("wbdata_"):
        local = local[len("wbdata_"):]
    for code, _desc, _cat in KEY_INDICATORS:
        if code.lower().replace(".", "_") == local:
            return code
    # Fall back to mechanical conversion for ad-hoc indicators.
    return local.upper().replace("_", ".")


# Topic mapping by World Bank indicator-code prefix. Used to assign a coarse
# category to the ~16k indicators fetched via discover_full().
_PREFIX_CATEGORIES = [
    ("NY.GDP", "macro"), ("NY.GNP", "macro"), ("FP.CPI", "macro"), ("FP.WPI", "macro"),
    ("NE.EXP", "trade"), ("NE.IMP", "trade"), ("BX.GRT", "trade"), ("TM.VAL", "trade"),
    ("TX.VAL", "trade"), ("TG.VAL", "trade"), ("BN.GSR", "trade"), ("BN.CAB", "macro"),
    ("SP.POP", "demographics"), ("SP.URB", "demographics"), ("SP.DYN", "demographics"),
    ("SP.M18", "demographics"), ("SP.HOU", "demographics"),
    ("SL.UEM", "labor"), ("SL.TLF", "labor"), ("SL.EMP", "labor"), ("SL.AGR", "labor"),
    ("SE.PRM", "education"), ("SE.SEC", "education"), ("SE.TER", "education"),
    ("SE.XPD", "education"), ("SE.ENR", "education"), ("SE.COM", "education"),
    ("SH.XPD", "health"), ("SH.DYN", "health"), ("SH.HIV", "health"), ("SH.MMR",
    "health"), ("SH.IMM", "health"), ("SH.STA", "health"), ("SH.MED", "health"),
    ("SH.TBS", "health"),
    ("EN.ATM", "environment"), ("EN.CLC", "environment"), ("EN.POP", "environment"),
    ("AG.LND", "environment"), ("AG.YLD", "environment"), ("AG.CON", "environment"),
    ("EG.USE", "energy"), ("EG.ELC", "energy"), ("EG.FEC", "energy"), ("EG.GDP", "energy"),
    ("IT.NET", "technology"), ("IT.CEL", "technology"), ("IT.MLT", "technology"),
    ("IC.FRM", "business"), ("IC.BUS", "business"), ("IC.LGL", "business"),
    ("BX.KLT", "investment"), ("CM.MKT", "finance"), ("FM.LBL", "finance"),
    ("GC.TAX", "finance"), ("GC.XPN", "finance"), ("GC.DOD", "finance"),
    ("DT.DOD", "debt"), ("DT.TDS", "debt"), ("DT.ODA", "debt"),
    ("IQ.CPA", "governance"), ("per", "governance"),
    ("SG.GEN", "gender"), ("SG.LAW", "gender"), ("SG.VIO", "gender"),
    ("HD.HCI", "human_capital"),
]


def _category_from_code(code: str, name: str = "") -> str:
    """Coarse category from a World Bank indicator code (and optional name)."""
    up = code.upper()
    for prefix, cat in _PREFIX_CATEGORIES:
        if up.startswith(prefix.upper()):
            return cat
    low = (name or "").lower()
    for kw, cat in [
        ("gdp", "macro"), ("inflation", "macro"), ("price", "macro"),
        ("population", "demographics"), ("health", "health"), ("education", "education"),
        ("export", "trade"), ("import", "trade"), ("energy", "energy"), ("emission",
        "environment"), ("co2", "environment"),
    ]:
        if kw in low:
            return cat
    return "other"


class WbDataAdapter(SourceAdapter):
    """Adapter for World Bank Open Data via the `world_bank_data` package."""

    @property
    def name(self) -> str:
        return "wbdata"

    @property
    def label(self) -> str:
        return "World Bank (world_bank_data)"

    @property
    def description(self) -> str:
        return (
            "World Bank Open Data via the world_bank_data package — GDP, population, "
            "trade, education, health, environment indicators (yearly cadence)"
        )

    @property
    def url(self) -> str:
        return "https://github.com/mwouts/world_bank_data"

    def is_available(self) -> bool:
        try:
            import world_bank_data  # noqa: F401
            return True
        except ImportError:
            return False

    def discover(self) -> list[dict]:
        """Return available indicator functions (curated key indicators).

        This returns the fast offline-curated subset (20 indicators) so the
        CLI `search` command stays snappy. For the full ~16k-indicator catalog,
        use `discover_full()` (requires network + the package installed), or
        load the catalog into the DB via load_wbdata_catalog.py.
        """
        result = []
        for code, desc, category in KEY_INDICATORS:
            result.append(self._function_dict(code, desc, category))
        return result

    def discover_full(self) -> list[dict]:
        """Return ALL World Bank indicators via world_bank_data.get_indicators().

        Requires network access to api.worldbank.org and the `world_bank_data`
        package installed. Returns one function dict per indicator (~16k).
        Use this for bulk-loading the catalog into the DB; do NOT call it from
        the CLI `search` hot path (it is a slow paginated network call).
        """
        import world_bank_data as wbd

        indicators = wbd.get_indicators()  # DataFrame indexed by indicator id
        result: list[dict] = []
        for code, row in indicators.iterrows():
            name = str(row.get("value", code)) if hasattr(row, "get") else str(code)
            category = _category_from_code(str(code), name)
            result.append(self._function_dict(str(code), name, category))
        return result

    def _function_dict(self, code: str, desc: str, category: str) -> dict:
        """Build a standard function dict for one World Bank indicator."""
        return {
            "name": _func_name(code),
            "label": desc,
            "description": f"World Bank (world_bank_data): {desc} (indicator: {code})",
            "category": category,
            "source": "wbdata",
            "frequency": "yearly",
            "parameters": [
                {"name": "country", "type": "str", "required": False,
                 "description": "ISO-2 or ISO-3 country code, list of codes, or 'all' (default: all)"},
                {"name": "date", "type": "str", "required": False,
                 "description": "Year or range, e.g. '2020' or '2015:2023'"},
                {"name": "mrv", "type": "int", "required": False,
                 "description": "Most recent N values (e.g. mrv=1 for latest year)"},
            ],
            "columns": [
                {"name": "country", "type": "str", "description": "Country name", "nullable": False},
                {"name": "country_code", "type": "str", "description": "ISO-3 country code", "nullable": True},
                {"name": "year", "type": "str", "description": "Year", "nullable": False},
                {"name": "value", "type": "float64", "description": desc, "nullable": True},
            ],
        }

    def fetch(self, function_name: str, **params: Any) -> Any:
        """Fetch indicator data via world_bank_data.get_series.

        get_series returns a pd.Series with a MultiIndex (names from the API's
        dimension.id, typically ['country', 'date', 'series']). We reset the
        index into a flat DataFrame and rename columns deterministically.
        """
        import pandas as pd
        import world_bank_data as wbd

        indicator_code = _code_from_func(function_name)

        # Forward recognized params; drop our own metadata keys.
        country = params.get("country")  # None → all countries
        api_params: dict = {}
        for key in ("date", "mrv", "mrnev", "frequency", "source"):
            if key in params and params[key] not in (None, ""):
                api_params[key] = params[key]

        series = wbd.get_series(
            indicator_code,
            country=country,
            id_or_value="value",  # human-readable labels in the index
            simplify_index=False,
            **api_params,
        )

        # Scalar result (zero-dimension request) — wrap as a 1-row DataFrame.
        if not isinstance(series, pd.Series):
            return pd.DataFrame([{
                "country": "all",
                "country_code": None,
                "year": str(api_params.get("date", "")),
                "value": float(series) if series is not None else None,
            }])

        df = series.reset_index()
        df.columns = [str(c) for c in df.columns]

        rename_map: dict[str, str] = {}
        for col in df.columns:
            low = col.lower()
            if low == "country":
                rename_map[col] = "country"
            elif low in ("date", "year", "time"):
                rename_map[col] = "year"
            elif low == "series":
                rename_map[col] = "series"
            elif col == series.name or low == "value":
                rename_map[col] = "value"
        df = df.rename(columns=rename_map)

        # Ensure expected columns exist.
        if "country" not in df.columns:
            df["country"] = None
        if "year" not in df.columns:
            # Some responses use a single date level named differently.
            for cand in ("date", "time"):
                if cand in df.columns:
                    df = df.rename(columns={cand: "year"})
                    break
        if "value" not in df.columns:
            # Last column holding the measurement is the value.
            non_index = [c for c in df.columns if c not in ("country", "year", "series")]
            if non_index:
                df = df.rename(columns={non_index[-1]: "value"})

        # Build a country_code column from the index if a parallel code level
        # is available. get_series(id_or_value='value') returns labels only,
        # so we leave country_code as None unless the caller passed a single
        # country (in which case we can infer it).
        if "country_code" not in df.columns:
            if country and isinstance(country, str) and country != "all":
                df["country_code"] = country.upper()
            else:
                df["country_code"] = None

        keep = [c for c in ("country", "country_code", "year", "value") if c in df.columns]
        return df[keep]

    def columns(self, function_name: str) -> list[dict]:
        """Return standard output columns for the given function."""
        code = _code_from_func(function_name)
        desc = next((d for c, d, _ in KEY_INDICATORS if c == code), code)
        return [
            {"name": "country", "type": "str", "description": "Country name", "nullable": False},
            {"name": "country_code", "type": "str", "description": "ISO-3 country code", "nullable": True},
            {"name": "year", "type": "str", "description": "Year", "nullable": False},
            {"name": "value", "type": "float64", "description": desc, "nullable": True},
        ]
