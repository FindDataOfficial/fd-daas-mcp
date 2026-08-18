"""tiny_econ.api - data-fetching functions (fixture for fd-coding-daas-datasource-builder)."""
import click
import pandas as pd
import requests

CPI_URL = "https://api.example.com/cpi"
GDP_URL = "https://api.example.com/gdp"
COUNTRIES_URL = "https://api.example.com/countries"
HOLIDAYS_URL = "https://api.example.com/holidays"


def get_cpi_series(country: str = "CN", start_year: int = 2010, end_year: int = 2024):
    """获取 CPI 同比序列数据 (月度)。

    Args:
        country: ISO alpha-2 国家代码, e.g. CN / US.
        start_year: 起始年份.
        end_year: 结束年份.

    Returns:
        DataFrame with columns: date, cpi_yoy, country.
    """
    r = requests.get(CPI_URL, params={"country": country, "start": start_year, "end": end_year})
    return pd.DataFrame(r.json())


def fetch_gdp_quarterly(country: str = "US"):
    """下载季度 GDP 数据。

    Args:
        country: ISO alpha-2 国家代码.

    Returns:
        DataFrame with columns: date, gdp_current_usd, gdp_growth_yoy, country.
    """
    r = requests.get(GDP_URL, params={"country": country, "freq": "Q"})
    return pd.DataFrame(r.json())


def list_countries():
    """列出所有支持的国家代码。

    Returns:
        list of {code, name} dicts.
    """
    r = requests.get(COUNTRIES_URL)
    return r.json()


@click.command("holidays")
@click.option("--market", default="US", help="market code, e.g. US/HK")
def fetch_holidays(market="US"):
    """下载市场假日数据 (年度).

    Returns:
        DataFrame with columns: date, market, name.
    """
    r = requests.get(HOLIDAYS_URL, params={"market": market})
    return pd.DataFrame(r.json())


def _normalize(df):
    """internal helper - not a data fetcher, should be excluded."""
    return df.fillna(0)
