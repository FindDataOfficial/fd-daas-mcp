## ADDED Requirements

### Requirement: Seed script registers Massive.com REST endpoints as daas_functions with columns

The system SHALL provide a seed script at `mcp/daas-mcp/seed_massive_endpoints.py` that, when executed against `daas.db`, registers Massive.com's REST API endpoints as `daas_functions` under the existing `massive` source (looked up by `sources.name='massive'`), each with one or more `daas_function_columns` (the endpoint's response columns) and a `parameters` JSON object carrying the `call_api` contract. The seed SHALL cover at minimum the following endpoints, organized by asset-class `daas_functions.category`:

- **Reference** (3): `reference_all_tickers` (`/v3/reference/tickers`), `reference_ticker_types` (`/v3/reference/tickers/types`), `reference_ticker_overview` (`/v3/reference/tickers/{ticker}`)
- **Stocks** (5): `stocks_previous_bar` (`/v2/aggs/ticker/{stocksTicker}/prev`), `stocks_aggregates` (`/v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{from}/{to}`), `stocks_related_companies` (`/v1/related-companies/{ticker}`), `stocks_ticker_events` (`/vX/reference/tickers/{id}/events`), `stocks_market_holidays` (`/v1/marketstatus/upcoming`)
- **Options** (5): `options_chain_snapshot` (`/v3/snapshot/options/{underlyingAsset}`), `options_contract_snapshot` (`/v3/snapshot/options/{underlyingAsset}/{optionContract}`), `options_all_contracts` (`/v3/reference/options/contracts`), `options_contract_overview` (`/v3/reference/options/contracts/{options_ticker}`), `options_last_trade` (`/v2/last/trade/{optionsTicker}`)
- **Crypto** (4): `crypto_last_trade` (`/v1/last/crypto/{from}/{to}`), `crypto_daily_summary` (`/v2/aggs/grouped/locale/global/market/crypto/{date}`), `crypto_previous_bar` (`/v2/aggs/ticker/{cryptoTicker}/prev`), `crypto_daily_open_close` (`/v1/open-close/crypto/{from}/{to}/{date}`)
- **Forex** (4): `forex_last_quote` (`/v1/last_quote/currencies/{from}/{to}`), `forex_previous_bar` (`/v2/aggs/ticker/{forexTicker}/prev`), `forex_daily_summary` (`/v2/aggs/grouped/locale/global/market/fx/{date}`), `forex_conversion` (`/v1/conversion/{from}/{to}`)
- **Futures** (6): `futures_snapshot` (`/futures/v1/snapshot`), `futures_products` (`/futures/v1/products`), `futures_exchanges` (`/futures/v1/exchanges`), `futures_quotes` (`/futures/v1/quotes/{ticker}`), `futures_trades` (`/futures/v1/trades/{ticker}`), `futures_market_status` (`/futures/v1/market-status`)
- **Indices** (4): `indices_snapshot` (`/v3/snapshot/indices`), `indices_previous_bar` (`/v2/aggs/ticker/{indicesTicker}/prev`), `indices_daily_open_close` (`/v1/open-close/{indicesTicker}/{date}`), `indices_market_status` (`/v1/marketstatus/now`)
- **Economy** (4): `economy_treasury_yields` (`/fed/v1/treasury-yields`), `economy_inflation` (`/fed/v1/inflation`), `economy_inflation_expectations` (`/fed/v1/inflation-expectations`), `economy_labor_market` (`/fed/v1/labor-market`)
- **Alternative** (2): `alt_merchant_hierarchy` (`/consumer-spending/eu/v1/merchant-hierarchy`), `alt_merchant_aggregates` (`/consumer-spending/eu/v1/merchant-aggregates`)

#### Scenario: Fresh database receives all endpoint functions and their columns

- **WHEN** the seed script is run against a `daas.db` where the `massive` source exists (created by `seed_external_mcps.py`) but has no `daas_functions` rows
- **THEN** `daas_functions` contains one row per endpoint listed above (at least 37 rows) with `source_id` = the `massive` source's id
- **AND** each `daas_function` has at least one corresponding row in `daas_function_columns` with a non-empty `name`
- **AND** each `daas_function.parameters` is a JSON object whose `path` field is non-empty and matches the endpoint's REST path

#### Scenario: Verified column schemas land on representative endpoints

