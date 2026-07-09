# Meteostat Datasource MCP — Summary

Built a datasource from the `meteostat` Python library (weather station time
series), wrapped it in a purpose-built MCP server, registered it in a
throwaway daas.db, and mapped its columns to canonical computed indicators.

## Files created

All under `/tmp/fd-dsc-eval/eval3-without/`:

| file | purpose |
|---|---|
| `mcp/meteostat-mcp/server.py` | FastMCP server wrapping the meteostat library — 6 tools (`find_stations`, `get_station`, `get_daily`, `get_hourly`, `get_monthly`, `get_normals`). Purpose-built pattern (like `edgartools-mcp`), not a registry/harness, because meteostat exposes an object/functional model, not a flat function catalog. Lazy imports so the server is importable without `meteostat` installed; tools return a clear error dict per-call if the library is missing. Includes a `--selfcheck` offline path (no network, no meteostat) that passes. |
| `mcp/meteostat-mcp/seed_meteostat.py` | Seeder that bootstraps the throwaway DB via `daas_database.Database` and registers the full datasource: source + categories + form + sections + functions + columns + indicator rules + collection. Idempotent (re-run = 0 new rows); supports `--dry-run`, `--unseed`, `--no-indicators`. |

## Database rows

Throwaway DB at `sqlite:////tmp/fd-dsc-eval/eval3-without/meteostat.db`
(bootstrapped by importing `daas_database.Database` from the real repo, which
runs `Base.metadata.create_all` — all 40 daas tables created). No writes to
the real `mcp/daas.db` or `.mcp.json`.

| table | rows | detail |
|---|---|---|
| `sources` | 1 | `meteostat` source, enabled, category `weather` |
| `categories` | 2 | `environment` (root) → `weather` (child) |
| `datasource_forms` | 1 | `default` form |
| `datasource_sections` | 6 | one per MCP tool, each carrying a routing instruction (`mcp=meteostat-mcp tool=<tool> param=...`) |
| `daas_functions` | 6 | `find_stations`, `get_station`, `get_daily`, `get_hourly`, `get_monthly`, `get_normals` |
| `daas_function_columns` | 54 | all output columns for the 6 functions (6+7+11+12+11+7 = 54) |
| `indicator_rules` | 51 | canonical computed indicators (see below) |
| `datasource_collections` | 1 | `core` collection |
| `datasource_collection_items` | 1 | meteostat added to `core` |

## Canonical indicator mapping approach

The repo has no formal "canonical indicator" table. The closest concepts are:
- `daas_function_columns` (has `name`/`label`/`type`/`description` but no
  `semantic_type` column — only the leader-mcp `function_columns` table has one)
- `indicator_rules` → `observations` — the repo's native indicator mechanism:
  a rule binds a (source_table, value_column) to a math op (sma/ema/pct_change/
  zscore/level/...) and writes computed series into `observations`

I designed a two-layer canonical indicator concept:

**Layer 1 — semantic-type taxonomy.** A `CANONICAL_TYPES` dict in the seeder maps
every raw meteostat column to a canonical semantic type + unit + description:
- `date`/`time`/`month` → date/datetime/month
- `tavg`/`tmin`/`tmax`/`temp` → `temperature` (deg C)
- `dwpt` → `dew_point` (deg C)
- `prcp` → `precipitation` (mm)
- `snow` → `snow_depth` (mm)
- `wdir` → `wind_direction` (deg)
- `wspd` → `wind_speed` (km/h), `wpgt` → `wind_gust` (km/h)
- `pres` → `pressure` (hPa)
- `rhum` → `humidity` (%)
- `tsun` → `sunshine` (min)
- `coco` → `condition_code`

Since `daas_function_columns` has no `semantic_type` column, the canonical type
is embedded in each column's `description` field as `[temperature] Average daily
air temperature` — the bracketed prefix is the canonical semantic type, making it
discoverable via `search_functions` / `get_function_detail`.

**Layer 2 — computed indicator rules.** Following the `seed_massive_endpoints.py`
pattern, `build_indicator_specs()` expands each weather value column through a
per-semantic-type set of math ops into canonical `indicator_name`s:
- Temperature columns (tavg, tmin, tmax, temp) → `sma7`, `sma30`, `pct_change`,
  `zscore30`, `level` (5 indicators each)
- Pressure (pres) → `sma7`, `zscore30`, `level`
- Humidity (rhum) → `sma7`, `zscore30`, `level`
- Precipitation (prcp) → `sma7`, `sma30`, `level`
- Wind speed/gust (wspd, wpgt) → `sma7`, `level`
- Dew point (dwpt) → `sma7`, `level`
- Sunshine (tsun) → `sma7`, `level`
- Snow (snow), wind direction (wdir) → `level` only

Naming: `meteostat_get_daily_sma7_tavg` → `indicator_name = sma7_tavg` (the
canonical label). The 51 rules point at `scraw_meteostat_daily` (28 rules) and
`scraw_meteostat_hourly` (23 rules) tables, which would be populated by a
backfill script (same `scraw_<slug>` convention the repo uses for all scraped
data). When `run_indicator` is called on any rule, it computes the series over
the source table and upserts into `observations` keyed on `(source=meteostat,
function_name=get_daily, indicator=sma7_tavg, date)`.

Indicator breakdown by op: sma=22, level=18, zscore=7, pct_change=4.

## Steps skipped / faked and why

1. **meteostat not installed** — no network access to `pip install meteostat`.
   The MCP server is fully built and importable (lazy imports), and its
   `--selfcheck` passes offline. Live tool calls would work once `meteostat` is
   installed. Not a code gap — the pattern is identical to `edgartools-mcp`
   which also lazy-imports its library.

2. **No live API calls** — meteostat fetches from the Meteostat data portal over
   HTTPS; no network available. The MCP tools are implemented end-to-end (date
   parsing, Point/Station/TimeSeries construction, `.fetch()` → DataFrame →
   serialized JSON) but were not exercised against a live station. No API key is
   needed for the Python library path (unlike edgartools-mcp's `EDGAR_IDENTITY`).

3. **scraw_meteostat_* tables not backfilled** — the 51 `indicator_rules` point
   at `scraw_meteostat_daily` / `scraw_meteostat_hourly` storage tables that
   don't exist yet (they'd be created by a backfill script that calls the MCP's
   `get_daily`/`get_hourly` and upserts rows — same pattern as
   `backfill_massive.py`). The rules are created up-front so an agent can
   discover available indicators before any data is fetched, and `run_indicator`
   would populate `observations` once the source tables exist. This mirrors the
   massive-endpoints design exactly.

4. **No `.mcp.json` entry added** — per the guardrails, the real `.mcp.json` was
   not modified. The MCP server is runnable via
   `python3 /tmp/fd-dsc-eval/eval3-without/mcp/meteostat-mcp/server.py`.

## Verification performed

- MCP server `--selfcheck`: passes (DataFrame serialization with reset_index,
  NaN→None, scalar/list/dict paths, date parsing, meteostat-not-installed guard)
- Seeder: full seed creates all expected rows (verified via sqlite3 queries)
- Idempotency: re-run produces 0 new rows (all get-or-create paths check first)
- `--dry-run`: plans correctly, performs no writes
- `--unseed`: removes all 120 owned rows (2 categories, 1 source, 1 form, 6
  sections, 6 functions, 54 columns, 51 indicators, 1 collection item, 1
  collection); re-seed restores them
