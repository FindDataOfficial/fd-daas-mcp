# fd-daas-indicators-creator Specification

## Purpose
TBD - created by archiving change add-fd-daas-skills. Update Purpose after archive.
## Requirements
### Requirement: Skill exists and triggers on create-indicators intent

The system SHALL ship a skill at `.claude/skills/fd-daas-indicators-creator/SKILL.md` (project scope) whose `description` triggers when the user wants to create a persistent `scraw_<slug>` table for a datasource, save fetched data into it, and schedule a refresh cron — in English or Chinese.

#### Scenario: Triggers on table-save-and-cron phrasing
- **WHEN** the user says "把沪深日行情存到一张表里并定时刷新" or "save this series to a table and refresh it on a cron"
- **THEN** the `fd-daas-indicators-creator` skill is consulted

### Requirement: Handoff from fd-daas-fetch-data

The skill's first step SHALL be to run (or reuse) the `fd-daas-fetch-data` skill for the entity → datasource → indicator steps. It MUST detect when steps 1–3 are already complete (entity linked, datasource covering, indicator created) and skip to step 4.

#### Scenario: Steps 1–3 already done
- **WHEN** the entity is already linked and the indicator already exists
- **THEN** the skill skips to step 4 (create the table) and does not re-run `fd-daas-fetch-data`

#### Scenario: Steps 1–3 not done
- **WHEN** no prior fetch-data run is detected
- **THEN** the skill invokes `fd-daas-fetch-data` first, then continues at step 4

### Requirement: Create the storage table

The skill SHALL create the `scraw_<slug>` storage table by calling `mcp__daas-mcp__add_pipeline_item` with a `source_mcp` + `tool` + `arguments_json` + `upsert_keys` + `cron_expr`. It MUST explain to the user that enabling the item triggers an immediate backfill.

#### Scenario: Table created
- **WHEN** the skill calls `add_pipeline_item` with a valid `source_mcp` + `tool`
- **THEN** a `scraw_<slug>` table is auto-created on first fetch and the item is added to the pipeline collection

#### Scenario: Duplicate item name
- **WHEN** an item with the same name already exists in the collection
- **THEN** the skill reports the duplicate and offers to update the existing item via `update_pipeline_item` rather than creating a duplicate

### Requirement: Save the data

The skill SHALL persist the fetched data into the `scraw_<slug>` table. Because enabling a pipeline item triggers an immediate backfill, the skill MUST verify the backfill landed rows (via `mcp__dashboard-mcp__query_table` or `mcp__daas-mcp__list_source_tables`) and show the user real records + counts before declaring success.

#### Scenario: Backfill produced rows
- **WHEN** the backfill completes and the table has rows
- **THEN** the skill shows the user a sample + count and proceeds to cron creation

#### Scenario: Backfill produced zero rows
- **WHEN** the table is empty after backfill
- **THEN** the skill reports the empty result, suggests checking the `arguments_json` + upstream connectivity, and stops before cron creation

### Requirement: Create the refresh cron

The skill SHALL schedule a refresh cron by relying on the pipeline item's `cron_expr` (which auto-wires a cron-mcp `create_task` + `create_schedule` on enable) and confirm the schedule exists. If the pipeline item is disabled or the cron is missing, the skill MUST call `mcp__cron-mcp__create_task` + `mcp__cron-mcp__create_schedule` (or `mcp__daas-mcp__sync_pipeline_cron`) to repair it.

#### Scenario: Cron auto-wired on enable
- **WHEN** the pipeline item is enabled with a `cron_expr`
- **THEN** the skill confirms the cron-mcp schedule exists and reports the next fire time to the user

#### Scenario: Cron missing or disabled
- **WHEN** the schedule is absent after the item is enabled
- **THEN** the skill calls `sync_pipeline_cron` (or manual `create_task` + `create_schedule`) and re-confirms

