## Context

The user has a catalog of ~17 A-share / HK-share data needs in `t.md` (沪深日行情、成交概况、行业估值、AH比价、增发配股、大宗交易、股本变动、股权质押、高管持股、分红、港股日行情/基本信息/公司行为、券商研报、盈利预测、主营构成). Today:

- `akshare-mcp` exposes 673+ functions and a `call_akshare_function(name, params_json)` tool, but it only returns records to the caller — it persists nothing.
- `cron-mcp` today schedules **shell-command** tasks: `create_task(name, command)` registers a row in `tasks`, and `create_schedule(name, cron, task)` binds a cron expression to it. The richer `data_job` / `cron_fetch_results` / `create_schedule(data_job=...)` abstraction from the existing `add-cron-mcp-data-fetch` change is **specced but not implemented** (no `cron_data_jobs` / `cron_fetch_results` tables; `schedules.task_name` is still `NOT NULL` with no `data_job_id` column).
- `mcp/daas.db` is the shared database. The project convention for raw fetched data is `scraw_<slug>` tables, introspected by `process-mcp.list_source_tables` (via `sqlite_master`) and queryable by `dashboard-mcp.query_table`. Only `scraw_configs` exists today (empty; oriented to scrapling crawlers).

Constraints: use the **current** MCPs as-is (the user said "use current mcp" and "manually"); `uv` + Python 3.10+; no new runtime dependencies if avoidable; `akshare-mcp` and `cron-mcp` are launched per `.mcp.json` with `uv run --directory mcp/<name>-mcp python server.py`.

## Goals / Non-Goals

**Goals:**
- Map **every** `t.md` data need to a concrete `akshare-mcp` function, in one curated, code-resident catalog.
- Persist each fetched dataset into `mcp/daas.db` as a `scraw_<slug>` table, idempotently.
- Wire a `cron-mcp` schedule per dataset using today's shell-task path, reproducibly and idempotently, while keeping each job a plain inspectable `tasks`+`schedules` row pair (the "manual" wiring the user asked for).
- Keep `akshare-mcp` as the single data gateway (the fetcher calls it via `fastmcp.Client`, not `import akshare`).

**Non-Goals:**
- Implementing the `add-cron-mcp-data-fetch` `data_job` / `cron_fetch_results` abstraction — that is a separate, already-specced change. This change is compatible with it but does not build it.
- Building management UI — the dashboard already reads `scraw_*` via `dashboard-mcp.query_table`.
- LLM extraction or indicator computation on fetched data — `process-mcp` already does this and can consume these `scraw_*` tables as rule source tables.
- Real-time streaming or intraday polling — cron cadence only.
- Backfill orchestration — manual one-shot via `cron-mcp.run_now` is sufficient.

## Decisions

### Decision 1 — Fetcher calls `akshare-mcp` via `fastmcp.Client`, not `import akshare`

`fetch_to_store.py` spawns `akshare-mcp` (using the launch command in `.mcp.json`) and calls its `call_akshare_function` tool via `fastmcp.Client`. The returned records are converted to a DataFrame and upserted.

- **Why**: honors the user's "use akshare-mcp" explicitly; keeps parameter resolution and registry metadata in one place; `akshare-mcp` stays the single data gateway.
- **Alternatives considered**:
  - (a) `import akshare` directly in the fetcher — one process, no MCP handshake, but duplicates the calling logic and bypasses the named gateway. Rejected for now; revisit only if latency matters.
  - (b) Wait for the `data_job` path from `add-cron-mcp-data-fetch` — rejected: not implemented; the user wants data now.
- **Trade-off**: two process spawns per fetch (subprocess + JSON-RPC handshake). Acceptable at daily/weekly/quarterly cadence.

### Decision 2 — Storage is `scraw_<slug>` tables in `mcp/daas.db`, one per dataset

Each catalog entry writes to its own `scraw_<slug>` table. First fetch does `CREATE TABLE IF NOT EXISTS` with columns derived from the DataFrame; subsequent fetches upsert on declared key columns.

- **Why**: matches the project's `scraw_*` convention; queryable by `dashboard-mcp.query_table` and the dashboard; usable as a `process-mcp` rule source table; requires no migration of `schedules`/`tasks`.
- **Alternatives considered**:
  - (a) A single `cron_fetch_results` table with a `data_json` blob (per the unimplemented spec) — rejected: not implemented, and a JSON blob is harder to query than typed columns.
  - (b) The `observations` table — rejected: that stores computed indicator series (date + single value), not multi-column DataFrames.
  - (c) The `process_results` table — rejected: that stores LLM-extracted records, not raw fetches.
- **Upsert keys** are declared per dataset in the catalog (e.g. A股日行情 → `["date","symbol"]`; 大宗交易每日明细 → `["trade_date","symbol","buyer","seller"]`).

### Decision 3 — Catalog is a plain Python module (`datasets.py`), not YAML

`datasets.py` exposes a list of `AkshareDataset` dataclasses. Both `fetch_to_store.py` and `register_cron.py` import it.

- **Why**: no new dependency (`pyyaml` is not currently required by `akshare-mcp`); still human-editable; importable without a parser; no network at import time.
- **Alternatives**: YAML (needs `pyyaml`); JSON (no comments, harder to read for ~17 entries).

### Decision 4 — Cron wiring is an idempotent `register_cron.py` that calls `cron-mcp` tools

