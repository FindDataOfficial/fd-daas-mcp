"""dispatch.py - source-prefix -> Python call-shape table for skill-based-data-fetch.

The skill consults this table to construct the correct `uv run python -c "..."`
snippet for a given `<source>_<func>` name. It is a REFERENCE table (import +
call shape + params + example), not a full adapter - the agent reads the entry
and writes the snippet. Per-source quirks (cnstats name-mapping, worldbank
indicator-code conversion) are documented in `notes`/`example`.

Shapes are sourced from the fd-world adapters (akshare/worldbank/cnstats/ckan/
wbdata) and the single-source harnesses (fd-dartlab/fd-edgar/fd-edinet/fd-yfinance).

Usage:
  python dispatch.py                       # list all sources
  python dispatch.py --source akshare      # show one entry
  python dispatch.py --resolve akshare_stock_zh_a_hist   # resolve prefix -> entry
"""
from __future__ import annotations

import json
import sys

# Each entry: how to call the Python library directly for a `<prefix>_<func>` name.
DISPATCH: dict[str, dict] = {
    "akshare_": {
        "source": "akshare",
        "pypi": "akshare",
        "import": "import akshare as ak",
        "call_shape": "ak.<func>(**params)  # <func> = name with 'akshare_' stripped",
        "params": "per-function (e.g. symbol, period, start_date, end_date)",
        "output": "pandas.DataFrame",
        "py_min": "3.10",
        "env": [],
        "example": (
            "uv run --with akshare --with pandas python -c \"\n"
            "import akshare as ak, json\n"
            "df = ak.stock_zh_a_hist(symbol='000001', period='daily', start_date='20250101')\n"
            "print(df.to_json(orient='records', force_ascii=False, date_format='iso'))\n"
            "\""
        ),
        "notes": "Keyless. 673+ functions. Strip the 'akshare_' prefix to get the akshare function name.",
    },
    "yfinance_": {
        "source": "yfinance",
        "pypi": "yfinance",
        "import": "import yfinance as yf",
        "call_shape": (
            "ticker_<method> -> yf.Ticker(symbol).<method>(...);  "
            "top-level (download, search) -> yf.<name>(...)"
        ),
        "params": "symbol (required for ticker_*), plus method-specific",
        "output": "pandas.DataFrame",
        "py_min": "3.10",
        "env": [],
        "example": (
            "uv run --with yfinance --with pandas python -c \"\n"
            "import yfinance as yf, json\n"
            "df = yf.Ticker('AAPL').history(period='1mo')\n"
            "print(df.reset_index().to_json(orient='records', date_format='iso'))\n"
            "\""
        ),
        "notes": "Keyless. Global/US market data. ticker_history -> Ticker(symbol).history(...).",
    },
    "dartlab_": {
        "source": "dartlab",
        "pypi": "dartlab",
        "import": "import dartlab",
        "call_shape": (
            "dartlab_company_panel -> dartlab.Company(ticker).panel();  "
            "dartlab_get_credit -> .credit();  dartlab_analyze -> .analysis();  "
            "dartlab_scan -> dartlab.scan(...)"
        ),
        "params": "ticker (required)",
        "output": "pandas.DataFrame",
        "py_min": "3.12",
        "env": [],
        "example": (
            "uv run --python 3.12 --with dartlab --with pandas python -c \"\n"
            "import dartlab, json\n"
            "df = dartlab.Company('005930').panel()\n"
            "print(df.to_json(orient='records', date_format='iso'))\n"
            "\""
        ),
        "notes": "Keyless (auto-downloads pre-built parquet from HuggingFace). Korea DART + US EDGAR. Python >=3.12 floor - use `uv run --python 3.12`.",
    },
    "edgar_": {
        "source": "edgar",
        "pypi": "edgar",
        "import": "import edgar",
        "call_shape": (
            "edgar_get_company -> edgar.Company(ticker);  "
            "edgar_list_filings -> edgar.get_filings(...);  "
            "edgar_get_filing -> edgar.Filing(filing_id);  "
            "edgar_get_financials -> Company(ticker).financials;  "
            "edgar_get_insider_trades -> edgar.get_insider_trades(...)"
        ),
        "params": "ticker / filing_id / form etc.",
        "output": "object or pandas.DataFrame",
        "py_min": "3.10",
        "env": ["EDGAR_IDENTITY"],
        "example": (
            "EDGAR_IDENTITY='Name email@domain' uv run --with edgar --with pandas python -c \"\n"
            "import edgar, json\n"
            "edgar.set_identity()\n"
            "fin = edgar.Company('AAPL').financials\n"
            "print(json.dumps({'income': str(fin.income_statement)[:500]}))\n"
            "\""
        ),
        "notes": "Requires EDGAR_IDENTITY (descriptive SEC User-Agent). Call edgar.set_identity() first.",
    },
    "edinet_": {
        "source": "edinet",
        "pypi": "edinet-tools",
        "import": "import edinet_tools",
        "call_shape": (
            "edinet_search_entities -> edinet_tools search;  "
            "edinet_get_entity -> edinet_tools.Entity(code);  "
            "edinet_list_documents -> Entity(code).documents;  "
            "edinet_get_document -> Document(...);  edinet_supported_doc_types -> catalog"
        ),
        "params": "code (EDINET entity code, e.g. E01225) / document_id",
        "output": "object or pandas.DataFrame",
        "py_min": "3.10",
        "env": ["EDINET_API_KEY"],
        "example": (
            "uv run --with edinet-tools --with pandas python -c \"\n"
            "import edinet_tools as et, json\n"
            "ent = et.Entity('E01225')\n"
            "print(json.dumps({'name': ent.name}))\n"
            "\""
        ),
        "notes": "EDINET_API_KEY required ONLY for edinet_list_documents/edinet_get_document (document fetching). search_entities/get_entity/supported_doc_types are keyless.",
    },
    "worldbank_": {
        "source": "worldbank",
        "pypi": "requests",
        "import": "import requests",
        "call_shape": (
            "requests.get(f'https://api.worldbank.org/v2/country/{country}/indicator/{code}', "
            "params={'format':'json','per_page':1000,'date':time})  "
            "# code = func name uppercased with _ -> . (worldbank_ny_gdp_mktp_cd -> NY.GDP.MKTP.CD)"
        ),
        "params": "country (ISO-3 or 'all', default 'all'), time (e.g. '2015:2023')",
        "output": "pandas.DataFrame [country, iso3, year, value]",
        "py_min": "3.10",
        "env": [],
        "example": (
            "uv run --with requests --with pandas python -c \"\n"
            "import requests, pandas as pd, json\n"
            "r = requests.get('https://api.worldbank.org/v2/country/CHN/indicator/NY.GDP.MKTP.CD',\n"
            "                  params={'format':'json','per_page':1000,'date':'2015:2023'}, timeout=30)\n"
            "data = r.json()\n"
            "rows = [{'country':i.get('country',{}).get('value',''),'iso3':i.get('countryiso3code',''),"
            "'year':i.get('date',''),'value':i.get('value')} for i in (data[1] if len(data)>1 else []) if i.get('value') is not None]\n"
            "print(pd.DataFrame(rows).to_json(orient='records'))\n"
            "\""
        ),
        "notes": "Uses the World Bank REST API directly (NOT wbgapi). Convert func name to indicator code: uppercase, replace '_' with '.'. Keyless.",
    },
    "wbdata_": {
        "source": "wbdata",
        "pypi": "world_bank_data",
        "import": "import world_bank_data as wbd",
        "call_shape": (
            "wbd.get_series(code, country=..., id_or_value='value', simplify_index=False, "
            "**{date/mrv/mrnev})  # code = func name uppercased with _ -> ."
        ),
        "params": "country (ISO-2/3 or 'all'), date (e.g. '2020' or '2015:2023'), mrv (most recent N)",
        "output": "pandas.DataFrame [country, country_code, year, value]",
        "py_min": "3.10",
        "env": [],
        "example": (
            "uv run --with world_bank_data --with pandas python -c \"\n"
            "import world_bank_data as wbd, pandas as pd, json\n"
            "s = wbd.get_series('NY.GDP.MKTP.CD', country='CHN', id_or_value='value', simplify_index=False)\n"
            "df = s.reset_index(); df.columns=[str(c) for c in df.columns]\n"
            "print(df.to_json(orient='records'))\n"
            "\""
        ),
        "notes": "world_bank_data package. Returns a MultiIndex Series; reset_index + rename to [country, year, value]. Convert func name to indicator code: uppercase, '_' -> '.'.",
    },
    "cnstats_": {
        "source": "cnstats",
        "pypi": "akshare",
        "import": "import akshare as ak",
        "call_shape": "ak.<mapped_func>()  # see notes for the cnstats -> akshare macro mapping",
        "params": "most take none (return monthly/quarterly series)",
        "output": "pandas.DataFrame",
        "py_min": "3.10",
        "env": [],
        "example": (
            "uv run --with akshare --with pandas python -c \"\n"
            "import akshare as ak, json\n"
            "df = ak.macro_china_cpi_yearly()\n"
            "print(df.to_json(orient='records', force_ascii=False, date_format='iso'))\n"
            "\""
        ),
        "notes": (
            "Uses akshare macro functions (NOT a separate cnstats lib). Mapping: "
            "cpi->macro_china_cpi_yearly, pmi->macro_china_pmi, "
            "industrial_output->macro_china_industrial_production_yoy, "
            "fixed_asset_investment->macro_china_fixed_asset_investment, "
            "retail_sales->macro_china_consumer_goods_retail, "
            "gdp_quarterly->macro_china_gdp_yearly, trade_balance->macro_china_trade_balance, "
            "money_supply->macro_china_money_supply. Keyless (via akshare)."
        ),
    },
    "ckan_": {
        "source": "ckan",
        "pypi": "ckanapi",
        "import": "import ckanapi",
        "call_shape": (
            "ckanapi.RemoteCKAN(portal).action.<package_search|package_show|resource_show|"
            "organization_list|tag_list>(**params)"
        ),
        "params": "q/rows (search), id (show), query (tag_list); portal default https://data.gov/api/3/",
        "output": "pandas.DataFrame",
        "py_min": "3.10",
        "env": [],
        "example": (
            "uv run --with ckanapi --with pandas python -c \"\n"
            "import ckanapi, pandas as pd, json\n"
            "client = ckanapi.RemoteCKAN('https://data.gov/api/3/')\n"
            "res = client.action.package_search(q='climate', rows=10)\n"
            "rows = [{'title':d.get('title',''),'name':d.get('name',''),'resources':len(d.get('resources',[]))} for d in res.get('results',[])]\n"
            "print(pd.DataFrame(rows).to_json(orient='records'))\n"
            "\""
        ),
        "notes": "portal_url configurable (default data.gov). Functions: package_search, package_show, resource_show, organization_list, tag_list.",
    },
}


