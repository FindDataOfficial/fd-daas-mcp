## Context

cron-mcp is a FastMCP stdio server (`mcp/cron-mcp/server.py`) wrapping APScheduler. A `Schedule` row (cron_expr + `task_name`) becomes an APScheduler job that calls `execute_task(schedule_id)`. `execute_task` resolves the task name to either a DB `Task` (run `command` as a shell subprocess) or a built-in registry callable, and writes an `Execution` row (`status`, `output` Text). All cron-mcp tables live in the shared schema package `mcp/models/models.py` and the shared DB `mcp/daas.db`.

The project already runs ~15 MCP servers, each registered in `.mcp.json` as `{command, args, cwd, env}` (stdio) entries. `composite-mcp` already connects to those servers as a client: `composite_database.build_client(upstream)` returns a `fastmcp.Client` over a stdio transport, and `client.call_tool(name, args)` / `client.list_tools()` do the work (see `composite_tools.make_chain_tool`). cron-mcp already depends on `fastmcp>=3.4.2` and `mcp>=1.28.0`, so the client primitives are available with no new dependency.

Constraints (from CLAUDE.md / `construction/mcp.md`): schema changes go in `mcp/models/models.py` first; SQLite is the DB; `Base.metadata.create_all` creates new tables; column additions to existing tables use guarded idempotent `ALTER TABLE` (the `daas-mcp` `_migrate_sources_category_id` precedent) — no Alembic.

## Goals / Non-Goals

**Goals:**
- Fetch structured data from any MCP server listed in `.mcp.json`, by tool name + arguments.
- Do it **manually** (one-shot, no setup; or run a saved definition) **and** **automatically** (on a cron schedule).
- Persist every fetch's result + status so it can be queried later.
- Reuse the existing schedule/execution machinery — a scheduled data fetch is just another kind of schedule.

