## 1. Schema & dependency

- [x] 1.1 Add `IndicatorRule` model to `mcp/models/models.py` (process-mcp domain): id, unique `name`, `datasource`, `function_name`, `source_table`, `date_column`, `value_column`, `op`, `params_json`, `indicator_name`, `enabled`, `created_at`/`updated_at`. No FK (soft ref to `sources.name`, matching `ProcessRule.datasource`). Add `to_dict()`.
- [x] 1.2 Add `pandas>=2.0` to `mcp/process-mcp/pyproject.toml` `dependencies`; add `indicator_tools` to `[tool.setuptools] py-modules`.
- [x] 1.3 `uv sync` the process-mcp venv; confirm `uv run --directory mcp/process-mcp python -c "import pandas"` succeeds.

## 2. Math operation catalog & compute (indicator_tools.py)

- [x] 2.1 Create `mcp/process-mcp/indicator_tools.py` with the op catalog as a dict: `pct_change`, `log_return`, `diff`, `sma`(window), `ema`(span), `rolling_std`(window), `rolling_min`(window), `rolling_max`(window), `rsi`(window), `zscore`(window), `ratio`(other_column), `level`. Each entry: `{fn: callable(df, value_column, params)->Series, required_params: list[str]}`. Each `fn` a pandas one-liner; NaN for warmup windows.
- [x] 2.2 Implement `list_indicator_ops()` → `{ops: [{name, required_params, description}]}`.
- [x] 2.3 Implement `validate_op(op, params)` → raises `IndicatorError` on unknown op or missing required param; `compute_series(df, value_column, op, params)` → pandas Series.
- [x] 2.4 Implement ad-hoc `calculate(db, source_table, date_column, value_column, op, params=None, datasource=None, function_name=None, indicator_name=None)` → validates table/columns/op/params via the shared guard, reads the series, computes, returns `{indicator, dates, values, count}`. Persists nothing.

## 3. Database layer (process_database.py)

- [x] 3.1 Add `create_indicator(name, datasource, source_table, date_column, value_column, op, params=None, function_name=None, indicator_name=None, enabled=True)`: validate `datasource` exists in `sources.name`; validate `source_table`/`date_column`/`value_column` via `validate_identifier` + `table_exists`/`column_exists`; validate op+params via `indicator_tools.validate_op`; default `indicator_name` to `name`; insert `IndicatorRule`.
- [x] 3.2 Add `list_indicators()`, `get_indicator(name)`, `get_indicator_row(name)`, `update_indicator(name, **fields)` (re-validate changed table/column/op/params), `delete_indicator(name)`.
- [x] 3.3 Add `fetch_indicator_series(source_table, date_column, value_column)` → `[(date, value)]` full-table, ordered by `date_column` (identifiers guarded; bind `rowid`/values).
- [x] 3.4 Add `upsert_observations(source, function_name, indicator, rows, metadata)`: bulk upsert into `observations` on `(source, function_name, indicator, date)`; `value` stored as `str(value)`; `metadata` JSON carries `{rule_name, op, params, value_column}`. Skip NaN/non-numeric.
- [x] 3.5 Add `run_indicator(name)` orchestration: load rule → fetch series → `compute_series` → `upsert_observations` with `source=datasource`, `function_name`, `indicator=indicator_name` → return `{rule, rows_written, up_to_date: true}`.

## 4. Server wiring (server.py)

- [x] 4.1 Register tools: `list_indicator_ops`, `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`, `calculate` (8 tools). Wrap `DbError`/`IndicatorError` → `{"error": ...}`.
- [x] 4.2 Add `--run-indicator <name>` CLI branch mirroring `--run-rule` (run in-process, print JSON summary, exit 0/non-zero, no stdio server). Extend `__main__` arg parsing.
- [x] 4.3 Update the server docstring tool list (11 → 19 tools: 11 LLM + 8 indicator).

## 5. Self-check

- [x] 5.1 Extend `mcp/process-mcp/selfcheck.py`: temp `:memory:` DB; create a `scraw_test` table with a `date` + numeric `close` column; `create_datasource`-equivalent row in `sources`; `create_indicator(op="sma", params={"window":3})`; `run_indicator`; assert `observations` rows written with correct `indicator`, `source`, `function_name`, string `value`, and `metadata.rule_name`. Re-run → assert idempotent (no row growth). Assert `run_rule` path still creates no `observations`.
- [x] 5.2 Run `uv run --directory mcp/process-mcp python selfcheck.py` → green.

## 6. Reference doc & CLAUDE.md

- [x] 6.1 Write `construction/daas-storage.md`: documents `sources` (daas datasources), `daas_functions`→`daas_function_columns` (per-source function + output columns), `datasource_columns` (dashboard legacy, incl. the stale-FK / `sources.id` gotcha), `observations` (indicator store shape + unique key), the `sources` vs `datasources` confusion, and how process-mcp indicators write to `observations`. Self-contained for reuse elsewhere.
- [x] 6.2 Update `CLAUDE.md` `mcp/process-mcp/` section: tool count 11 → 19 (11 LLM + 8 indicator), new `indicator_rules` table, `--run-indicator` cron CLI branch, `observations` sink, `pandas` dep, note that the LLM path (`run_rule`/`extract_*`) still does not touch daas tables.

## 7. Verification

- [x] 7.1 `openspec validate add-process-mcp-indicators --strict` (and `openspec status --change add-process-mcp-indicators`) → all green.
- [x] 7.2 Manual smoke: seeded `scraw_smoke_prices` (6 rows) against the real `mcp/daas.db`, reused the existing `cnstats` datasource, `create_indicator` + `run_indicator` via the process-mcp DB layer (same methods the server tools call). Verified 4 correct SMA(3) `observations` rows landed (121.0/122.0/123.0/124.0, 2-row warmup skipped) via direct `sqlite3` inspection (observations 5313→5317). The `dashboard-mcp.query_table` path could not be demonstrated: the running dashboard-mcp process is pointed at an empty/different database (returns `total:0` for both `sources` and `observations` despite real rows) — a pre-existing session-config issue, not a defect of this change. Smoke data cleaned up (smoke observations/rules/table removed; observations back to 5313).