- **WHEN** the seed has run and the functions `reference_all_tickers`, `stocks_previous_bar`, `options_chain_snapshot`, `economy_treasury_yields`, and `futures_products` are inspected
- **THEN** `reference_all_tickers` has columns including `ticker, name, market, locale, primary_exchange, type, active, currency_name, cik, composite_figi, share_class_figi, last_updated_utc`
- **AND** `stocks_previous_bar` has columns `T, v, vw, o, c, h, l, t_2, n`
- **AND** `options_chain_snapshot` has columns including `details_contract_type, details_expiration_date, details_strike_price, details_ticker, open_interest, underlying_asset_ticker, day_close, day_volume, day_vwap`
- **AND** `economy_treasury_yields` has columns `date, yield_1_year, yield_5_year, yield_10_year`
- **AND** `futures_products` has columns including `asset_sub_class, date, product_code, trade_currency_code, trading_venue, type, unit_of_measure`

#### Scenario: Seed is idempotent across re-runs

- **GIVEN** the seed script has completed successfully once against `daas.db`
- **WHEN** the seed script is invoked a second time with no other writes between runs
- **THEN** the counts of `daas_functions` and `daas_function_columns` rows under the `massive` source are identical before and after the second run
- **AND** the second run's exit status is 0

### Requirement: Entitlement-gated endpoints are marked in metadata

The seed SHALL mark endpoints that return HTTP 403 on the current Massive.com plan by setting `parameters.gated=true` on those `daas_functions` and including a note in the function `description` that the endpoint requires a higher plan. At minimum the 12 endpoints discovered to be gated SHALL be marked: `crypto_last_trade`, `forex_last_quote`, `indices_snapshot`, `options_last_trade`, `forex_conversion`, `futures_snapshot`, `futures_quotes`, `futures_trades`, `indices_previous_bar`, `indices_daily_open_close`, `alt_merchant_hierarchy`, `alt_merchant_aggregates`. These endpoints SHALL be registered (so agents discover them) but SHALL NOT be backfilled and SHALL NOT have indicator_rules.

#### Scenario: Gated endpoints carry the gated flag

- **WHEN** the `daas_functions` rows for the 12 gated endpoints listed above are inspected after seeding
- **THEN** each row's `parameters` JSON has `gated` equal to `true`
- **AND** each row's `description` mentions the entitlement requirement
- **AND** the total count of gated `daas_functions` under the `massive` source is at least 12

### Requirement: Indicator seeder creates indicator_rules over Massive Economy series

