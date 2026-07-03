## 1. Spike (de-risk before building)

- [ ] 1.1 Confirm `fastmcp.Client` over a stdio transport built from a `.mcp.json` entry (`{command, args, cwd, env}`) can connect to a local MCP (e.g. `daas-mcp` or `yfinance-mcp`), `await client.list_tools()`, and `await client.call_tool(name, args)` returning a `.data` JSON-addressable result. ~15 lines, throwaway script in `mcp/cron-mcp/`.
- [ ] 1.2 Confirm `asyncio.run(coro)` works inside the APScheduler `BackgroundScheduler` thread (run a one-off `execute_task` that calls an async fetch), so the scheduled path is viable without switching to `AsyncIOScheduler`.
- [ ] 1.3 Document the real `call_tool` result shape (`.data` vs `.content`) for a representative source (yfinance history + daas `fetch_data`) so the `row_count` heuristic and `data_json` storage are built against reality. Confirm the 5 MB `data_json` cap against a real yfinance payload.

## 2. Schema (mcp/models/ first)

- [ ] 2.1 Add `CronDataJob` model: `id, name (unique, indexed), source_mcp, tool, arguments (JSON), description (Text), timeout (Integer, default 60), enabled (Boolean, default True), created_at, updated_at`.
- [ ] 2.2 Add `CronFetchResult` model: `id, job_id (FK → cron_data_jobs.id, ON DELETE SET NULL, nullable, indexed), source_mcp, tool, arguments (JSON), status (String), row_count (Integer, default 0), data_json (JSON, nullable), error (Text, nullable), started_at, finished_at`.
- [ ] 2.3 Add nullable FK `Schedule.data_job_id` (`Integer, ForeignKey("cron_data_jobs.id", ondelete="SET NULL"), nullable=True, index=True`).
- [ ] 2.4 Reinstall `mcp/models/` (`pip install -e mcp/models`); confirm `cron_data_jobs` + `cron_fetch_results` create in `daas.db` via `Base.metadata.create_all`.

## 3. Migration guard (database.py)

- [ ] 3.1 Add `database._migrate_schedule_data_job()` — idempotent: `PRAGMA table_info(schedules)` check → `ALTER TABLE schedules ADD COLUMN data_job_id INTEGER REFERENCES cron_data_jobs(id) ON DELETE SET NULL`. Mirror `daas_database._migrate_sources_category_id`.
- [ ] 3.2 Call it from `init_db()` after `Base.metadata.create_all` (tables must exist before the FK reference resolves).

## 4. MCP client helper (mcp_client.py)

- [ ] 4.1 `list_mcp_servers()` — read project-root `.mcp.json` (repo root = `Path(__file__).resolve().parents[2]`), return stdio entries as `{name: {command, args, cwd, env}}`; exclude `cron-mcp` itself.
- [ ] 4.2 `build_client(server_name)` — look up the entry, build a `fastmcp.Client` over a stdio transport (mirror `combine_database.build_transport`/`build_client`). Raise a clear error if `server_name` not in `.mcp.json`.
- [ ] 4.3 `async call_mcp_tool(server_name, tool, arguments, timeout=60)` — `async with client:` + `asyncio.wait_for(client.call_tool(tool, arguments), timeout)`; return `result.data` (fallback to stringified `result.content` if None).
- [ ] 4.4 `async list_mcp_tools(server_name)` — `await client.list_tools()` → `[{name, description}]`.

## 5. Fetch runner (fetch_runner.py)

- [ ] 5.1 `async _fetch(job_or_fields)` — call `call_mcp_tool`, derive `row_count` (list→len; dict with `data`/`rows`/`records` list→len; else 1), truncate `data_json` at 5 MB cap (set `error` if exceeded), return `(status, data_json, row_count, error)`.
- [ ] 5.2 `run_data_job(job_name, schedule_id=None)` — load `CronDataJob`, run the fetch (sync wrapper: `asyncio.run(_fetch(...))`), persist a `CronFetchResult` row; if `schedule_id` given, update the `Execution` (status + summary `output`) and `schedule.last_run_at`. Return `{status, result_id, row_count, preview}`.
- [ ] 5.3 `fetch_data_now(source_mcp, tool, arguments, timeout=60)` — same as 5.1 but with `job_id=NULL`; persist + return summary. Reuse `_fetch`.

