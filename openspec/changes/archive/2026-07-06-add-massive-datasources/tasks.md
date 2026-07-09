## 1. Catalog sampling (one-time, bake into seeder)

- [x] 1.1 For each non-gated Massive endpoint not yet sampled (stocks_aggregates, stocks_related_companies, stocks_ticker_events, stocks_market_holidays, options_contract_snapshot, options_all_contracts, options_contract_overview, options_last_trade, crypto_daily_summary, crypto_previous_bar, crypto_daily_open_close, forex_previous_bar, forex_daily_summary, forex_conversion, futures_snapshot, futures_exchanges, futures_quotes, futures_trades, futures_market_status, indices_previous_bar, indices_daily_open_close, indices_market_status, economy_inflation, economy_inflation_expectations, economy_labor_market, alt_merchant_hierarchy, alt_merchant_aggregates, reference_ticker_types, reference_ticker_overview), call `massive.call_api` with `store_as` and record the returned column list. Use plausible path params (AAPL/SPY/BTC/USD/EUR/I:SPX) and small `limit` where the endpoint supports it.
- [x] 1.2 For the three gated endpoints (crypto_last_trade, forex_last_quote, indices_snapshot) that return HTTP 403, infer the response columns from the `search_endpoints` description text (e.g. crypto last trade → price, size, timestamp, exchange, conditions) and record them as best-effort column lists.
- [x] 1.3 Assemble the final hard-coded catalog: a Python data structure mapping each of the 37 endpoint names → `{path, method, query_params, category, gated, columns: [{name, label?, type?}]}`. This is the source of truth the seeder reads.

## 2. Seeder skeleton

- [x] 2.1 Create `mcp/daas-mcp/seed_massive_endpoints.py` with the `seed_external_mcps.py` scaffolding: repo-root `dotenv` load, `sys.path` setup, `from daas_database import Database`, `from models import DaasSource, DaasFunction, DaasFunctionColumn, IndicatorRule`, a `Counts` class, an `argparse` entrypoint accepting `--db-url`, `--dry-run`, `--unseed`, `--seed-indicators`.
- [x] 2.2 Add `OWNED_FUNCTION_PREFIX = "massive_"` (or an ownership set derived from the catalog) so `--unseed` deletes exactly the `daas_functions` whose `name` is in the catalog, plus their cascade columns and the `indicator_rules` with `datasource="massive"` this seed created. Confirm cascade FK (`daas_function_columns.function_id` ON DELETE CASCADE) handles columns.

## 3. Endpoint + column seeding

- [x] 3.1 Implement `goc_function(session, source_id, name, label, description, category, parameters, counts, dry_run)` — get-or-create on `(source_id, name)`; update `parameters`/`label`/`description`/`category` if changed.
- [x] 3.2 Implement `goc_column(session, function_id, name, label, type, description, counts, dry_run)` — get-or-create on `(function_id, name)`.
- [x] 3.3 In `seed()`: look up the `massive` source (fail with a clear error pointing to `seed_external_mcps.py` if missing); iterate the catalog; create each `daas_function` + its `daas_function_columns`. Set `parameters.gated=true` and an entitlement-note `description` for the three gated endpoints.

## 4. Indicator seeder

- [x] 4.1 Implement `goc_indicator(session, name, datasource, function_name, source_table, date_column, value_column, op, params, indicator_name, counts, dry_run)` — direct insert into `indicator_rules` on unique `name`; update op/params if changed. Do NOT call `create_indicator` (bypass source-table validation, per D4).
- [x] 4.2 Define the indicator spec list (Treasury yields: sma30/ema20/pct_change/zscore30/rolling_std30/level × {yield_1_year, yield_5_year, yield_10_year}; inflation: sma12/pct_change/zscore12/level; inflation_expectations: sma12/pct_change/zscore12; labor_market: sma12/pct_change/zscore12/level) and the `--seed-indicators` branch that creates them. Rule `name` = `massive_<endpoint>_<op>_<window?>_<column>`; `source_table` = `scraw_massive_<slug>`; `date_column="date"`.
- [x] 4.3 Make `--seed-indicators` run by default (so a bare `python seed_massive_endpoints.py` seeds endpoints + indicators), with `--no-indicators` to skip.

## 5. --unseed

