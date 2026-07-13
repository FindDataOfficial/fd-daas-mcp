"""tiny_econ - tiny fake economic data library (fixture)."""
from .api import get_cpi_series, fetch_gdp_quarterly, list_countries, fetch_holidays

__all__ = ["get_cpi_series", "fetch_gdp_quarterly", "list_countries", "fetch_holidays"]