## 6. Data-job tools (server.py)

- [ ] 6.1 `create_data_job(name, source_mcp, tool, arguments, description="", timeout=60)` — persist, reject duplicate name.
- [ ] 6.2 `list_data_jobs()` / `get_data_job(name)`.
- [ ] 6.3 `update_data_job(name, arguments=..., description=..., timeout=..., enabled=...)` — update only supplied fields (prevents breaking bound schedules on arg change).
- [ ] 6.4 `delete_data_job(name)` — remove row (FK `SET NULL` clears bound schedules); return `{success, name}`.

## 7. Manual fetch + discovery + results tools (server.py)

- [ ] 7.1 `fetch_data_now(source_mcp, tool, arguments, timeout=60)` — call `fetch_runner.fetch_data_now`.
- [ ] 7.2 `run_data_job(name)` — call `fetch_runner.run_data_job`.
- [ ] 7.3 `list_mcp_servers()` / `list_mcp_tools(source_mcp)` — call `mcp_client`.
- [ ] 7.4 `list_fetch_results(job_id=None, source_mcp=None, limit=50)` / `get_fetch_result(result_id)`.

## 8. Schedule integration (server.py + agent_runner.py)

- [ ] 8.1 Extend `create_schedule` with optional `data_job: Optional[str] = None`; validate mutual exclusivity with `task` and that the job exists; set `Schedule.data_job_id`, leave `task_name` empty. Return `data_job` in the response.
- [ ] 8.2 `agent_runner.execute_task` — branch: if `schedule.data_job_id` is set, call `fetch_runner.run_data_job(by_id, schedule_id)`; else existing `task_name` path. Create the `Execution` row before the branch in both cases.
- [ ] 8.3 Confirm `run_now` → `run_schedule_now` → `execute_task` works for a data-job schedule (no new code, just verify the branch fires).
- [ ] 8.4 Confirm `load_schedules` re-registers data-job schedules across a restart (next_run_at updated).

## 9. Package config

- [ ] 9.1 `mcp/cron-mcp/pyproject.toml` — add `mcp_client`, `fetch_runner` to `[tool.setuptools] py-modules`. (No new dependency — `fastmcp`/`mcp` already present.)

## 10. Self-check

- [ ] 10.1 `mcp/cron-mcp/selfcheck.py` (temp DB) — covers: `list_mcp_servers` excludes cron-mcp; `create_data_job` + `run_data_job` against a stubbed MCP client (patch `call_mcp_tool`); `fetch_data_now` stores a result with `job_id=NULL`; `create_schedule(data_job=...)` rejects `task`+`data_job` and missing job; `execute_task` branch runs the job and writes `Execution`+`CronFetchResult`; `delete_data_job` sets `schedules.data_job_id` to NULL. Mock the MCP client (no real subprocess) so it runs offline.
- [ ] 10.2 One live smoke test, gated behind `CRON_LIVE=1`, that fetches from `yfinance-mcp` (ticker_history AAPL 1mo) end-to-end via `fetch_data_now`.

## 11. Docs

- [ ] 11.1 Update `CLAUDE.md` `mcp/cron-mcp/` section: new tables, new tools (fetch_data_now, data jobs, run_data_job, list_mcp_servers/tools, list_fetch_results/get_fetch_result), `create_schedule(data_job=...)`, key files (`mcp_client.py`, `fetch_runner.py`, `selfcheck.py`), self-check command.
- [ ] 11.2 Update `construction/mcp.md`: add `cron_data_jobs` / `cron_fetch_results` to the cron-mcp table domain row; note `schedules.data_job_id` guarded ALTER.
