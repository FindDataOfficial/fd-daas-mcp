### Requirement: Indicator rule persistence in the shared schema
The server SHALL persist indicator rules in a new `indicator_rules` table added to the shared `mcp/models` `Base`, created in `mcp/daas.db` via `Base.metadata.create_all`. Columns: id, unique `name`, `datasource` (daas `sources.name`, soft reference), `function_name`, `source_table`, `date_column`, `value_column`, `op`, `params_json`, `indicator_name`, `enabled`, `created_at`, `updated_at`. There SHALL be no foreign key to `sources` (soft reference, matching `ProcessRule.datasource`). `indicator_name` SHALL default to the rule `name` when unset.

#### Scenario: indicator_rules table is created on first run
- **WHEN** process-mcp starts against a `daas.db` that lacks `indicator_rules`
- **THEN** `Base.metadata.create_all` creates `indicator_rules` without altering any other table

#### Scenario: deleting an indicator rule does not cascade to observations
- **WHEN** `delete_indicator` removes a rule that has produced `observations` rows
- **THEN** the `indicator_rules` row is removed and no `observations` row is deleted (soft reference; observations rows survive and remain identifiable via their `metadata.rule_name`)

### Requirement: Math operation catalog
The server SHALL expose `list_indicator_ops()` returning a fixed catalog of math operations, each with its required params. The catalog SHALL include at least: `pct_change`, `log_return`, `diff`, `sma` (window), `ema` (span), `rolling_std` (window), `rolling_min` (window), `rolling_max` (window), `rsi` (window), `zscore` (window), `ratio` (other_column), `level` (passthrough). Each op SHALL be a deterministic pandas computation; no op SHALL execute arbitrary user-supplied expressions.

#### Scenario: list_indicator_ops returns the catalog
- **WHEN** `list_indicator_ops()` is called
- **THEN** the result includes each op name with its required params (e.g. `sma` requires `window`, `ratio` requires `other_column`)

#### Scenario: catalog ops are deterministic
- **WHEN** the same source rows and the same op+params are supplied twice
- **THEN** the computed values are identical (no LLM, no randomness)

### Requirement: Indicator rule CRUD tools with validation
The server SHALL expose `create_indicator(name, datasource, source_table, date_column, value_column, op, params?, function_name?, indicator_name?, enabled?)`, `list_indicators()`, `get_indicator(name)`, `update_indicator(name, ...)`, and `delete_indicator(name)`. `create_indicator` SHALL validate: (a) `datasource` exists in daas `sources.name`; (b) `source_table` exists in `sqlite_master` and `date_column`/`value_column` exist in its `PRAGMA table_info`; (c) `op` is in the catalog; (d) the op's required params are present. A failing check SHALL return `{"error": ...}` and create no rule.

#### Scenario: create_indicator validates the source table and columns
- **WHEN** `create_indicator` is called with `source_table="scraw_prices"`, `date_column="date"`, `value_column="close"`, `op="sma"`, `params={"window":5}`
- **THEN** the rule is created and `list_indicators` includes it

#### Scenario: create_indicator rejects a missing datasource
- **WHEN** `create_indicator` is called with `datasource="no_such_source"`
- **THEN** the server returns `{"error": "datasource not found"}` and creates no rule

#### Scenario: create_indicator rejects a missing column
- **WHEN** `create_indicator` is called with a `value_column` not present in the source table
- **THEN** the server returns `{"error": "value_column not found in source table"}` and creates no rule

#### Scenario: create_indicator rejects an unknown op
- **WHEN** `create_indicator` is called with `op="magic"`
- **THEN** the server returns `{"error": "unknown op"}` and creates no rule

#### Scenario: create_indicator rejects a missing required param
- **WHEN** `create_indicator` is called with `op="sma"` and no `window` param
- **THEN** the server returns `{"error": "op 'sma' requires param 'window'"}` and creates no rule

#### Scenario: update_indicator changes only provided fields
- **WHEN** `update_indicator` is called with `name` and `enabled=false`
- **THEN** only `enabled` (and `updated_at`) change; other fields are preserved

### Requirement: run_indicator computes and upserts into observations
The server SHALL expose `run_indicator(name)` that reads the rule's `source_table` (full table, ordered by `date_column`), computes the op over `value_column` with `params`, and upserts each `(date, value)` into the existing daas `observations` table on `(source=datasource, function_name, indicator=indicator_name, date)`, with `value` stored as a string (matching `observations.value`'s `String(64)` type) and `metadata` carrying `{"rule_name","op","params","value_column"}`. The run SHALL be a full recompute (no incremental cursor) and SHALL be idempotent on re-run via the unique constraint. The result SHALL include `rule`, `rows_written`, and `up_to_date: true`.

