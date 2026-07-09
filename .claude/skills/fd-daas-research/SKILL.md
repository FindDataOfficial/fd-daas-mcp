---
name: fd-daas-research
description: Orchestrate a full daas research workflow — analyze a natural-language demand into an analysis plan, then delegate to fd-daas-entities-collection-creator (when the demand defines a group/watchlist), fd-daas-indicators-creator (table + save + cron), and fd-daas-dashboard-creator (standalone HTML dashboard). Use this skill whenever the user gives a research-style demand that needs indicators and a dashboard — phrases like "帮我研究一下比亚迪，做指标和看板", "research TSLA — build indicators and a dashboard", "研究一下沪深300成分股做个看板", "research SSE banks — set up indicators and a dashboard", "分析这只股票并做个可视化", "把今天大宗交易过的股票做个研究流水线", "set up a full pipeline for these stocks", or any entity + "research / 分析 / 研究 / full pipeline". When the demand names a group (a watchlist, a rule like "SSE banks", or an explicit list of codes), this skill first delegates to fd-daas-entities-collection-creator to persist the group as a re-syncable collection before building indicators over its members. Do NOT use this skill if the user only wants indicators (use fd-daas-indicators-creator) or only a dashboard (use fd-daas-dashboard-creator) or a one-shot fetch (use fd-daas-fetch-data) or only an entity collection (use fd-daas-entities-collection-creator); this skill orchestrates the full analyze → [collection] → indicators → dashboard flow.
---

# fd-daas-research

Analyze a demand → produce a plan → delegate to `fd-daas-entities-collection-creator` (group demands only) → `fd-daas-indicators-creator` + `fd-daas-dashboard-creator`. This is the top-level orchestration skill; it does not call MCP tools directly except to read context for the plan.

## Mental model

Four delegations, with an explicit confirmation gate before any of them and a conditional collection step for group demands:

1. **Analyze the demand** → an analysis plan naming entities (or a group/rule), indicators, and dashboard shape. Get user confirmation.
2. **Delegate to `fd-daas-entities-collection-creator`** — only when the demand defines a group/watchlist (a rule like "SSE banks", or an explicit code list), not a single entity. Persist the group as a re-syncable collection before building indicators over its members.
3. **Delegate to `fd-daas-indicators-creator`** with the entities (single, or the collection's members) + indicators from the plan.
4. **Delegate to `fd-daas-dashboard-creator`** with the indicator names + `scraw_<slug>` tables from step 3.

Each delegation passes context forward and skips already-done steps.

## Step 1 — Analyze the demand

Goal: turn a loose research demand into a concrete plan.

1. Parse the user's demand for: the entity (stock/company/country) **or a group** (a watchlist, a rule like "SSE banks" / "stocks with block trades today", or an explicit list of codes), the time range, the indicators implied (price → SMA/EMA/RSI; fundamentals → ratios/growth; macro → level/pct_change), and the desired dashboard (line chart, comparison, table).
2. Read context to ground the plan:
   - `mcp__daas-mcp__search_entities` — confirm the entity exists + get `entity_id`. For a group demand, confirm a few representative members resolve so the plan doesn't promise a collection of codes that aren't in the registry.
   - `mcp__daas-mcp__get_entity_coverage` — see which datasources + columns are available (so the plan doesn't promise a column that doesn't exist).
   - `mcp__daas-mcp__list_indicator_ops` — confirm the ops you'll propose are real.
   - `mcp__daas-mcp__list_entity_collections` — if it's a group demand, check a collection with this name/rule doesn't already exist (skip-if-already-done).
3. Draft the plan as markdown:
   - **Entities** — name + `entity_id` + `identifier_in_source`; **or**, for a group demand,
   - **Collection** — collection name + the membership rule (declarative `rule_json` fields like `entity_type`/`exchange`/`codes`/`name_regex`, **or** a description of the script logic for the creator skill to author as a `members(ctx)` script — use a script when the rule reads another table like `scraw_dzjy` or `observations`)
   - **Indicators** — one row per indicator: name, op, params, `source_table`, `value_column`
   - **Dashboard shape** — title, charts (type + source), tables, refresh cadence
   - **Skip flags** — if no indicators are needed (dashboard-only), say so
4. Show the plan to the user and ask: "Does this plan look right? I'll delegate to entities-collection-creator (if group), then indicators-creator, then dashboard-creator."

## Step 2 — No-indicators branch

If the analysis shows the demand is dashboard-only (no new indicators/tables needed — e.g. visualize an existing `observations` series), skip the indicators delegation and go straight to `fd-daas-dashboard-creator`. A group demand can still go through the collection step first — a collection is useful even without indicators. Tell the user why you skipped (e.g. "indicators already exist for this entity").

## Step 3 — Delegate to fd-daas-entities-collection-creator (group demands only)

Hand off the collection-definition work when the demand names a group rather than a single entity. Defining the group as a collection first (instead of a loose code list passed inline) is what lets the rest of the flow — and later crons/workflows — refer to it by name and re-sync membership as it drifts.

- Invoke the `fd-daas-entities-collection-creator` skill.
- Pass as context: the collection name + the membership rule (the declarative `rule_json` fields, OR a description of the script logic the creator skill will turn into a `members(ctx)` script saved to `mcp/daas-mcp/rules/entity_collections/<name>.py`).
- The creator skill decides `rule_json` vs `rule_script`, authors + saves the script if needed, creates the collection with `rule_script=<path>` (or `rule`), syncs to populate members, and optionally registers a daily cron.
- Wait for it to finish, then collect the collection name + its member entity codes/ids for step 4.

**Skip if not a group demand**: if the plan names a single entity, skip this step entirely and go to step 4 — there's nothing to collect.

**Skip if already done**: if `mcp__daas-mcp__list_entity_collections` shows a collection with this name + rule, skip and tell the user.

## Step 4 — Delegate to fd-daas-indicators-creator

Hand off the indicator + table + cron work:

- Invoke the `fd-daas-indicators-creator` skill.
- Pass as context: the entities (with `entity_id` + `identifier_in_source`), the indicators (name, op, params, `source_table`, `value_column`), and the suggested `cron_expr`.
  - If step 3 produced a collection, pass its member codes as the entity set. The indicators-creator skill is single-entity-per-call (it reuses `fd-daas-fetch-data` per entity), so for a collection you iterate it per member; for a large collection, pick a lead member for the indicator+dashboard and note the collection name as the universe so the dashboard can label it.
- The indicators-creator skill runs its steps 1–6 (reusing `fd-daas-fetch-data` for 1–3 if not already done, then table + save + cron for 4–6).
- Wait for it to finish, then collect the created `scraw_<slug>` table name(s) + indicator names for step 5.

**Skip if already done**: if `mcp__daas-mcp__list_indicators` shows the indicators already exist and `mcp__daas-mcp__list_source_tables` shows the `scraw_<slug>` table, skip this delegation and tell the user.

## Step 5 — Delegate to fd-daas-dashboard-creator

Hand off the dashboard work:

- Invoke the `fd-daas-dashboard-creator` skill.
- Pass as context: the indicator names + the `scraw_<slug>` table(s) from step 4, plus the dashboard shape from the plan. If step 3 produced a collection, pass the collection name so the dashboard can label its universe.
- The dashboard-creator skill runs its propose → permission → build → open → iterate → register flow.
- Wait for it to finish.

**Skip if already done**: if `dashboard/my-charts-dashboard/daas.md` already lists a dashboard for this plan, skip and tell the user.

## Gotchas

- **This skill orchestrates; it does not call `create_indicator`/`create_entity_collection` or write HTML itself.** All state-mutating work happens in the delegated skills. If you find yourself writing a `scraw_*` table, a rule script, or an HTML file, stop — you're inside the wrong skill.
- **The collection step is group-only.** Don't force a collection on single-entity research ("research 比亚迪" has one entity — go straight to indicators). The collection step earns its place only when the demand defines a rule or a set of entities that should persist as a named, re-syncable group.
- **A rule-based collection is authoritative.** `sync_entity_collection` re-derives the full intended set and remove_out's anything not in it — including members added by hand. If the user later hand-edits a collection this flow created, the next sync (manual, or via the optional cron the creator skill may have registered) reverts those edits; tell them to edit the rule or the script instead.
- **Pass context forward explicitly.** The `entities-collection-creator` step needs the membership rule; the `indicators-creator` step needs the `entity_id` + `identifier_in_source` + the exact indicator specs (or the collection's member codes); the `dashboard-creator` step needs the `scraw_<slug>` table names + the collection name (for labeling). Don't make any skill re-derive what the plan already established.
- **Skip-if-already-done** mirrors the `fd-daas-indicators-creator` step-0 rule: check `list_entity_collections` + `list_indicators` + `list_source_tables` + `daas.md` before each delegation.
