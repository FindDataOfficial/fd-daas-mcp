## Why

`massive` is already a daas datasource (source id=25, `Market-Data → Massive`), but only at the composable-tool level — a single `default` form with three sections (`Search-Endpoints`, `Call-API`, `Query-Data`) that route to the three `mcp_massive` tools. An agent searching daas sees "Massive.com has a search tool" but cannot discover *which* data Massive.com exposes, what columns come back, or compute indicators over its series. The ~37 REST endpoints across 8 asset classes (Stocks, Options, Crypto, Forex, Futures, Indices, Economy, Alternative + Reference) and their response schemas are invisible to the daas registry. This change registers Massive.com's per-endpoint catalog as `daas_functions` + `daas_function_columns` under the existing `massive` source, and creates `indicator_rules` over its time-series endpoints (Treasury yields, inflation, labor market) so agents can discover, fetch, and compute over Massive data the same way they already do over akshare/yfinance.

## What Changes

- **New seeder `mcp/daas-mcp/seed_massive_endpoints.py`** — idempotent, no-network at seed time (hard-coded endpoint + column metadata, sourced from `search_endpoints` / `call_api` sampling). Registers ~37 Massive.com REST endpoints as `daas_functions` under the existing `massive` source, each with `daas_function_columns` (the response columns) and a `parameters` JSON carrying the path template + query params. Endpoints organized by asset-class `category`. `--dry-run` / `--unseed` mirror `seed_external_mcps.py`.
- **Indicator seeder** (same script, `--seed-indicators`, or a `seed_massive_indicators` section) — creates `indicator_rules` over Massive Economy time-series endpoints (Treasury yields, inflation, inflation expectations, labor market), pointing at `scraw_massive_<slug>` source tables. Direct DB inserts (the seed pattern), so rules exist independent of backfill state.
- **Backfill helper `mcp/daas-mcp/backfill_massive.py`** (`--backfill` on the seeder, or standalone) — calls the `massive` upstream via `fastmcp.Client` (standalone process, *not* the daas-mcp server context — avoids the known-broken pipeline-bridge), fetches each Economy endpoint, upserts into `scraw_massive_<slug>` tables. Run once after seeding so `run_indicator` computes real values; re-runnable for refreshes.
- **Self-check `mcp/daas-mcp/selfcheck_massive_endpoints.py`** — temp DB, no network; exercises seeder idempotency, `--unseed`, and indicator-rule shape.
- **No schema changes** — `daas_functions`, `daas_function_columns`, `indicator_rules`, and `scraw_*` tables all exist already.
- **No `.mcp.json` change** — `massive` is already a `leader_upstreams` row reached through `leader-mcp`.

## Capabilities

### New Capabilities
- `massive-endpoint-catalog`: Register Massive.com's per-endpoint REST API as daas `daas_functions` + `daas_function_columns` under the existing `massive` source (organized by asset class), create `indicator_rules` over its Economy time-series endpoints, and provide a standalone backfill helper that populates `scraw_massive_*` tables so indicators compute.

### Modified Capabilities
<!-- None. The existing `external-mcp-datasource-seed` capability (massive source + `default` form) and `daas-indicators` capability (CRUD + `run_indicator` + op catalog) are used as-is, not changed. -->

## Impact

- `mcp/daas-mcp/seed_massive_endpoints.py` (new) — endpoint + indicator seeder, idempotent, `--dry-run` / `--unseed` / `--seed-indicators`.
- `mcp/daas-mcp/backfill_massive.py` (new) — live backfill via `fastmcp.Client` against the `massive` `leader_upstreams` row.
- `mcp/daas-mcp/selfcheck_massive_endpoints.py` (new) — hermetic seeder self-check.
- `mcp/daas.db` (data only) — new `daas_functions` / `daas_function_columns` / `indicator_rules` rows; `scraw_massive_*` tables created on first backfill.
- `construction/mcp.md` + `CLAUDE.md` — document the new seeder, backfill, and self-check.
- Entitlement caveat: real-time Crypto last-trade, Forex last-quote, and Indices snapshot endpoints return HTTP 403 on the current Massive.com plan; they are registered as metadata (so agents discover them) but are not backfilled. Indicators focus on the entitlement-confirmed Economy endpoints.
- No dependencies change; no other MCP is touched; `massive` is called as a client, not modified.