#### Scenario: run_indicator writes one observation per date
- **WHEN** `run_indicator` is called on an `sma`/`window=5` rule over a 30-row price table
- **THEN** up to 26 `observations` rows are written (5-row warmup yields NaN, which are skipped) with `indicator` equal to the rule's `indicator_name`

#### Scenario: run_indicator is idempotent on re-run
- **WHEN** `run_indicator` is called twice on the same rule with unchanged source data
- **THEN** the `observations` row count does not increase (upsert on the unique constraint) and values are unchanged

#### Scenario: run_indicator skips non-numeric and NaN values
- **WHEN** the source table has a row whose `value_column` is non-numeric or whose computed indicator is NaN (e.g. the warmup window)
- **THEN** no `observations` row is written for that date and no error is raised

#### Scenario: run_indicator records the op in metadata
- **WHEN** `run_indicator` writes a row
- **THEN** the `observations.metadata` JSON includes `rule_name`, `op`, `params`, and `value_column`

### Requirement: Ad-hoc calculate tool
The server SHALL expose `calculate(source_table, date_column, value_column, op, params?, datasource?, function_name?, indicator_name?)` that computes the indicator over the given table without persisting a rule and without writing to `observations`. It SHALL return `{indicator, dates, values, count}`. It SHALL validate the table/columns/op/params as `create_indicator` does.

#### Scenario: calculate returns the series without persisting
- **WHEN** `calculate` is called with `source_table="scraw_prices"`, `op="pct_change"`, `value_column="close"`
- **THEN** the result contains `dates` and `values` arrays of equal length and no `indicator_rules` or `observations` rows are created

#### Scenario: calculate rejects a missing column
- **WHEN** `calculate` is called with a `value_column` not in the table
- **THEN** the server returns `{"error": "value_column not found in source table"}` and performs no computation

### Requirement: SQL-injection guard on dynamic identifiers
Because `source_table`, `date_column`, and `value_column` are interpolated into SQL (they cannot be bind parameters), the server SHALL validate each against `^[A-Za-z_][A-Za-z0-9_]*$` and confirm existence in `sqlite_master` / `PRAGMA table_info` before executing any source-table query. A failing check SHALL return an error and execute no SQL against the source table.

#### Scenario: invalid table name is rejected
- **WHEN** `calculate` or `run_indicator` targets `source_table="scraw_x; DROP TABLE sources;--"`
- **THEN** the server returns `{"error": "invalid source_table identifier"}` and executes no SQL

### Requirement: Cron-driven execution via CLI branch
The server SHALL support a `--run-indicator <name>` CLI argument. When present, the server SHALL run `run_indicator(<name>)` in-process, print a JSON summary to stdout, and exit with code 0 on success or non-zero on failure — without starting the MCP stdio server. A `cron-mcp` `Task.command` of the form `uv run --directory mcp/process-mcp python server.py --run-indicator <name>` SHALL execute the indicator on schedule.

#### Scenario: CLI branch runs an indicator and exits
- **WHEN** `server.py --run-indicator sma5_close` is invoked from a shell
- **THEN** the indicator runs, a JSON summary is printed, and the process exits without starting the stdio server

#### Scenario: cron task command drives the indicator
- **WHEN** a cron-mcp `Task` has `command="uv run --directory mcp/process-mcp python server.py --run-indicator sma5_close"` and a `Schedule` references it
- **THEN** on the schedule, cron-mcp's subprocess runner executes the command and records an `Execution`

### Requirement: observations sink reuses the daas indicator store
Indicator outputs SHALL be written to the existing `observations` table (no new results table) keyed by `(source, function_name, indicator, date)`. The server SHALL NOT create a separate indicator-results table for this purpose.

#### Scenario: indicators land in observations
- **WHEN** `run_indicator` completes for a rule with `datasource="cnstats"`, `function_name="scraw_prices"`, `indicator_name="sma5_close"`
- **THEN** the written rows are visible as `observations` rows with `source="cnstats"`, `function_name="scraw_prices"`, `indicator="sma5_close"`, and are returned by `dashboard-mcp.query_table(database="daas", table="observations")`