**Non-Goals:**
- No multi-step pipelines across MCPs (that is `composite-mcp`'s chains).
- No persistent client connection pooling — a client is spawned per fetch.
- No file offload for large payloads — results live in a JSON column.
- No new MCP server, no new `.mcp.json` entry, no changes to other MCPs.
- No `update_data_job`-style ergonomics beyond what prevents dangling schedules (the one update path that exists is to avoid silently breaking a bound schedule).

## Decisions

### D1. Call other MCPs as a `fastmcp.Client`, transport built from `.mcp.json`
cron-mcp reads `.mcp.json` (repo root) and builds a `fastmcp.Client` over a stdio transport (`StdioServerParameters(command, args, cwd, env)`), exactly mirroring `composite_database.build_transport` / `build_client`. Per-call `async with client:` → `await client.call_tool(tool, args)` → `result.data`.

- **Why:** reuses a pattern already proven in-repo; `fastmcp.Client` is already a dependency; no new transport code.
- **Alternative:** spawn the target `server.py` and speak raw JSON-RPC over stdio. Rejected — `fastmcp.Client` already does this and handles content-block parsing.
- **Alternative:** import the target MCP's Python code in-process. Rejected — only works for MCPs whose deps are installed in cron-mcp's venv, and breaks isolation; composite-mcp deliberately uses subprocess clients.

### D2. New tables `cron_data_jobs` + `cron_fetch_results`; `Schedule.data_job_id` nullable FK
`CronDataJob(name unique, source_mcp, tool, arguments JSON, description, timeout, enabled, timestamps)` is the reusable fetch definition. `CronFetchResult(job_id nullable, source_mcp, tool, arguments JSON, status, row_count, data_json JSON, error Text, started_at, finished_at)` stores each fetch's output (`job_id` nullable so ad-hoc `fetch_data_now` results are stored too). `Schedule.data_job_id` is a nullable FK `→ cron_data_jobs.id ON DELETE SET NULL` so a schedule can target a data job instead of a `task_name`.

- **Why:** a saved definition is needed for the automatic (scheduled) path and for repeatable manual runs; a dedicated results table keeps structured data separate from `Execution.output` (a short Text summary). `SET NULL` means deleting a job disables its schedules rather than cascading deletes or dangling references.
- **Alternative:** reference data jobs from `Schedule.task_name` via a magic prefix like `data:<job>`. Rejected — magic string in a free-text column, no integrity; a typed FK matches the `sources.category_id` precedent.
- **Alternative:** reuse `Execution.output` for the data. Rejected — `output` is `Text` (string), and we want queryable structured JSON + row counts.

### D3. `execute_task` branches on `data_job_id`; scheduled fetch runs in its own event loop
`execute_task` gains one branch: if `schedule.data_job_id` is set, run the data job instead of resolving `task_name`. The fetch core is async (`async with client`); `execute_task` is sync (called by APScheduler in a thread), so it wraps the fetch in `asyncio.run(...)`. The `Execution` row still records status; `output` holds a short summary (`status, result_id, row_count`), and the full payload goes to `CronFetchResult.data_json` linked by `job_id`.

- **Why:** minimal change to the scheduler — one branch, no new APScheduler plumbing. `run_now` already calls `execute_task`, so the manual run-now path works for free.
- **Alternative:** run data fetches on APScheduler's `AsyncIOScheduler`. Rejected — would force the whole scheduler async and touch every existing sync task; `asyncio.run` per cron fire is fine (cron is not a hot path).
- `# ponytail: per-call asyncio.run + per-call client spawn; reuse a loop / pool if fetch frequency makes spawn latency matter`

### D4. The manual tools are async; they `await` directly
`fetch_data_now`, `run_data_job`, `list_mcp_tools` are `async def` FastMCP tools, so they `await` the client directly — no event-loop bridging. Only the scheduler path (sync `execute_task`) needs `asyncio.run`.

### D5. Result shape + row count
`call_tool` returns a `CallToolResult`; use `.data` (structured, parsed from JSON content), falling back to stringified `.content` if `.data` is None. `row_count`: `len(data)` if list; `len(data["data"|"rows"|"records"])` if dict with one of those keys as a list; else 1. `# ponytail: heuristic row-count; refine per-source if a datasource needs exact counts`

### D6. Timeout
Each fetch honors `CronDataJob.timeout` (default 60, reusing `Task.timeout` semantics) via `asyncio.wait_for` around `client.call_tool`. A timeout yields a `failed` result with `error="timeout after Ns"`.

## Risks / Trade-offs

- **Spawn latency per fetch** — each fetch spawns the target MCP as a subprocess (~1–2s). → Acceptable for cron/manual; document as a known ceiling with an upgrade path (persistent client / pool). Not the hot path.
- **Large payloads in a JSON column** — a `call_yfinance_function` returning a full price history could be large. → Store as JSON for now; truncate `data_json` at a generous cap (e.g. 5 MB) and set `error` if exceeded. Add file offload when a real payload overflows.
- **Target MCP must be launchable from cron-mcp's process** — `.mcp.json` uses absolute-ish paths / `uv run --directory`; works when run on the same host. → Fine for this project's single-host layout; no remote HTTP transport in v1 (composite-mcp's http transport shape is available if needed later).
- **Dangling schedules on job delete** — mitigated by `ON DELETE SET NULL` + `execute_task` treating a null `data_job_id` (with no resolvable `task_name`) as a clear error in the `Execution`.
- **`asyncio.run` in a scheduler thread** — safe because APScheduler `BackgroundScheduler` runs each job in a thread from its `ThreadPoolExecutor`; each thread creates and tears down its own loop. Not safe if the scheduler is ever moved to `AsyncIOScheduler` — revisit then.

## Migration Plan

1. Add `CronDataJob` + `CronFetchResult` models to `mcp/models/models.py`; add `data_job_id` FK column to `Schedule`. Reinstall `mcp/models` (`pip install -e mcp/models`).
2. New tables are created by the existing `init_db()` → `Base.metadata.create_all(engine)` at startup — no migration step.
3. The new `schedules.data_job_id` column is added by a guarded `database._migrate_schedule_data_job()` (idempotent `PRAGMA table_info` check → `ALTER TABLE schedules ADD COLUMN data_job_id INTEGER REFERENCES cron_data_jobs(id) ON DELETE SET NULL`), mirroring `daas_database._migrate_sources_category_id`. Called from `init_db()`.
4. Rollback: drop the two new tables + the column; no existing data is touched by the feature.

## Open Questions

- Should `fetch_data_now` also accept a `save_as` name to persist an ad-hoc fetch as a data job? (Leaning: no — keep `fetch_data_now` ephemeral; use `create_data_job` + `run_data_job` for the saved path. Revisit if users ask.)
- Default `row_count` cap / `data_json` truncation threshold — 5 MB is a placeholder; confirm against a real yfinance history payload during the spike.