The seed script (via a `--seed-indicators` flag or an indicator-seeding section) SHALL create `indicator_rules` rows over the Massive Economy time-series endpoints, inserting directly into `indicator_rules` (bypassing `create_indicator`'s source-table-existence validation, mirroring the seed pattern). Each rule SHALL have `datasource="massive"`, `function_name` equal to the endpoint's daas_function name, `source_table` equal to `scraw_massive_<slug>` (e.g. `scraw_massive_treasury_yields`), `date_column="date"`, a `value_column` drawn from the endpoint's columns, an `op` from the `indicator_tools` catalog with its required `params`, and a unique `name`/`indicator_name`. At minimum:

- **Treasury yields** (`scraw_massive_treasury_yields`): `sma(30)`, `ema(20)`, `pct_change`, `zscore(30)`, `rolling_std(30)`, `level` over `yield_1_year`, `yield_5_year`, `yield_10_year`
- **Inflation** (`scraw_massive_inflation`): `sma(12)`, `pct_change`, `zscore(12)`, `level`
- **Inflation expectations** (`scraw_massive_inflation_expectations`): `sma(12)`, `pct_change`, `zscore(12)`
- **Labor market** (`scraw_massive_labor_market`): `sma(12)`, `pct_change`, `zscore(12)`, `level`

#### Scenario: Indicator rules are created for Economy endpoints

- **WHEN** the seed is run with `--seed-indicators` against a `daas.db` where the `massive` source exists
- **THEN** `indicator_rules` contains at least 25 rows with `datasource="massive"` and `source_table` starting with `scraw_massive_`
- **AND** each such rule's `op` is one of `sma, ema, pct_change, zscore, rolling_std, level`
- **AND** each rule whose `op` requires params (e.g. `sma`, `ema`, `zscore`, `rolling_std`) has those params present in `params_json`

#### Scenario: Indicator rules are idempotent

- **GIVEN** the indicator seeder has run once
- **WHEN** it runs a second time
- **THEN** the count of `indicator_rules` rows with `datasource="massive"` is unchanged
- **AND** no duplicate `name` violation is raised

### Requirement: Backfill helper populates scraw_massive tables via a standalone fastmcp.Client

The system SHALL provide `mcp/daas-mcp/backfill_massive.py` (runnable via `uv run --directory mcp/daas-mcp python backfill_massive.py`) that builds a `fastmcp.Client` against the `massive` `leader_upstreams` launch config (or `.mcp.json`), calls `call_api` for each Massive Economy endpoint, auto-creates the `scraw_massive_<slug>` table on first fetch (`CREATE TABLE IF NOT EXISTS` with the response columns), and upserts rows keyed on `date`. The script SHALL run as a standalone process (not inside the daas-mcp server context) and SHALL NOT use the `pipeline_collections` bridge.

#### Scenario: First backfill creates and populates the treasury-yields table

- **WHEN** `backfill_massive.py` is run against a `daas.db` with no `scraw_massive_treasury_yields` table
- **THEN** the table is created with columns `date, yield_1_year, yield_5_year, yield_10_year`
- **AND** the table contains rows of daily Treasury-yield data
- **AND** `run_indicator` on the `massive` treasury-yields `sma(30)` rule writes `observations` rows with `source="massive"`

#### Scenario: Re-running the backfill upserts without duplicating

- **GIVEN** `scraw_massive_treasury_yields` has been populated once
- **WHEN** `backfill_massive.py` is run a second time
- **THEN** the row count for overlapping `date` keys does not increase (upsert)
- **AND** newer dates, if any, are appended

### Requirement: Seed is no-network, supports --dry-run and --unseed, and leaves the existing massive source intact

The seed script SHALL be executable in the daas-mcp venv without `massive` or `fastmcp` installed (no sibling-MCP imports; all endpoint/column metadata is hard-coded). It SHALL accept `--dry-run` (print the plan, perform no writes) and `--unseed` (remove only the rows this seed owns: the `daas_functions`, `daas_function_columns`, and `indicator_rules` rows it created under `massive`). `--unseed` SHALL NOT delete the `massive` `sources` row, its `default` form, its three sections, or its `core` collection item (those are owned by `seed_external_mcps.py`).

#### Scenario: Seed runs without massive installed

- **GIVEN** the daas-mcp venv has only the daas-mcp dependencies installed
- **WHEN** the seed script is run
- **THEN** all imports resolve and the script completes with exit status 0
- **AND** no `import massive` or `import fastmcp` appears in the seed script's import graph

#### Scenario: --dry-run performs no writes

- **WHEN** the seed script is run with `--dry-run`
- **THEN** a plan is printed listing the `daas_functions`, `daas_function_columns`, and `indicator_rules` that would be created
- **AND** no row is added to `daas_functions`, `daas_function_columns`, or `indicator_rules`

#### Scenario: --unseed removes only endpoint-function and indicator rows

- **GIVEN** the seed has run successfully, populating `daas_functions`/`daas_function_columns`/`indicator_rules` for `massive`
- **WHEN** the seed script is run with `--unseed`
- **THEN** no `daas_functions` rows remain with `source_id` = the `massive` source's id
- **AND** no `indicator_rules` rows remain with `datasource="massive"` that this seed created
- **AND** the `massive` row in `sources` is still present
- **AND** the `massive` `default` form and its three sections (`Search-Endpoints`, `Call-API`, `Query-Data`) are still present
- **AND** the `core` collection still contains a `massive` item

### Requirement: Self-check validates the seeder hermetically

The system SHALL provide `mcp/daas-mcp/selfcheck_massive_endpoints.py` that runs the seeder against a temp DB (no network, no LLM), and asserts: the expected `daas_functions` + `daas_function_columns` are created, the gated endpoints carry `parameters.gated=true`, the indicator rules are created with the correct `source_table` prefix, a second seed run is a no-op, and `--unseed` removes only the owned rows while preserving the `massive` source/form/sections.

#### Scenario: Self-check passes with no network

- **WHEN** `selfcheck_massive_endpoints.py` is run in an environment with no network access
- **THEN** it creates a temp DB, runs the seeder, asserts the expected function/column/indicator counts and shapes, asserts idempotency, asserts `--unseed` cleanup, and exits 0
