## Context

process-mcp is today an LLM-extraction server: `process_rules` bind a scraped source-data table + text column + JSON Schema + model, and `run_rule` incrementally extracts into `process_results`. Its spec explicitly forbids touching daas registry tables (`sources`, `daas_functions`, `observations`, `datasource_*`) — "traceability only".

daas-mcp already owns the storage model the user wants to build on:

- `sources` — daas datasources (ckan, cnstats, worldbank, edgar, edinet, yfinance, cnreport, hkex, + scraw archives). **Not** `datasources` — that table is a legacy combine-mcp MCP-server registry; the two are unrelated despite the name.
- `daas_functions` → `daas_function_columns` — per-source function + output-column registry (currently unpopulated for the seeded sources).
- `observations` — `(source, function_name, indicator, date, value, metadata)`, unique on `(source, function_name, indicator, date)`. Already holds 5313 rows (e.g. `cnstats_cpi`/`今值`). This is the project's existing indicator store.

The user wants process-mcp to additionally compute **deterministic numeric indicators** (moving averages, returns, volatility, RSI, …) over a datasource's columns and persist them — reusing `observations` rather than a new sink — and wants a standalone reference doc of the daas storage model for reuse elsewhere.

Constraints: shared `mcp/models` Base + single `mcp/daas.db`; `Base.metadata.create_all` for new tables (no Alembic); SQLite `PRAGMA foreign_keys=ON` per connection (process-mcp already does this); dynamic table/column names must pass the `^[A-Za-z_][A-Za-z0-9_]*$` guard + existence check before interpolation (process-mcp already does this for `process_rules`).

## Goals / Non-Goals

**Goals:**
- Add a pandas-backed indicator path to process-mcp: persisted indicator rules + ad-hoc calculate, writing to `observations`.
- Reuse the existing `observations` sink and its unique constraint (idempotent upsert).
- Reuse the existing identifier guard + source-table/column existence checks.
- Ship a `--run-indicator` cron CLI branch mirroring `--run-rule`.
- Ship `construction/daas-storage.md` documenting how daas stores datasources + columns + indicators (incl. `sources` vs `datasources`), for reuse outside this repo.
- Keep the LLM extraction path (`run_rule`/`extract_*`) exactly as-is, including its "does not touch daas tables" guarantee.

**Non-Goals:**
- No general expression/eval engine (no `df.eval` of user formulas in v1). Fixed op catalog only; `formula` is a documented future escape hatch.
- No incremental cursor (`last_rowid`) for indicators. Full recompute per run.
- No reading/writing `daas_function_columns` or `datasource_columns` from process-mcp. The live source data table (validated via `PRAGMA table_info`) is the source of truth for computation; the daas column registries are metadata documented in the reference doc, not read at runtime.
- No new MCP server. Indicators live in process-mcp per the user's request.
- No dashboard/UI changes for indicators in this change (results are queryable via existing `dashboard-mcp.query_table` against `observations`).

## Decisions

### D1: Reuse `observations` as the sink (no new results table)
Indicator results upsert into the existing `observations` table on `(source, function_name, indicator, date)`.

- **Why:** `observations` is already the project's indicator store, already has the right shape + unique constraint, and already holds live data. Reusing it makes indicators immediately queryable via daas-mcp/dashboard-mcp and matches the daas pattern the user pointed at.
- **Alt considered:** a new `process_indicator_results` table. Rejected — duplicates `observations`'s purpose and hides indicators from existing tooling.

### D2: Full recompute per run (no incremental cursor)
`run_indicator` reads the whole source table, computes the series, upserts all rows.

- **Why:** windowed ops (`sma`, `rsi`, `rolling_std`) need lookback; an incremental `last_rowid` cursor (like `process_rules`) would compute wrong leading values for rows whose window straddles the cursor. Idempotent upsert (unique constraint) makes full recompute safe and re-runnable.
- **Alt considered:** incremental cursor + warmup window. Rejected as v1 complexity; full recompute is correct and cheap for scraped-series sizes.
- **Ceiling:** a source table with millions of rows would make per-run full recompute expensive. A `ponytail:` comment names this and points at the incremental-with-warmup upgrade path.

### D3: Fixed math-op catalog (no eval engine)
Ship a fixed set of named ops, each a pandas one-liner: `pct_change`, `log_return`, `diff`, `sma`, `ema`, `rolling_std`, `rolling_min`, `rolling_max`, `rsi`, `zscore`, `ratio`, `level` (passthrough). `list_indicator_ops()` returns the catalog with each op's required params.

- **Why:** safer than `df.eval` on user input, self-documenting, covers the common indicator set. A fixed catalog is trivially testable.
- **Alt considered:** a `formula` op backed by `DataFrame.eval`. Deferred — flexible but a code-injection surface and unnecessary for v1. Documented as a future escape hatch in the reference doc and `list_indicator_ops`.

