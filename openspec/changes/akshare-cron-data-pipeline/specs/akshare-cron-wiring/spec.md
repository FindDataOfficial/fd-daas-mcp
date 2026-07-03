## ADDED Requirements

### Requirement: A helper wires each catalog entry into `cron-mcp` as a task plus a schedule

`mcp/akshare-mcp/register_cron.py` SHALL connect to `cron-mcp` via `fastmcp.Client` (using the launch command resolved from `.mcp.json`) and, for each catalog entry, register a `cron-mcp` task whose `command` invokes `fetch_to_store.py` with the entry's `akshare_function`, `default_params_json`, `table`, and `upsert_keys`, then register a schedule bound to that task with the entry's `cron` expression and `timezone="Asia/Shanghai"`.

#### Scenario: Wiring one dataset end-to-end

- **WHEN** `register_cron.py --only ashare-daily` is run
- **THEN** a `cron-mcp` task named `akshare_ashare-daily` is created with a command of the form `uv run --directory <repo>/mcp/akshare-mcp python fetch_to_store.py --name <fn> --params '<json>' --table scraw_ashare_daily --keys date,symbol`
- **AND** a `cron-mcp` schedule named `akshare_ashare-daily` is created with the entry's `cron` expression, `task` set to the task name, and `timezone="Asia/Shanghai"`
- **AND** the script prints a JSON summary of created/updated/skipped tasks and schedules

#### Scenario: All datasets wired in one command

- **WHEN** `register_cron.py` is run with no `--only` flag
- **THEN** every entry in `ALL_DATASETS` is processed
- **AND** one task and one schedule are created per entry

### Requirement: Wiring is idempotent

Re-running the helper SHALL not fail on existing names; it SHALL update the task `command` and the schedule `cron`/`timezone` to match the catalog, and SHALL leave `enabled` state and any existing schedule `id` intact where possible.

#### Scenario: Re-run updates instead of failing

- **WHEN** `register_cron.py --only ashare-daily` is run a second time
- **THEN** the existing task's `command` is updated to the current catalog value (via `cron-mcp.update_task`)
- **AND** the existing schedule's `cron` is updated to match the catalog
- **AND** the summary reports the entry as `updated`, not `created`, and not as an error

#### Scenario: Existing schedule id and enabled state preserved

- **WHEN** an entry being updated has an existing schedule that is currently paused (`enabled=0`)
- **THEN** the helper SHALL NOT re-enable it; the `enabled` state is preserved
- **AND** the schedule `id` is unchanged

### Requirement: Helper supports dry-run, single-entry, unregister, and immediate run

The helper SHALL support `--dry-run` (print planned actions, create nothing), `--only <name>` (process one entry), `--unregister` (delete the task and schedule for each entry), and `--run <name>` (trigger an immediate fetch via `cron-mcp.run_now` after wiring).

#### Scenario: Dry-run previews without side effects

- **WHEN** `register_cron.py --dry-run` is run
- **THEN** the planned task `command` and schedule `cron` for every entry are printed
- **AND** no `cron-mcp` tool that mutates state is called

#### Scenario: Unregister removes tasks and schedules

- **WHEN** `register_cron.py --unregister --only ashare-daily` is run
- **THEN** the `akshare_ashare-daily` schedule is deleted (via `cron-mcp.delete_schedule`) and the `akshare_ashare-daily` task is deleted (via `cron-mcp.delete_task`)
- **AND** the `scraw_*` table is left untouched

#### Scenario: Run-now triggers an immediate fetch

- **WHEN** `register_cron.py --run ashare-daily` is run
- **THEN** after wiring, the helper calls `cron-mcp.run_now` for the entry's schedule
- **AND** reports the execution result in the summary

### Requirement: Task commands use absolute paths and are CWD-independent

Every task `command` registered by the helper SHALL use absolute paths (`uv run --directory <abs_repo>/mcp/akshare-mcp python fetch_to_store.py ...`) so that `cron-mcp` can execute it correctly regardless of its working directory.

#### Scenario: Command runs from any CWD

- **WHEN** `cron-mcp` executes a registered task from its own working directory
- **THEN** the `--directory` flag resolves the fetcher location absolutely
- **AND** `fetch_to_store.py` resolves `DAAS_DATABASE_URL` and `.mcp.json` independently of the CWD
