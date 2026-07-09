## Why

cron-mcp today can only run a shell command or a trivial built-in stub on a schedule — `Schedule.task_name` resolves to a DB `Task.command` (run as a subprocess) or a registry callable (`news_summary`, `weekly_report`, `backup`). It cannot pull data from the project's other MCP servers (`daas` `fetch_data`, `yfinance` `call_yfinance_function`, `edgartools` `get_financials`, …) — neither on a cron nor on demand. composite-mcp already proves the cross-MCP call pattern (`fastmcp.Client` over a stdio transport built from an `.mcp.json` entry), and cron-mcp already depends on `fastmcp` + `mcp`, so this is a thin fetch-and-store layer over an existing primitive — not new infrastructure.

## What Changes

- New first-class **data fetch** unit: a reusable, named definition (`source_mcp`, `tool`, `arguments`) that connects to another MCP server and persists the data its tool returns.
- **Manual** path: `fetch_data_now(source_mcp, tool, arguments)` runs a one-shot fetch with no setup; `run_data_job(name)` runs a saved fetch on demand.
- **Automatic** path: `create_schedule` gains an optional `data_job` parameter; the scheduled job runs the data fetch on cron (and on demand via the existing `run_now`).
- **Discovery**: `list_mcp_servers` (from `.mcp.json`) and `list_mcp_tools(source_mcp)` (live tool list) so a fetch can be targeted without leaving cron-mcp.
- **Stored results**: every fetch (manual or scheduled) is persisted with status, row count, data, and error; `list_fetch_results` / `get_fetch_result` retrieve them.
- New shared-schema tables: `cron_data_jobs`, `cron_fetch_results`. New nullable `Schedule.data_job_id` FK, added by a guarded idempotent `ALTER TABLE` mirroring `daas-mcp`'s `category_id` migration (no Alembic).
- No new dependencies (`fastmcp.Client` is already available). No changes to other MCP servers — they are called as clients, not modified.

## Capabilities

### New Capabilities

- `cron-data-fetch`: Manual, on-demand cross-MCP data fetch — ad-hoc (`fetch_data_now`) and saved data jobs (`create` / `run` / `update` / `delete` / `list` / `get_data_job`), MCP discovery (`list_mcp_servers`, `list_mcp_tools`), and persisted fetch results (`list_fetch_results`, `get_fetch_result`).
- `cron-data-schedule`: Automatic, scheduled cross-MCP data fetch — bind a data job to a cron `Schedule` (via `create_schedule(data_job=...)`) and run it on the schedule or via `run_now`, recording both an `Execution` and a `CronFetchResult`.

### Modified Capabilities

None — cron-mcp has no prior spec; both capabilities are new.

## Impact

- `mcp/models/models.py`: +2 tables (`CronDataJob`, `CronFetchResult`), +1 nullable FK column on `Schedule` (`data_job_id`, `ON DELETE SET NULL`).
- `mcp/cron-mcp/`: new `mcp_client.py` (transport + client over `.mcp.json`) and `fetch_runner.py` (run a job, persist result); extend `server.py` (new tools + `data_job` param on `create_schedule`), `agent_runner.py` (`execute_task` branches on `data_job_id`), `database.py` (guarded `ALTER TABLE`); update `pyproject.toml` `py-modules`.
- `mcp/daas.db`: new tables auto-created via `Base.metadata.create_all`; `schedules.data_job_id` added by guarded `ALTER TABLE` at startup.
- No new dependencies. No `.mcp.json` change (cron-mcp reads the existing file). Other MCP servers untouched.
