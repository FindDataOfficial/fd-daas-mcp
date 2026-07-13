---
name: fd-daas-research
description: Orchestrate a full daas research workflow - analyze a natural-language demand into an analysis plan, then delegate to fd-daas-entities-collection-creator (when the demand defines a group/watchlist), fd-daas-indicators-creator (table + save), and fd-daas-dashboard-creator (standalone HTML dashboard). Use this skill whenever the user gives a research-style demand that needs indicators and a dashboard - phrases like "帮我研究一下比亚迪，做指标和看板", "research TSLA - build indicators and a dashboard", "研究一下沪深300成分股做个看板", "research SSE banks - set up indicators and a dashboard", "分析这只股票并做个可视化", or any entity + "research / 分析 / 研究 / full pipeline". When the demand names a group (a watchlist, a rule like "SSE banks", or an explicit list of codes), this skill first delegates to fd-daas-entities-collection-creator to persist the group before building indicators over its members. Do NOT use this skill if the user only wants indicators (use fd-daas-indicators-creator) or only a dashboard (use fd-daas-dashboard-creator) or a one-shot fetch (use fd-daas-fetch-data) or only an entity collection (use fd-daas-entities-collection-creator); this skill orchestrates the full analyze -> [collection] -> indicators -> dashboard flow. Uses sqlite3 for plan context - NO MCP tools.
---

# fd-daas-research

Analyze a demand -> produce a plan -> delegate to `fd-daas-entities-collection-creator` (group demands only) -> `fd-daas-indicators-creator` (table + save, **no cron**) + `fd-daas-dashboard-creator`. This is the top-level orchestration skill; it reads context via **`sqlite3`** for the plan and does not mutate state itself.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` points at the DB (currently `sqlite:///daas.db`). From the repo root, `sqlite3 daas.db "..."` works.

## Mental model

1. **Analyze the demand** -> a plan naming entities (or a group/rule), indicators, and dashboard shape. Get user confirmation.
2. **Delegate to `fd-daas-entities-collection-creator`** - group demands only.
3. **Delegate to `fd-daas-indicators-creator`** - entities + indicators (table + save; no cron).
4. **Delegate to `fd-daas-dashboard-creator`** - indicator names + `scraw_<slug>` tables.

## Step 1 - Analyze the demand

1. Parse the demand for: the entity **or a group** (watchlist, rule, or code list), the time range, the indicators implied (price -> SMA/EMA/RSI; fundamentals -> ratios/growth; macro -> level/pct_change), and the dashboard shape.
2. Read context via `sqlite3`:
   - Confirm the entity exists: `sqlite3 daas.db "SELECT id, name, ticker FROM entities WHERE name LIKE '%<term>%' OR ticker LIKE '%<term>%'"`
   - Coverage: `sqlite3 daas.db "SELECT s.name, l.identifier_in_source, f.name FROM entity_datasource_links l JOIN sources s ON s.id=l.source_id JOIN daas_functions f ON f.source_id=s.id WHERE l.entity_id=<id>"`
   - Indicator ops: `uv run --with pandas --with numpy python .claude/skills/skill-based-data-fetch/scripts/run_indicator.py --list-ops`
   - Existing collections (group demands): `sqlite3 daas.db "SELECT name, description FROM entity_collections"`
3. Draft the plan as markdown: **Entities** (name + id + `identifier_in_source`) **or Collection** (name + membership rule), **Indicators** (name, op, params, `source_table`, `value_column`), **Dashboard shape**, **Skip flags**.
4. Show the plan and ask: "Does this plan look right? I'll delegate to entities-collection-creator (if group), then indicators-creator, then dashboard-creator."

## Step 2 - No-indicators branch

If dashboard-only (no new indicators/tables needed), skip the indicators delegation and go straight to `fd-daas-dashboard-creator`. A group demand can still go through the collection step first. Tell the user why you skipped.

## Step 3 - Delegate to fd-daas-entities-collection-creator (group demands only)

- Invoke `fd-daas-entities-collection-creator` with the collection name + membership rule.
- Wait for it to finish, then collect the collection name + member codes/ids for step 4.

**Skip if not a group demand**: single entity -> go straight to step 4.
**Skip if already done**: if `sqlite3 daas.db "SELECT name FROM entity_collections WHERE name='<name>'"` returns a row, skip and tell the user.

## Step 4 - Delegate to fd-daas-indicators-creator

- Invoke `fd-daas-indicators-creator` with the entities (id + `identifier_in_source`), indicators (name, op, params, `source_table`, `value_column`).
  - For a collection, iterate per member. For a large collection, pick a lead member for the indicator+dashboard and note the collection name as the universe.
- The indicators-creator skill runs steps 1-5 (reusing `fd-daas-fetch-data` for 1-3, then table + save for 4-5; **no cron**).
- Wait, then collect the `scraw_<slug>` table name(s) + indicator names.

**Skip if already done**: if `sqlite3 daas.db "SELECT name FROM indicator_rules WHERE name='<name>'"` returns a row and the `scraw_<slug>` table exists, skip and tell the user.

## Step 5 - Delegate to fd-daas-dashboard-creator

- Invoke `fd-daas-dashboard-creator` with the indicator names + `scraw_<slug>` table(s) + dashboard shape. If step 3 produced a collection, pass its name for labeling.
- Wait for it to finish.

**Skip if already done**: if `dashboards/daas.md` already lists a dashboard for this plan, skip and tell the user.

## Gotchas

- **This skill orchestrates; it does not write `scraw_*` tables, rule scripts, or HTML itself.** All state-mutating work happens in the delegated skills.
- **The collection step is group-only.** Don't force a collection on single-entity research.
- **No cron.** The indicators-creator no longer schedules refresh - refresh is manual. Don't promise scheduled refresh to the user.
- **Pass context forward explicitly** - the membership rule, the entity_id + identifier_in_source + indicator specs, the `scraw_<slug>` table names + collection name.
- **Skip-if-already-done**: check `entity_collections` + `indicator_rules` + `scraw_*` tables + `dashboards/daas.md` before each delegation.
