# tiny_econ (fixture)

A tiny fake economic-data library used to evaluate `fd-coding-daas-datasource-builder`.
Do NOT add real network calls - `api.example.com` is intentionally unreachable;
the analyzer is AST-only and never executes the functions.

Functions in `tiny_econ/api.py`:
- `get_cpi_series` - fetcher, **no** CLI -> should be wrapped by sidecar.
- `fetch_gdp_quarterly` - fetcher, **no** CLI -> should be wrapped.
- `list_countries` - fetcher, **no** CLI -> should be wrapped.
- `fetch_holidays` - fetcher, **already** has `@click.command` -> sidecar must SKIP.
- `_normalize` - private helper -> must be EXCLUDED by the analyzer.

Expected sidecar commands: `get-cpi-series`, `fetch-gdp-quarterly`, `list-countries` (3 total).
