## ADDED Requirements

### Requirement: Bind a data job to a cron schedule

`create_schedule` SHALL accept an optional `data_job` (data job name) parameter. When set, the schedule targets that data job instead of a shell/registry `task`, and `schedules.data_job_id` is populated.

#### Scenario: Create a schedule bound to a data job

- **WHEN** `create_schedule(name="nightly_nav", cron="0 9 * * *", data_job="daily_fund_nav")` is called
- **THEN** a `schedules` row is persisted with `data_job_id` set to the `daily_fund_nav` job's id and `task_name` left empty
- **AND** an APScheduler job is registered under `schedule:<id>` that runs the data job on the cron
- **AND** the tool returns `{success, schedule_id, name, cron, data_job}`

#### Scenario: task and data_job are mutually exclusive

- **WHEN** `create_schedule` is called with both `task` and `data_job`
- **THEN** the tool returns `{success: false, error}` without creating a schedule

#### Scenario: Binding to a missing data job fails

- **WHEN** `create_schedule(..., data_job="nope")` references a non-existent job
- **THEN** the tool returns `{success: false, error}` and no schedule is created

### Requirement: Execute a scheduled data fetch on cron

When a schedule with `data_job_id` fires, the scheduler SHALL run that data job — connecting to its `source_mcp`, calling `tool` with `arguments` — and persist the result.

#### Scenario: Cron fire runs the bound data job

- **WHEN** APScheduler fires a schedule whose `data_job_id` is set
- **THEN** `execute_task` runs the data job (not the `task_name` path), stores a `cron_fetch_results` row, and records an `Execution` with `status` reflecting success/failure
- **AND** `Execution.output` holds a short summary (`status, result_id, row_count`) while the full data lives in the result row

#### Scenario: A disabled schedule does not fetch

- **WHEN** a schedule with `data_job_id` has `enabled=0`
- **THEN** firing it SHALL do nothing and record no result

### Requirement: Run a scheduled data fetch on demand

A schedule bound to a data job SHALL be runnable immediately via the existing `run_now` tool.

#### Scenario: run_now executes the data job

- **WHEN** `run_now(schedule_id)` is called for a schedule with `data_job_id` set
- **THEN** the data job runs immediately, a `cron_fetch_results` row is stored, and the schedule's `last_run_at` is updated
- **AND** the tool returns `{success, schedule_id, message}`

### Requirement: Schedule integrity when a data job is deleted

Deleting a data job SHALL NOT delete schedules that reference it; the reference SHALL be cleared.

#### Scenario: Delete nulls the schedule binding

- **WHEN** a data job referenced by one or more schedules is deleted via `delete_data_job`
- **THEN** `schedules.data_job_id` is set to NULL for those rows (FK `ON DELETE SET NULL`)
- **AND** the schedules themselves remain (paused-effective: a fire with no `data_job_id` and no `task_name` records a failed `Execution` with a clear error)

### Requirement: Loading schedules at startup binds data jobs

At startup, `load_schedules` SHALL register APScheduler jobs for all enabled schedules, including those bound to a data job, so scheduled fetches resume across restarts.

#### Scenario: Restart resumes a data-job schedule

- **WHEN** cron-mcp restarts with an enabled schedule whose `data_job_id` is set
- **THEN** the schedule's APScheduler job is re-registered and `next_run_at` is updated
- **AND** firing it after restart runs the data job