def resolve(function_name: str) -> dict | None:
    """Return the dispatch entry for a `<source>_<func>` name, or None."""
    for prefix, entry in DISPATCH.items():
        if function_name.startswith(prefix):
            return {"prefix": prefix, **entry}
    return None


def list_sources() -> list[dict]:
    """Return a compact list of all source entries."""
    return [
        {
            "prefix": p,
            "source": e["source"],
            "pypi": e["pypi"],
            "py_min": e["py_min"],
            "env": e["env"],
            "call_shape": e["call_shape"],
        }
        for p, e in DISPATCH.items()
    ]


def main(argv: list[str]) -> int:
    if not argv:
        print(json.dumps(list_sources(), ensure_ascii=False, indent=2))
        return 0
    if argv[0] == "--source" and len(argv) > 1:
        entry = DISPATCH.get(argv[1] if argv[1].endswith("_") else argv[1] + "_")
        print(json.dumps(entry or {"error": f"unknown source: {argv[1]}"}, ensure_ascii=False, indent=2))
        return 0 if entry else 2
    if argv[0] == "--resolve" and len(argv) > 1:
        print(json.dumps(resolve(argv[1]) or {"error": f"no dispatch for: {argv[1]}"}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"error": "usage: [--source <name>] | [--resolve <func>]"}))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