### D4: One indicator per rule
An `indicator_rule` binds one (op, value_column, params) → one output `indicator_name`. Want SMA-5 and EMA-12? Create two rules.

- **Why:** matches `process_rules`' one-rule-one-binding shape; composable; simple upsert (one row per date).
- **Alt considered:** multi-output rules (op list). Rejected — complicates the table and upsert without real benefit.

### D5: `datasource` + `function_name` are soft string references, no FK
`indicator_rules.datasource` (daas `sources.name`) and `indicator_rules.function_name` are plain strings written through to `observations.source` / `observations.function_name`. No FK to `sources.id`.

- **Why:** matches the existing `ProcessRule.datasource` traceability pattern; `observations.source` is already a plain string; daas sources may be renamed/recreated. Validation confirms the source exists (returns a clear error otherwise) but does not hard-link.
- **Alt considered:** FK to `sources.id`. Rejected — would couple indicator lifecycle to daas source CRUD and break the soft-reference symmetry with `ProcessRule.datasource`.

### D6: Source data table = any table in `daas.db`, validated via PRAGMA
`create_indicator` accepts any `source_table` whose name passes the identifier guard and exists in `sqlite_master` (reusing the `process_rules` validation). `list_source_tables` (scraw_* discovery) is reused for discovery but indicators are not restricted to `scraw_*`.

- **Why:** indicators are most useful on real series tables, which may be `scraw_*` or another table the user created. Restricting to `scraw_*` would be artificial.
- **Alt considered:** restrict to `scraw_*`. Rejected — the validation already guarantees safety; the restriction has no benefit.

### D7: Reference doc at `construction/daas-storage.md`
A standalone Markdown doc explains the daas storage model — `sources`, `daas_functions`/`daas_function_columns`, `datasource_columns` (dashboard legacy, incl. the stale-FK gotcha), `observations`, and the `sources` vs `datasources` confusion — so the user can reuse the logic in another place. Placed in `construction/` (the repo's architecture-docs home, alongside `mcp.md`/`dashboard.md`).

- **Alt considered:** `mcp/daas-mcp/STORAGE.md`. Rejected — `construction/` is where cross-cutting architecture docs live and is where the user said they'd look ("i may use it in another place").

## Risks / Trade-offs

- **[Collides with daas-mcp's own `observations` writes]** → `observations` has no per-writer ownership column; two writers can target the same `(source, function_name, indicator, date)` and upsert over each other. **Mitigation:** the rule owns its `indicator` name; document that users should namespace indicator names (e.g. `sma_5_close`) to avoid stomping daas-native indicators. Idempotent upsert means the only consequence of a collision is last-write-wins, never duplication.

- **[`observations.value` is `String(64)`]** → numeric indicator values are stringified on write (e.g. `"7.1"`), matching existing rows. **Mitigation:** store `str(value)`; the full float is recoverable from the string; `metadata` can carry `{"op","params","value_column"}` for traceability. No schema change to `observations`.

- **[Full recompute cost on large tables]** → a million-row source table re-reads + recomputes every run. **Mitigation:** `ponytail:` ceiling comment in `indicator_tools`; documented upgrade path (incremental cursor + warmup window) in design + reference doc. Not built in v1.

- **[New `pandas` dependency for process-mcp]** → adds install weight to process-mcp's venv. **Mitigation:** pandas is already standard across the ecosystem (daas-mcp, yfinance, akshare); the marginal cost is negligible and pandas is the right tool for windowed math.

- **[Spec modification to `process-mcp-server`'s daas-traceability requirement]** → narrowing a SHALL NOT is a real contract change. **Mitigation:** the MODIFIED requirement keeps the original `run_rule` scenario intact ("no `observations` row is created or modified") and only carves out the new indicator tools; the LLM path's guarantee is preserved verbatim.

## Migration Plan

1. Add `IndicatorRule` to `mcp/models/models.py` (additive table; `Base.metadata.create_all` creates it on next process-mcp start — idempotent, no existing table touched).
2. Add `pandas>=2.0` to `mcp/process-mcp/pyproject.toml`; `uv sync` the process-mcp venv.
3. Implement `indicator_tools.py` + extend `process_database.py` + `server.py` + `selfcheck.py`.
4. Write `construction/daas-storage.md`.
5. Update `CLAUDE.md` `mcp/process-mcp/` section.
6. Rollback: delete the new tools/table — `indicator_rules` is additive and `observations` rows written by indicators are identifiable via `metadata.rule_name` and deletable by that filter. No destructive change to any existing table.

## Open Questions

- Should `list_source_tables` be extended to also list non-`scraw_` tables for indicator targeting, or is a separate `list_tables` helper cleaner? **Lean:** keep `list_source_tables` scraw-only (its contract is documented); add a tiny `list_tables()` helper in the indicator path if needed. Decide in tasks.
- Default `indicator_name` when omitted: rule name, or `f"{op}_{value_column}"`? **Lean:** default to rule name (matches `ProcessRule` naming); `indicator_name` is optional and overrides.