- [x] 5.1 Implement `unseed()`: delete `daas_functions` rows under the `massive` source whose `name` is in the catalog (cascade drops their `daas_function_columns`); delete `indicator_rules` rows with `datasource="massive"` whose `name` this seed owns. Do NOT touch the `massive` `sources` row, its `default` form, its 3 sections, or its `core` collection item. Guard with the ownership prefix/set.

## 6. Self-check

- [x] 6.1 Create `mcp/daas-mcp/selfcheck_massive_endpoints.py`: temp DB via `Database` with a `DAAS_DATABASE_URL` override to a temp file; pre-create the `massive` source + `default` form + 3 sections (mirroring `seed_external_mcps.py` minimal); run the seeder; assert ≥37 `daas_functions`, each with ≥1 column; assert the 5 representative endpoints have the verified column sets; assert the 3 gated endpoints have `parameters.gated=true`; assert ≥25 `indicator_rules` with `datasource="massive"` and `source_table` LIKE `scraw_massive_%`; assert a second seed run is a no-op; assert `--unseed` removes owned rows and leaves the `massive` source/form/sections. Exit 0.
- [x] 6.2 Run it: `uv run --directory mcp/daas-mcp python selfcheck_massive_endpoints.py` — passes with no network.

## 7. Backfill helper

- [x] 7.1 Create `mcp/daas-mcp/backfill_massive.py`: load the `massive` `leader_upstreams` row from `daas.db` (or fall back to `.mcp.json`); build a `fastmcp.Client` (stdio) using its `command`/`args_json`/`env_json`/`cwd`; for each Economy endpoint (`economy_treasury_yields`, `economy_inflation`, `economy_inflation_expectations`, `economy_labor_market`) call `call_api` with `store_as` then `query_data DESCRIBE` (or read the `call_api` column header) to get columns; `CREATE TABLE IF NOT EXISTS scraw_massive_<slug> (...)`; `INSERT ... ON CONFLICT(date) DO UPDATE` upsert the rows. Standalone process — no daas-mcp server-context imports.
- [x] 7.2 Add a `--drop` flag that drops the `scraw_massive_*` tables (for reset), and a `--only <slug>` filter for one endpoint.
- [x] 7.3 Run it once against live `daas.db`: `uv run --directory mcp/daas-mcp python backfill_massive.py` — creates + populates `scraw_massive_treasury_yields` (and the others). Verify row counts via `sqlite3 mcp/daas.db "SELECT COUNT(*) FROM scraw_massive_treasury_yields;"`.

## 8. Live verification

- [x] 8.1 Run the seeder on live `daas.db`: `uv run --directory mcp/daas-mcp python seed_massive_endpoints.py` (then `--dry-run` re-run is a no-op on counts).
- [x] 8.2 Spot-check via `sqlite3 mcp/daas.db`: `SELECT COUNT(*) FROM daas_functions WHERE source_id=(SELECT id FROM sources WHERE name='massive');` (≥37); `SELECT COUNT(*) FROM daas_function_columns WHERE function_id IN (SELECT id FROM daas_functions WHERE source_id=(SELECT id FROM sources WHERE name='massive'));` (>0); `SELECT COUNT(*) FROM indicator_rules WHERE datasource='massive';` (≥25).
- [x] 8.3 Run an indicator: `uv run --directory mcp/daas-mcp python server.py --run-indicator massive_treasury_yields_sma30_yield_10_year` (adjust to the actual rule name) — verify it writes `observations` rows with `source="massive"`: `sqlite3 mcp/daas.db "SELECT COUNT(*) FROM observations WHERE source='massive';"`.
- [x] 8.4 Verify the `massive` source's pre-existing `default` form + 3 sections + `core` collection item are unchanged (re-run `seed_external_mcps.py --dry-run` is a no-op).

## 9. Docs

- [x] 9.1 Update `construction/mcp.md` daas-mcp section: document `seed_massive_endpoints.py` (37 endpoints + columns, `--seed-indicators`, `--dry-run`/`--unseed`), `backfill_massive.py` (standalone `fastmcp.Client` → `scraw_massive_*`), and `selfcheck_massive_endpoints.py`.
- [x] 9.2 Update `CLAUDE.md` daas-mcp section with the same three new files + run commands, mirroring the `seed_external_mcps.py` / `seed_pipeline_from_mapping.py` documentation style.
- [x] 9.3 Note the entitlement caveat (crypto/forex/indices real-time gated) and the run order (seed → backfill → `run_indicator`) in both docs.
