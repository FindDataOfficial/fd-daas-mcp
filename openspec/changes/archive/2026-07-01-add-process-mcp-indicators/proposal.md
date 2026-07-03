## Why

process-mcp today only extracts via LLM (`process_rules` → `process_results`); it cannot compute deterministic numeric indicators (moving averages, returns, volatility, RSI, …) over a datasource's columns, and it is explicitly forbidden from writing to the daas `observations` indicator store. daas-mcp already defines the storage model the user wants to build on — datasources in `sources`, per-function output columns in `daas_function_columns`, and an `observations` table keyed `(source, function_name, indicator, date, value)` that already holds 5313 rows (e.g. `cnstats_cpi`/`今值`). This change adds a pandas-backed indicator path to process-mcp that reads a source data table's columns, applies a fixed catalog of math operations, and writes the resulting series into `observations` — reusing the daas indicator pattern instead of inventing a new sink. It also ships a standalone reference doc of that daas storage model so the user can reuse it elsewhere.

## What Changes

- New **indicator rule** unit in process-mcp: a persisted binding of (daas `datasource` name, source data table, date column, value column, math op, op params, output indicator name) — mirrors the `process_rules` one-rule-one-binding shape.
- New **math operation catalog** (pandas one-liners): `pct_change`, `log_return`, `diff`, `sma`, `ema`, `rolling_std`, `rolling_min`, `rolling_max`, `rsi`, `zscore`, `ratio`, `level` (passthrough). `list_indicator_ops()` returns the catalog.
- **Persisted path**: `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`.
- **Ad-hoc path**: `calculate(table, date_column, value_column, op, params?)` computes without persisting (mirrors `extract_text`).
- **Sink**: `run_indicator` and `calculate` upsert results into the existing daas `observations` table on `(source, function_name, indicator, date)`. No new results table.
- **Cron**: `python server.py --run-indicator <name>` CLI branch mirrors `--run-rule`; wireable via cron-mcp `Task.command`.
- **Full recompute per run** (indicators are windowed → incremental cursors produce wrong leading values); idempotent upsert makes this safe. A `ponytail:` comment names the ceiling and the incremental upgrade path.
- New shared-schema table `indicator_rules` (additive; `Base.metadata.create_all`, no Alembic).
- New reference doc `construction/daas-storage.md` documenting how daas-mcp stores datasources + columns + indicators (incl. the `sources` vs `datasources` gotcha), for reuse outside this repo.
- **One new dependency**: `pandas>=2.0` added to `mcp/process-mcp/pyproject.toml` (process-mcp today has no pandas; daas-mcp/yfinance already use it). `numpy` comes transitively via pandas. No `.mcp.json` change. Other MCP servers untouched.

## Capabilities

### New Capabilities
- `process-mcp-indicators`: Deterministic math indicators over a datasource's columns — persisted indicator rules (create / list / get / update / delete / run), an ad-hoc `calculate` tool, a fixed math-op catalog (`list_indicator_ops`), results upserted into the daas `observations` table, and a `--run-indicator` cron CLI branch.

### Modified Capabilities
- `process-mcp-server`: The "daas integration is traceability only" requirement is **narrowed in scope** — it now applies to the LLM extraction path only (`create_rule`/`run_rule`/`extract_*` SHALL NOT touch daas tables). The new indicator tools are explicitly exempted and SHALL write to `observations`. The `run_rule` scenario ("no `observations` row is created or modified") is retained for the LLM path.

## Impact

- `mcp/models/models.py`: +1 table `IndicatorRule` (name unique, datasource, function_name, source_table, date_column, value_column, op, params_json, indicator_name, enabled, timestamps). No FK (daas `sources.name` is a soft reference, matching the existing `ProcessRule.datasource` traceability pattern).
- `mcp/process-mcp/`: new `indicator_tools.py` (op catalog + pandas compute + ad-hoc `calculate`); extend `process_database.py` (`IndicatorRule` CRUD, source-table/column validation reuse, `observations` upsert); extend `server.py` (6 new tools + `--run-indicator` CLI branch); update `selfcheck.py` (temp-DB indicator round-trip, no network).
- `mcp/process-mcp/pyproject.toml`: +1 dependency (`pandas>=2.0`); `indicator_tools` added to `py-modules`.
- `mcp/daas.db`: `indicator_rules` auto-created via `Base.metadata.create_all`; writes to existing `observations` (no schema change to it).
- `construction/daas-storage.md`: new reference doc.
- `CLAUDE.md`: extend the `mcp/process-mcp/` section (tool count 11 → 18, new table, `--run-indicator` branch, `observations` sink, pandas dep).
- No `.mcp.json` change. No other MCP server modified.
