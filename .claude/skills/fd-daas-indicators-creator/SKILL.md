---
name: fd-daas-indicators-creator
description: End-to-end create-indicators workflow — extend the fd-daas-fetch-data workflow with a persistent scraw_<slug> storage table, save the fetched data into it, and schedule a refresh cron. Use this skill whenever the user wants to persist a daas data series to a table and refresh it on a schedule — phrases like "把沪深日行情存到一张表里并定时刷新", "save this series to a table and cron it", "create a scraw table for this indicator", "schedule a daily refresh of stock_zh_a_hist", or any series + "save to table / persist / cron / schedule refresh". If steps 1–3 (entity → coverage → indicator) are already done, this skill skips straight to steps 4–6 (table + save + cron). Do NOT use this skill for a one-shot fetch with no persistence (use fd-daas-fetch-data + calculate) or to build a dashboard (use fd-daas-dashboard-creator).
---

# fd-daas-indicators-creator

Extend `fd-daas-fetch-data` with the table/save/cron steps. Steps 1–3 (entity → datasource → indicator) come from `fd-daas-fetch-data`; this skill adds steps 4–6. The numbering is intentionally `1, 4, 5, 6` so the two skills form one unified 6-step flow.

## Mental model

Six steps total; steps 1–3 belong to `fd-daas-fetch-data`:

1. (fetch-data) Check the entities
2. (fetch-data) Find the related datasource
3. (fetch-data) Create indicators
4. **Create the table** — `scraw_<slug>` via `add_pipeline_item`
5. **Save the data** — verify the backfill landed rows
6. **Create the cron** — confirm the refresh schedule

If steps 1–3 are already done (entity linked + indicator exists), skip to step 4.

## Step 0 — Handoff from fd-daas-fetch-data

Before step 4, confirm steps 1–3 are done:

- Is the entity linked to a datasource? (`mcp__daas-mcp__get_entity` shows `links`.)
- Does the indicator already exist? (`mcp__daas-mcp__list_indicators` — check by name.)

If both yes → skip to step 4. If not → invoke the `fd-daas-fetch-data` skill first, then continue at step 4. Pass the entity + indicator names forward as context so step 4 doesn't re-ask.

## Step 4 — Create the storage table

Goal: bind a `source_mcp` + `tool` + `arguments_json` to a `scraw_<slug>` storage table + upsert keys + cron cadence.

1. If no pipeline collection exists yet, create one: `mcp__daas-mcp__create_pipeline_collection(name="...", description="...")`.
2. Add the item: `mcp__daas-mcp__add_pipeline_item` with:
   - `collection_name` — the pipeline collection from step 4.1
   - `name` — unique item name (kebab-case)
   - `source_mcp` — e.g. `akshare-mcp` (resolves via `.mcp.json` `mcpServers` OR the `mcp/<source_mcp>/server.py` convention dir)
   - `tool` — the dispatch tool, e.g. `call_akshare_function`
   - `arguments_json` — JSON object of `{name, params_json}`, e.g. `{"name":"stock_zh_a_hist","params_json":"{\"symbol\":\"000001\",\"period\":\"daily\",\"start_date\":\"20240101\"}"}`
   - `storage_table` — the `scraw_<slug>` name
   - `upsert_keys` — the dedup columns, e.g. `["date"]`
   - `cron_expr` — an off-minute `Asia/Shanghai` cron, e.g. `7 16 * * 1-5` (weekdays 16:07)
3. **Enabling an item triggers an immediate backfill** — `add_pipeline_item` with `enabled=true` (the default) spawns the `source_mcp`, calls `tool`, and upserts into `scraw_<slug>`. Tell the user this is happening.

**Duplicate item name**: if `add_pipeline_item` rejects with a duplicate-name error, offer to `mcp__daas-mcp__update_pipeline_item` (same `collection_name` + `name`) instead of creating a duplicate. Confirm with the user before overwriting.

## Step 5 — Save the data (verify the backfill)

Goal: confirm the backfill landed real rows before declaring success.

1. Call `mcp__daas-mcp__list_source_tables` — introspects `scraw_*` (excluding `scraw_configs`) and returns each with row count + columns. Confirm `scraw_<slug>` is there with `row_count > 0`.
2. Call `mcp__dashboard-mcp__query_table` with `database="daas"`, `table="scraw_<slug>"`, `limit=5` to show a sample.
3. Show the user: "Backfill landed N rows; sample: …".

**Zero rows**: if the table is empty, the backfill failed. Report it, suggest checking the `arguments_json` + the upstream MCP's connectivity, and STOP before step 6. Do not schedule a cron for an empty table.

## Step 6 — Create the refresh cron

Goal: confirm a refresh schedule exists; repair if missing.

1. Enabling the pipeline item with a `cron_expr` auto-wires a cron-mcp `create_task` + `create_schedule`. Confirm the schedule exists: `mcp__cron-mcp__list_schedules` — find the schedule whose `task` matches the item's `--fetch-item <id>` command.
2. If present → report the next fire time to the user.
3. **Missing or disabled**: call `mcp__daas-mcp__sync_pipeline_cron` (re-syncs cron for all enabled items, removes disabled ones). If still missing, manually `mcp__cron-mcp__create_task` + `mcp__cron-mcp__create_schedule` with the cron task command `uv run --directory /Users/chengsishi/code/cli-anything/mcp/daas-mcp python server.py --fetch-item <id>` (use the actual repo root) + the item's `cron_expr` + `timezone="Asia/Shanghai"`.

## Gotchas

- **Enabling an enabled item triggers an immediate backfill.** This is the `add_pipeline_item` default. If you don't want a backfill (e.g. dry-run), pass `enabled=false` then `enable_pipeline_item` later — but the indicator-creator workflow always wants the backfill.
- **`source_mcp` resolves two ways**: `.mcp.json` `mcpServers` entry OR the `mcp/<source_mcp>/server.py` convention dir. `mcp/models` is injected into `PYTHONPATH` so spawned servers can `import models`.
- **daas-mcp's own `fetch_data` is intentionally NOT used** for the bridge — the bridge calls the source MCPs directly (the daas registry has no akshare functions and the daas-agent-harness path is mis-resolved).
- **The cron task command** must point at the real repo root: `uv run --directory <repo>/mcp/daas-mcp python server.py --fetch-item <id>`. Schedules fire on the next `cron-mcp` start (`load_schedules()` loads enabled rows into APScheduler).
- **`upsert_keys`** must be columns that exist in the fetched data (e.g. `["date"]` for daily series). The bridge upserts on these keys; mismatched keys cause duplicate rows.
- This skill stops at table + save + cron. To visualize the data, hand off to `fd-daas-dashboard-creator`. To summarize the whole flow as a replayable workflow, hand off to `fd-daas-workflow-creator`.
