# daas-skill: tiny_econ

A data-fetch skill for the **tiny_econ** library - a tiny economic-data library
exposing CPI, GDP, country-list, and market-holiday fetchers.

## When to use

Use this skill when an agent needs to fetch macro-economic time series for a
country:

- CPI year-over-year (monthly) -> `get_cpi_series`
- Quarterly GDP (current USD + YoY growth) -> `fetch_gdp_quarterly`
- The list of supported country codes -> `list_countries`
- Market holidays (annual) -> `fetch_holidays` (already has its own Click CLI)

## How it works

1. **Resolve** the country to its ISO alpha-2 code (e.g. CN, US, HK). These
   map 1:1 to `country` entities in daas.db.
2. **Fetch** by calling `tiny_econ.api.<function>(...)` (or the sidecar
   `daas_cli.py <command>` for JSON output). The library hits
   `api.example.com` over `requests` and returns a `pandas.DataFrame` (or a
   list of dicts for `list_countries`).
3. **Persist** the records into a `scraw_tiny_econ_<slug>` table (auto-created
   by the shared upsert helper), then compute proposed indicators (sma /
   pct_change / zscore over the date + numeric column) into `observations`.

## Commands (sidecar CLI)

| Command | Function | Options |
|---|---|---|
| `get-cpi-series` | `get_cpi_series` | `--country` (default CN), `--start-year` (2010), `--end-year` (2024) |
| `fetch-gdp-quarterly` | `fetch_gdp_quarterly` | `--country` (default US) |
| `list-countries` | `list_countries` | (none) |

`fetch_holidays` is **not** wrapped - the original library already exposes it
as `python -m tiny_econ holidays --market US`.

## Output columns

- `get_cpi_series` -> `date, cpi_yoy, country` (monthly)
- `fetch_gdp_quarterly` -> `date, gdp_current_usd, gdp_growth_yoy, country` (quarterly)
- `list_countries` -> `code, name`
- `fetch_holidays` -> `date, market, name` (annual)

## Indicators

For each numeric time-series column, propose `sma` / `pct_change` / `zscore`
over `(date, value)`. CPI and GDP concepts already exist in daas (massive /
wbdata sources); the proposed indicator names are new variants and must not
duplicate existing `indicator_rules.indicator_name` (see `daas.descriptor.json`).

## Caveats

- `api.example.com` is an unreachable fixture endpoint. Live calls will fail;
  this skill is structural (descriptor + dispatch) and is meant to be imported
  into daas.db, not run against the live API.
- Return shapes are inferred from docstrings (AST + docstring analysis only).