`register_cron.py` connects to `cron-mcp` via `fastmcp.Client` and, for each catalog entry, calls `create_task` then `create_schedule`. On a name conflict it **updates** the command/cron rather than failing. It supports `--dry-run`, `--only <name>`, and `--unregister`.

- **Why**: the user wants "manual" wiring but also reproducibility across 17 datasets; idempotency gives both. Each job remains a plain `cron-mcp` row the user can inspect/pause/delete with existing tools.
- **Task command template**: `uv run --directory <repo>/mcp/akshare-mcp python fetch_to_store.py --name <fn> --params '<json>' --table scraw_<slug> --keys <col,col>` (absolute repo path so `cron-mcp` can run it from any CWD).
- **Alternatives considered**:
  - (a) User wires each dataset by hand via `create_task` / `create_schedule` — supported and documented, but tedious for 17 datasets; the helper is optional convenience.
  - (b) One cron-mcp task that loops all datasets — rejected: loses per-dataset cadence and per-dataset pause/inspect.
- **Note**: `register_cron.py` calls `cron-mcp` tools (not direct DB writes) so APScheduler registration and validation go through `cron-mcp` as designed.

### Decision 5 — Per-dataset cadence (cron expressions, `Asia/Shanghai`)

| Dataset group | Cron | Rationale |
|---|---|---|
| A股日行情 / 成交概况 / AH比价 / 大宗交易 / 高管持股 | off-minute weekdays ~16:30–17:30 | after A-share close |
| 港股日行情 / 港股公司行为 | `0 18 * * 1-5` | after HK close |
| 研报 / 盈利预测 / 主营构成 | off-minute weekdays ~18:30 | end of trading day |
| 行业估值 / 增发 / 配股 / 股权质押 | weekly Friday | low intraday churn |
| 股本变动 / 分红 | monthly / quarterly | event-driven, infrequent |

All schedules use `timezone="Asia/Shanghai"` (cron-mcp's `create_schedule` accepts it; default is UTC). Exact off-minute times are staggered across datasets to avoid hammering akshare simultaneously (see Risks).

## Risks / Trade-offs

- **[akshare rate-limiting / IP blocking under repeated cron]** → stagger cron minutes (no two datasets at the same `:00`/`:30`); one fetch per dataset per cadence; rely on `akshare-mcp`'s existing call path.
- **[Two-process spawn per fetch adds latency]** → acceptable at cron cadence; fallback is Decision 1 alt (a) direct `import akshare`.
- **[`scraw_<slug>` schema drift if akshare changes columns]** → fetcher derives columns from the first DataFrame; new columns on later fetches are appended via guarded `ALTER TABLE`; dropped columns are left as NULL. Documented in the fetch-to-store spec.
- **[Catalog of 17 datasets vs. akshare endpoint churn]** → catalog is one Python file; one edit per dataset; a `selfcheck` smoke-tests a couple of live endpoints on demand.
- **[`schedules.task_name` is `NOT NULL`]** → `register_cron.py` always supplies a task name; consistent with today's schema.
- **[cron-mcp `create_schedule` defaults to UTC]** → `register_cron.py` passes `timezone="Asia/Shanghai"` for every entry.
- **[Idempotent upsert requires a unique index on key columns]** → fetcher issues `CREATE UNIQUE INDEX IF NOT EXISTS` on the declared keys after table creation; upsert uses `INSERT ... ON CONFLICT(key,...) DO UPDATE`.

## Migration Plan

- **Deploy**: add `datasets.py`, `fetch_to_store.py`, `register_cron.py` under `mcp/akshare-mcp/`. No DB migration — `scraw_*` tables auto-create on first fetch. Preview with `register_cron.py --dry-run`, then `register_cron.py` to wire. Trigger first fetches via `cron-mcp.run_now` or `register_cron.py --run <name>`.
- **Rollback**: `register_cron.py --unregister` removes the `tasks`+`schedules` rows; `scraw_*` tables can be dropped via `sqlite3 mcp/daas.db "DROP TABLE scraw_<slug>"` (or left in place — they're inert). No code change elsewhere.
- **Future migration to `data_job`**: when `add-cron-mcp-data-fetch` lands, each catalog entry's `name`/`params_json`/`cron` maps directly to `create_data_job(source_mcp="akshare-mcp", tool="call_akshare_function", arguments={"name":..., "params_json":...})` + `create_schedule(data_job=...)`. The `fetch_to_store.py` bridge can then be retired in favor of `cron-mcp`'s built-in fetch+persist; the `scraw_*` tables remain the storage format (or migrate to `cron_fetch_results`).

## Open Questions

- **`scraw_configs` row per dataset?** The `scraw_configs` table (url/name/columns_json) is oriented to scrapling crawlers, and `process-mcp` discovers `scraw_*` via `sqlite_master` directly. Lean: **no** `scraw_configs` row. Revisit if the dashboard's scraw discovery needs it.
- **Fetch provenance log?** `cron-mcp.executions` already records task runs (status, output). A dedicated `akshare_fetch_log` (run_at, dataset, row_count, status) is a possible follow-on; out of scope unless the user wants it.
- **Symbol universe for per-symbol functions** (e.g. `stock_zh_a_hist` needs a `symbol`): the catalog's default `params_json` uses a representative symbol for the smoke test, but a real daily job needs a symbol list. Open: does the user want one task per symbol, or a single task that iterates a watchlist? Lean: single task iterating a watchlist file (`mcp/akshare-mcp/watchlist.txt`), defaulting to a small set, editable. To confirm with the user at apply time.
