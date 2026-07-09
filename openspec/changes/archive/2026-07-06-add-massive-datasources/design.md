## Context

`massive` is already a daas datasource (source id=25, category `Market-Data → Massive`), registered by `seed_external_mcps.py` at the **composable-tool level**: one `default` form with three sections (`Search-Endpoints`, `Call-API`, `Query-Data`) that route to the three `mcp_massive` tools. An agent can discover "Massive.com has a search/call/query tool" but cannot discover *which* data Massive.com exposes or what columns come back — the ~37 REST endpoints across 8 asset classes and their response schemas are not in the registry.

The daas source-based registry has the right layer for this: `daas_functions` (one row per endpoint, `source_id` → `massive`) + `daas_function_columns` (one row per response column). These tables exist and are used by the akshare/yfinance harnesses but are empty for `massive`. Likewise `indicator_rules` exists (72 rules already, over akshare `scraw_*` tables) but has none for Massive. The `scraw_<slug>` table convention and the `indicator_tools` op catalog (`sma`, `ema`, `rsi`, `pct_change`, `zscore`, …) are established.

Constraints:
- The seeder must run in the daas-mcp venv without `massive`/`fastmcp` installed (mirrors `seed_external_mcps.py`'s no-sibling-import rule) → endpoint + column metadata is hard-coded.
- `indicator_rules.source_table` must exist for `run_indicator` to succeed, but `create_indicator` validates the table at creation time → the seeder inserts rules directly (bypassing that validation), so a rule is a contract that becomes runnable once the backfill creates the table.
- The daas-mcp pipeline-bridge cron path is broken (memory: `_cron_call` fails "Connection closed" in the daas-mcp server context; `add_pipeline_item`/`sync_pipeline_cron` silently fail) → the live backfill must NOT use pipeline collections or the daas-mcp server context. A standalone script with its own `fastmcp.Client` is required.
- Real-time Crypto last-trade, Forex last-quote, and Indices-snapshot endpoints return HTTP 403 on the current Massive.com plan → register as metadata, do not backfill, do not create indicators over them.

Stakeholders: agents discovering data via `list_sources`/`search_datasources`; the dashboard `/datasources` view; anyone running `run_indicator` over Economy series.

## Goals / Non-Goals

**Goals:**
- Make Massive.com's per-endpoint catalog + response columns discoverable in the daas registry (so `search_functions` / `get_function_detail` over `massive` returns the endpoints and their columns).
- Make Massive's Economy time-series computable: create `indicator_rules` over Treasury yields / inflation / inflation expectations / labor market, and a backfill that populates the underlying `scraw_massive_*` tables so `run_indicator` produces real `observations` rows.
- Keep the seed hermetic, idempotent, and reversible (`--dry-run` / `--unseed`), matching the `seed_external_mcps.py` contract.

**Non-Goals:**
- Registering every Massive.com endpoint exhaustively (the catalog is sampled from `search_endpoints`; `search_endpoints` returns a curated ~5-result page per query, so the ~37 endpoints are the representative surface, not a complete scrape). More endpoints can be added later by editing the seeder constants.
- Wiring cron for the backfill (daily Treasury-yield refresh etc.) — deferred; cron wiring via direct `cron-mcp` tools is a follow-up.
- Adding Massive endpoints/indicators to a curated collection (`core` or a new `massive-economy` collection) — curation concern, out of scope.
- Fixing the pipeline-bridge cron path — the standalone backfill routes around it; fixing the bridge is a separate change.
- Computing indicators over gated (403) real-time endpoints — no data to compute over.

## Decisions

### D1: Per-endpoint functions + columns, not more forms/sections
Register each Massive.com REST endpoint as a `daas_function` (with `daas_function_columns`) under the existing `massive` source, **not** as additional forms/sections.

- *Why:* forms/sections route an agent to a *tool* (the `default` form's 3 sections already do this for `search_endpoints`/`call_api`/`query_data`). `daas_functions` + `daas_function_columns` document a *data surface's schema* (what columns come back) — exactly what's missing. Reusing forms/sections would lose column-level metadata and conflate "tool routing" with "data schema".
- *Alternative considered:* add a per-endpoint section under a new form with a `call_api path=…` instruction. Rejected: no column metadata; the `default` form already covers `call_api` routing generically.

### D2: Hard-coded, no-network seeder (mirror `seed_external_mcps.py`)
All endpoint metadata (path, query params, response columns, category) is hard-coded Python constants in `seed_massive_endpoints.py`, sampled once via `search_endpoints`/`call_api` during implementation and baked in.

- *Why:* the seeder must run in the daas-mcp venv without `massive`/`fastmcp` installed, must be deterministic, and must be CI-safe. This matches the `seed_external_mcps.py` contract ("no sibling-MCP imports at runtime").
- *Alternative considered:* introspect endpoints live at seed time via `call_api`. Rejected: network dependency, non-deterministic, slow, and would make the seed fail if Massive.com is down or the plan is gated.
- *Drift handling (v1):* none automated. A `--resample` flag that re-fetches columns and reports drift is a follow-up enhancement, not required here.

### D3: `parameters` JSON carries the call_api contract
Each `daas_function.parameters` is a JSON object `{path, method, query_params: [...], gated?: bool}`. `path` keeps `{placeholder}` tokens for path params (e.g. `/v2/aggs/ticker/{stocksTicker}/prev`). An agent (or the backfill helper) reads this to build a `call_api` request deterministically.

- *Why:* the forms/sections routing grammar (`mcp=massive-mcp tool=call_api param=path=<ask-agent>`) is tool-level and generic; the function-level `parameters` JSON gives the *specific* path + params for each endpoint, which is what an agent needs to actually call it.
- *Alternative considered:* encode the path in the function `description`. Rejected: unstructured, not machine-readable.

### D4: Indicator seeder inserts directly into `indicator_rules` (bypass `create_indicator` validation)
The indicator seeder uses a `goc_indicator` helper that inserts directly via the SQLAlchemy session, NOT the `create_indicator` MCP tool.

- *Why:* `create_indicator` validates that `source_table` exists in `sqlite_master` (per the `daas-indicators` spec). The `scraw_massive_<slug>` tables don't exist until the backfill runs. Direct insert lets a rule exist as a contract independent of backfill state — the same property the 72 existing akshare indicator_rules have (they depend on the akshare backfill having run).
- *Risk:* a rule whose table hasn't been backfilled fails at `run_indicator` time with a clear "source table not found" error. Acceptable and documented (run order: seed → backfill → `run_indicator`).
- *Alternative considered:* pre-create empty `scraw_massive_*` tables in the seeder so `create_indicator` validation passes. Rejected: scraw tables are conventionally auto-created on first fetch (schema follows the response); pre-creating them with a guessed schema risks drift.

### D5: Backfill via standalone `fastmcp.Client`, not pipeline collections
`backfill_massive.py` is a standalone script run via `uv run`. It reads the `massive` `leader_upstreams` launch config (or `.mcp.json`), builds a `fastmcp.Client`, calls `call_api` per Economy endpoint, and upserts into `scraw_massive_<slug>` tables (auto-created on first fetch).

- *Why:* the daas-mcp pipeline-bridge cron path is broken (server-context `_cron_call` fails; `add_pipeline_item`/`sync_pipeline_cron` silently fail). A standalone process has no server-context issue and is the simplest reliable path.
- *Alternative considered:* (a) route the backfill through `leader-mcp`'s `call_data_mcp` gateway. Viable but adds a leader-mcp round-trip + dependency; the direct client is more self-contained. (b) Fix the pipeline-bridge and use `pipeline_collections`. Out of scope (separate change).

### D6: `scraw_massive_<slug>` naming + per-endpoint upsert keys
Backfill target tables: `scraw_massive_treasury_yields`, `scraw_massive_inflation`, `scraw_massive_inflation_expectations`, `scraw_massive_labor_market`. Each is auto-created (`CREATE TABLE IF NOT EXISTS`) on first fetch with the response columns. Upsert keys: `(date)` for the daily/monthly time series (natural key); conflict replaces.

- *Why:* mirrors the `scraw_<slug>` convention and the akshare scraw pattern. Date is the natural unique key for these Fed series.

### D7: Indicator ops for Economy series
- **Treasury yields** (daily, back to 1962): `sma(30)`, `ema(20)`, `pct_change`, `zscore(30)`, `rolling_std(30)`, `level` over `yield_1_year`, `yield_5_year`, `yield_10_year` → 18 rules.
- **Inflation** (monthly): `sma(12)`, `pct_change`, `zscore(12)`, `level` → 4+ rules (one set per value column).
- **Inflation expectations** (monthly): `sma(12)`, `pct_change`, `zscore(12)` → 3+ rules.
- **Labor market** (monthly): `sma(12)`, `pct_change`, `zscore(12)`, `level` → 4+ rules.

Total ~30 indicator rules. Each rule: `datasource="massive"`, `function_name=<endpoint>`, `source_table="scraw_massive_<slug>"`, `date_column="date"`, `value_column=<column>`, `indicator_name="<op>_<window>_<column>"`.

### D8: Entitlement-gated endpoints registered as metadata only
The 403-gated endpoints (crypto last-trade, forex last-quote, indices snapshot) are registered as `daas_functions` with `parameters.gated=true` and a description note, so agents discover them but know the current plan is not entitled. They are not backfilled and have no indicators.

## Risks / Trade-offs

- **[403 entitlement]** Real-time crypto/forex/indices endpoints are gated on the current plan. → Register as metadata only; indicators focus on Economy (entitlement-confirmed). The gate is recorded in `parameters.gated` and the function description.
- **[Backfill network dependency]** The backfill helper needs network + the Massive.com session env wired into the `massive` `leader_upstreams` row. → Backfill is a separate, re-runnable step; the seeder (metadata) succeeds without it. Documented run order.
- **[Column drift]** Massive.com may change response schemas; hard-coded columns go stale. → v1 accepts this (re-sample + re-bake during maintenance). A `--resample` drift-report flag is a follow-up.
- **[Indicator rules reference non-existent tables until backfill]** → `run_indicator` returns a clear "source table not found" error; the backfill helper creates+populates the table. Run order documented. Same model as the existing akshare indicator_rules.
- **[Broken pipeline-bridge]** → Standalone backfill script, not pipeline collections. Does not fix the bridge.
- **[Catalog completeness]** `search_endpoints` returns a curated ~5-result page per query, so ~37 endpoints is the representative surface, not an exhaustive scrape. → Documented as a non-goal; more endpoints added by editing seeder constants.

## Migration Plan

1. Run seeder (metadata): `uv run --directory mcp/daas-mcp python seed_massive_endpoints.py` — creates `daas_functions` + `daas_function_columns` + `indicator_rules` (idempotent; safe on live `daas.db`).
2. Run backfill (live, once): `uv run --directory mcp/daas-mcp python backfill_massive.py` — creates + populates `scraw_massive_*` tables for the Economy endpoints. Re-runnable for refresh.
3. Verify: `run_indicator massive_treasury_yields_sma30` writes `observations` rows.
4. Self-check (CI): `uv run --directory mcp/daas-mcp python selfcheck_massive_endpoints.py` (temp DB, no network).

**Rollback:** `uv run --directory mcp/daas-mcp python seed_massive_endpoints.py --unseed` removes only the rows this seeder owns (the `daas_functions` + `daas_function_columns` + `indicator_rules` it created under `massive`). The `massive` source, its `default` form + 3 sections, and the `core` collection item (owned by `seed_external_mcps.py`) are untouched. `scraw_massive_*` tables: dropped by `backfill_massive.py --drop` or `--unseed` with a guard.

## Open Questions

- **Cron for backfill?** Should `backfill_massive.py` register a daily `cron-mcp` schedule (via direct `cron-mcp` tools, per the broken-bridge memory) for Treasury-yield / inflation refreshes? Deferred — the standalone backfill is sufficient for v1; cron wiring is a follow-up.
- **Collection membership?** Should the Economy endpoints join a curated `massive-economy` collection (or the existing `core` collection)? Deferred — curation is a separate concern.
- **Stocks aggregates indicators?** Massive's `/v2/aggs/ticker/{t}/range/...` could compute sma/rsi over US stocks, but the existing 72 akshare indicator_rules already cover US-leaders stocks. Avoid duplication → Massive indicators focus on Economy only. Confirm during implementation.
