# tiny_econ daas skill

Mini skill doc for fetching data from the **tiny_econ** Python data library (a test
fixture; `api.example.com` is unreachable by design). The descriptor
`../daas.descriptor.json` is the source of truth (4 functions, 9 proposed indicators).

> NOTE: tiny_econ is a simulated fixture. In a real onboarding you would call the
> functions to fetch live data; here, only the CLI/import shape is used. Persist
> any real fetched rows into `scraw_<slug>` so indicators can compute over them.

## Install / run

```bash
# from the directory containing daas_cli.py + the tiny_econ package (or its parent)
uv run --with requests --with pandas --with click python daas_cli.py --help
uv run --with requests --with pandas --with click python daas_cli.py get-cpi-series --country CN
```

The sidecar CLI imports `tiny_econ.api` via `importlib` (the original package is
never modified). It wraps the 3 functions that lack an existing CLI;
`fetch_holidays` already has `@click.command` and is intentionally skipped.

## Functions

| command | function | category | frequency | has_existing_cli | output |
|---|---|---|---|---|---|
| `get-cpi-series` | `get_cpi_series` | macro | monthly | no | DataFrame(date, cpi_yoy, country) |
| `fetch-gdp-quarterly` | `fetch_gdp_quarterly` | macro | quarterly | no | DataFrame(date, gdp_current_usd, gdp_growth_yoy, country) |
| `list-countries` | `list_countries` | reference | irregular | no | list[{code, name}] |
| `holidays` (in-package) | `fetch_holidays` | reference | annual | yes | DataFrame(date, market, name) |

## Import shape (direct Python)

```python
from tiny_econ.api import get_cpi_series, fetch_gdp_quarterly, list_countries, fetch_holidays

df_cpi = get_cpi_series(country="CN", start_year=2010, end_year=2024)
df_gdp = fetch_gdp_quarterly(country="US")
countries = list_countries()          # list of {code, name}
df_hol = fetch_holidays(market="US")  # already a click command
```

## Persist to daas.db (scraw_<slug>)

Use the shared upsert helper so indicators can compute over the rows:

```bash
# fetch (in real use) then persist into the scraw table named in the descriptor
uv run python .claude/skills/skill-based-data-fetch/scripts/upsert.py \
  --table scraw_tiny_econ_get_cpi_series \
  --records '{"date":"2024-01-01","cpi_yoy":0.5,"country":"CN"}'
```

The `source_table` for each function's indicators (see `dispatch.json`):
- `get_cpi_series` -> `scraw_tiny_econ_get_cpi_series`
- `fetch_gdp_quarterly` -> `scraw_tiny_econ_fetch_gdp_quarterly`
- `list_countries` -> no time series (reference snapshot, no indicators)
- `fetch_holidays` -> no numeric metrics (no indicators)

## Indicators (proposed, in the descriptor)

9 proposed indicator rules, all `dedup_status: new` (concept already in daas but
exact names new). Metric columns + chosen ops:

- `cpi_yoy` (monthly rate): sma12, pct_change, zscore12
- `gdp_current_usd` (quarterly level): level, pct_change, sma4
- `gdp_growth_yoy` (quarterly rate): sma4, pct_change, zscore4

Compute them with:

```bash
uv run python .claude/skills/skill-based-data-fetch/scripts/run_indicator.py <indicator_name>
```

## Entities

All functions cover `entity_type=country`, identifier = ISO alpha-2 (CN/US/...).
daas already has 60 countries incl. CN/US, so `matched_existing=true` everywhere -
no manual entity linking needed on import.

## Confidence

Source-level confidence is low-ish (~0.43 avg) because tiny_econ is a simulated
fixture with no named upstream bureau (provenance_officialness=0). Docstrings are
good (columns + params listed); frequencies inferable (monthly/quarterly/annual)
but non-official; type hints partial; access is keyless.

## Import the descriptor into daas.db

```bash
python .claude/skills/fd-daas-datasource-builder/scripts/import_descriptor.py daas.descriptor.json
# (add --dry-run to preview)
```
