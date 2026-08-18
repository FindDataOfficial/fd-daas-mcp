---
name: fd-daas-based-data-fetch
description: Fetch financial/economic data by resolving an entity + indicator against the daas.db registry via sqlite3, then calling the Python data library (akshare/yfinance/edgar/edinet-tools/dartlab/worldbank/ckan/cnstats) directly and persisting results to scraw_*/observations. Use when the user wants to look up or fetch data for a stock, country, or indicator, or to compute/refresh an indicator. Does NOT use any MCP tool or fd-* CLI.
---

# skill-based-data-fetch

Fetch data the direct way: **sqlite3 on `daas.db`** to resolve what to fetch, **Python data library** to fetch it, **sqlite3** to persist. No MCP server, no `fd-*` CLI, no `mcp__*` tool calls.

## When to use

- "查一下比亚迪在 daas 里有没有 / fetch AAPL close price / get CPI for China"
- "compute the 20-day SMA over scraw_spy_daily / refresh the SPY_rsi14 indicator"
- "save this series to a table"

Do NOT use for: scraping a new website, building a dashboard (use `fd-daas-dashboard-creator`), or creating an entity collection (use `fd-daas-entities-collection-creator`).

## The daas.db location

`daas.db` is a SQLite file at the repo root. Its path comes from `DAAS_DATABASE_URL` in the repo-root `.env` (currently `sqlite:///daas.db`). **Always read it from `.env`** - the scripts in `scripts/` do this automatically; for ad-hoc queries use:

```bash
DB=$(grep -i '^DAAS_DATABASE_URL=' .env | cut -d= -f2- | tr -d '"' | sed 's|sqlite:///||')
sqlite3 "$DB" "SELECT ..."
```

From the repo root, `sqlite3 daas.db "..."` works.

## Step 1 - Resolve the entity + indicator (sqlite3)

Resolve a user entity to its source + `identifier_in_source` + the function/columns to fetch:

```bash
# entity lookup (by name / ticker / code)
sqlite3 daas.db "SELECT id, entity_type, code, name, ticker, exchange, country_code FROM entities WHERE name LIKE '%比亚迪%' OR ticker LIKE '%BYD%' OR code LIKE '%002594%'"

# coverage: which datasource covers this entity + how to fetch it
sqlite3 daas.db "SELECT s.name AS source, l.identifier_in_source, f.name AS function, fc.name AS column_name
  FROM entity_datasource_links l
  JOIN sources s ON s.id = l.source_id
  JOIN daas_functions f ON f.source_id = s.id
  LEFT JOIN daas_function_columns fc ON fc.function_id = f.id
  WHERE l.entity_id = <entity_id>"
```

To find an existing indicator rule:

```bash
sqlite3 daas.db "SELECT name, datasource, source_table, date_column, value_column, op, params_json FROM indicator_rules WHERE name LIKE '%SPY%'"
```

## Step 2 - Fetch by calling the Python library directly

Consult `scripts/dispatch.py` for the exact import + call shape per source prefix. The pattern is always: import the lib, call the function with the resolved params, print JSON. Run it with `uv run python` (add `--python 3.12` for `dartlab`).

```bash
# akshare (A-share daily history)
uv run --with akshare --with pandas python -c "
import akshare as ak, json
df = ak.stock_zh_a_hist(symbol='000001', period='daily', start_date='20250101', end_date='20250201')
print(df.to_json(orient='records', force_ascii=False, date_format='iso'))
"

# yfinance (US/global)
uv run --with yfinance --with pandas python -c "
import yfinance as yf, json
df = yf.Ticker('AAPL').history(period='1mo')
print(df.reset_index().to_json(orient='records', date_format='iso'))
"
```

`scripts/dispatch.py` maps each prefix (`akshare_`, `yfinance_`, `edgar_`, `edinet_`, `dartlab_`, `worldbank_`, `wbdata_`, `ckan_`, `cnstats_`, `massive_`) to its `{import, call_shape, params, output, py_min, env}`. Source-specific auth env: `EDGAR_IDENTITY` (edgar), `EDINET_API_KEY` (edinet document fetch), `MASSIVE_API_KEY` (massive). dartlab and akshare are keyless.

## Step 3 - Persist (sqlite3 via scripts/upsert.py)

Save fetched records into a `scraw_<slug>` table (auto-created, `INSERT OR REPLACE` on the upsert keys):

```bash
uv run --with pandas python scripts/upsert.py --table scraw_my_slug --keys date \
  --records '[{"date":"2025-01-02","Close":"101.0","Volume":"1100"}]'
```

Or upsert a value series into `observations` (keyed on `source, function_name, indicator, date`):

```bash
uv run python scripts/upsert.py --observations \
  '[{"source":"yfinance","function_name":"ticker_history","indicator":"close","date":"2025-01-02","value":"101.0"}]'
```

`upsert.py` backs up `daas.db` to `.bak` before writing and sets `PRAGMA foreign_keys=ON`. **No automatic refresh** - re-run this step manually when you want fresh data.

## Step 4 - Compute indicators (scripts/run_indicator.py)

Compute a deterministic math indicator over a source table and upsert into `observations`:

```bash
# run an existing rule (persisted to observations)
uv run --with pandas --with numpy python scripts/run_indicator.py SPY_ma5

# ad-hoc (no persist, prints the series)
uv run --with pandas --with numpy python scripts/run_indicator.py --calc scraw_spy_daily date Close sma window=5

# list the op catalog
uv run --with pandas --with numpy python scripts/run_indicator.py --list-ops
```

Ops: `sma ema rsi pct_change log_return diff rolling_std rolling_min rolling_max zscore ratio level`. To create a new persistent rule, INSERT into `indicator_rules` via sqlite3 (validate `datasource` exists in `sources`, `source_table`+columns exist, `op` is in the catalog):

```bash
sqlite3 daas.db "INSERT INTO indicator_rules (name, datasource, function_name, source_table, date_column, value_column, op, params_json, indicator_name, enabled) VALUES ('my_ma5','yfinance','scraw_spy_daily','scraw_spy_daily','date','Close','sma','{\"window\":5}','my_ma5',1)"
```

## Hard rules

- **No `mcp__*` tool calls.** No `mcp__daas-mcp__*`, no `mcp__fd-daas-mcp__*`, no `leader_call_data_mcp`.
- **No `fd-*` CLI binaries.** No `fd-akshare`, `fd-yfinance`, `fd-dartlab`, `fd-edgar`, `fd-edinet`, `fd-daas`. No `uv run --directory fd-...`.
- **No `import daas.<source>`.** Call the data library directly (`import akshare`, `import yfinance`, …).
- **Back up before bulk writes.** `upsert.py` / `run_indicator.py` do this automatically; for ad-hoc `sqlite3` writes, `cp daas.db daas.db.bak` first.
- **Validate dynamic identifiers** against `^[A-Za-z_][A-Za-z0-9_]*$` before interpolating table/column names into SQL (the scripts do this; do it for ad-hoc queries too).
