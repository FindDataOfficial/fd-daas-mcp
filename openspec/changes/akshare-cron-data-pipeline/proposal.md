## Why

The user maintains a catalog of ~17 A-share / HK-share data needs (`t.md`: 沪深日行情、交易市场成交概况、行业估值、AH比价、增发配股、大宗交易、股本变动、股权质押、高管持股、分红、港股日行情/基本信息/公司行为、券商研报、盈利预测、主营构成). `akshare-mcp` exposes 673+ functions but only returns data to the caller — it does not persist. `cron-mcp` can schedule shell tasks today (`create_task` + `create_schedule(task=...)`) but has no fetcher that bridges `akshare-mcp` → storage, and the richer `data_job` / `cron_fetch_results` abstraction from the existing `add-cron-mcp-data-fetch` change is specced but **not yet implemented**. We need, right now and using only the current MCPs: (1) a curated mapping from each `t.md` need to a concrete `akshare-mcp` function, and (2) a thin fetcher + per-dataset cron wiring so each dataset is fetched on a schedule and stored in `mcp/daas.db` for the dashboard and `process-mcp` to consume.

## What Changes

- **New — akshare dataset catalog**: a curated Python module (`mcp/akshare-mcp/datasets.py`) that maps each `t.md` data need to a concrete `akshare-mcp` function plus default `params_json`, target `scraw_<slug>` storage table, upsert key columns, and a cron cadence. Single source of truth for "which function fetches this data". No new runtime dependency (plain Python dataclasses).
- **New — fetch-to-store bridge**: a script `mcp/akshare-mcp/fetch_to_store.py` that calls `akshare-mcp`'s `call_akshare_function` via `fastmcp.Client` (so `akshare-mcp` remains the single data gateway and parameter-resolution logic stays in one place), converts the returned records to a DataFrame, and upserts them into a `scraw_<slug>` table in `mcp/daas.db` (created on first fetch). CLI: `--name <fn> --params '<json>' --table scraw_<slug> --keys <col,col>`. Idempotent on re-run.
- **New — cron wiring helper**: `mcp/akshare-mcp/register_cron.py` that, for each catalog entry (or one named entry), calls `cron-mcp`'s `create_task` + `create_schedule` idempotently — so the user can wire all datasets with one command, or wire a single dataset by hand. Each dataset becomes a discrete, inspectable `tasks` + `schedules` row pair in `cron-mcp` (the "manual" path the user asked for; no new cron-mcp tools or schema).
- **Docs**: the full `t.md → akshare function` mapping is captured in the catalog module and reproduced in `design.md`.

No **BREAKING** changes. `akshare-mcp` and `cron-mcp` tool surfaces are unchanged — they are consumed as-is.

## Capabilities

### New Capabilities

- `akshare-dataset-catalog`: a curated, code-resident mapping from each `t.md` data need to a concrete `akshare-mcp` function, with default params, target `scraw_<slug>` storage table, upsert keys, and cron cadence. The single source of truth that the fetcher and the cron wiring both read from.
- `akshare-fetch-to-store`: a fetcher bridge that calls `akshare-mcp`'s `call_akshare_function` via `fastmcp.Client` and persists returned records into a `scraw_<slug>` table in `mcp/daas.db` with idempotent upsert, error-recording behavior, and a JSON summary on stdout — suitable for `cron-mcp` shell-task scheduling.
- `akshare-cron-wiring`: per-dataset `cron-mcp` `task` + `schedule` rows that fetch & store each dataset on its cadence, registered through an idempotent helper that issues `create_task` / `create_schedule` (and skips or updates on conflict), so wiring is reproducible while each job remains a plain manual cron-mcp row.

### Modified Capabilities

<!-- None. cron-mcp and akshare-mcp are consumed as-is; no spec-level behavior of an existing capability changes. -->

## Impact

- **New code**: `mcp/akshare-mcp/datasets.py` (catalog), `mcp/akshare-mcp/fetch_to_store.py` (bridge), `mcp/akshare-mcp/register_cron.py` (wiring helper), plus a small `selfcheck`-style smoke test.
- **Storage**: new `scraw_<slug>` tables in `mcp/daas.db` (one per dataset), created on first fetch. Queryable via `dashboard-mcp.query_table(database="daas", table="scraw_*")` and the dashboard; usable as `process-mcp` rule source tables.
- **cron-mcp**: new `tasks` + `schedules` rows only — **no schema change**, no new tools (uses today's shell-task path).
- **akshare-mcp**: unchanged; called as a subprocess MCP server via `fastmcp.Client` using the launch command already in `.mcp.json`.
- **Dependencies**: `fastmcp` (already present), `pandas` (already present). No new dependency (catalog is plain Python, not YAML).
- **Related work**: the existing `add-cron-mcp-data-fetch` change specs a richer `data_job` / `cron_fetch_results` / `create_schedule(data_job=...)` abstraction that is not yet implemented. This change is deliberately compatible with it: each catalog entry maps 1:1 to a future `create_data_job`, and the shell tasks introduced here can migrate to `data_job` bindings once that capability lands. This change does not duplicate that spec — it provides the akshare-specific dataset layer that either path can drive.
