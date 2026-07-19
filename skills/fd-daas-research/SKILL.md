---
name: fd-daas-research
description: Orchestrate a full daas research workflow - analyze a natural-language demand into a plan, build the components (entity collection, indicators, dashboard) via the fd-daas-* creator skills, then PERSIST the whole study as a `research` bundle and generate a markdown report using the `research_*` MCP tools. Use this skill whenever the user gives a research-style demand that needs indicators and a dashboard - phrases like "帮我研究一下比亚迪，做指标和看板", "research TSLA - build indicators and a dashboard", "研究一下沪深300成分股做个看板", "research SSE banks - set up indicators and a dashboard", "分析这只股票并做个可视化", or any entity + "research / 分析 / 研究 / full pipeline". When the demand names a group (a watchlist, a rule like "SSE banks", or an explicit list of codes), this skill first delegates to fd-daas-entities-collection-creator to persist the group before building indicators over its members. On a repeat demand whose research already exists, this skill REFRESHES it (`research_refresh`) and regenerates the report instead of rebuilding from scratch. Do NOT use this skill if the user only wants indicators (use fd-daas-indicators-creator) or only a dashboard (use fd-daas-dashboard-creator) or a one-shot fetch (use fd-daas-fetch-data) or only an entity collection (use fd-daas-entities-collection-creator); this skill orchestrates the full analyze -> [collection] -> indicators -> dashboard -> research-bundle flow. Uses sqlite3 for plan context and the `research_*` MCP tools to persist/refresh/report the bundle.
---

# fd-daas-research

Analyze a demand -> produce a plan (naming a `research` handle) -> build components via the `fd-daas-*` creator skills -> **persist the study as a `research` bundle** (`research_create`) -> **generate a markdown report** (`research_generate_report`). On a repeat run, **refresh** (`research_refresh`) + regenerate the report. This is the top-level orchestration skill; it reads context via **`sqlite3`** for the plan and mutates bundle/report state through the **`research_*`** MCP tools.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` points at the DB (currently `sqlite:///daas.db`). From the repo root, `sqlite3 daas.db "..."` works.

## Mental model

1. **Analyze the demand** -> a plan naming: a `research` name (the bundle handle), entities (or a group/rule), indicators, and dashboard shape. Get user confirmation.
2. **Build the entity collection** (group demands only) - delegate to `fd-daas-entities-collection-creator`.
3. **Build indicators** - delegate to `fd-daas-indicators-creator` (table + save; no cron).
4. **Build the dashboard** - delegate to `fd-daas-dashboard-creator`.
5. **Persist the research bundle** - `research_create` referencing the entity collection name, indicator collection name, dashboard slug, (optional) pipeline collection name, and rule/scraw refs.
6. **Generate the report** - `research_generate_report`; surface the returned `report_path` to the user.

## Step 1 - Analyze the demand

1. Parse the demand for: a **research name** (derive a kebab/snake handle, e.g. `byd-trend` or `sse_banks`), the entity **or a group** (watchlist, rule, or code list), the time range, the indicators implied (price -> SMA/EMA/RSI; fundamentals -> ratios/growth; macro -> level/pct_change), and the dashboard shape.
2. Read context via `sqlite3`:
   - Confirm the entity exists: `sqlite3 daas.db "SELECT id, name, ticker FROM entities WHERE name LIKE '%<term>%' OR ticker LIKE '%<term>%'"`
   - Coverage: `sqlite3 daas.db "SELECT s.name, l.identifier_in_source, f.name FROM entity_datasource_links l JOIN sources s ON s.id=l.source_id JOIN daas_functions f ON f.source_id=s.id WHERE l.entity_id=<id>"`
   - Indicator ops: `uv run --with pandas --with numpy python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --list-ops`
   - Existing collections (group demands): `sqlite3 daas.db "SELECT name, description FROM entity_collections"`
   - Existing researches (repeat-run detection): `sqlite3 daas.db "SELECT name, status FROM researches WHERE name='<research_name>'"`
   - Prior brainstorm plans: `ls daas-doc/research/*.md 2>/dev/null` - read any whose handle matches the demand and pre-fill the plan (see "Prior brainstorm plan" below)
3. Draft the plan as markdown: **Research name**, **Entities** (name + id + `identifier_in_source`) **or Collection** (name + membership rule), **Indicators** (name, op, params, `source_table`, `value_column`), **Dashboard shape**, **Skip flags**.
4. Show the plan and ask: "Does this plan look right? I'll build the components, then create the research `<name>` and generate its report."

### Repeat-run shortcut

If `researches` already has a row for `<research_name>`, skip steps 2-4 and go straight to **Step 7 - Refresh**: call `research_refresh(name="<research_name>")` then `research_generate_report(name="<research_name>")`, and tell the user the study was refreshed rather than rebuilt.

### Prior brainstorm plan

If a `daas-doc/research/<plan-slug>.md` exists that matches the demand (same entity/group + lens), read it and pre-fill the analysis plan - the research name, entities, indicators implied by the lens, and dashboard shape - instead of deriving them from scratch. Tell the user you are building from the brainstorm plan and confirm before proceeding. This does NOT skip the build (the research does not exist yet) - it only pre-fills Step 1's plan.

## Step 2 - No-indicators branch

If dashboard-only (no new indicators/tables needed), skip the indicators delegation and go straight to `fd-daas-dashboard-creator`. A group demand can still go through the collection step first. Tell the user why you skipped.

## Step 3 - Build entity collection (group demands only)

- Invoke `fd-daas-entities-collection-creator` with the collection name + membership rule.
- Wait for it to finish, then collect the collection name + member codes/ids for step 4.

**Skip if not a group demand**: single entity -> go straight to step 4.
**Skip if already done**: if `sqlite3 daas.db "SELECT name FROM entity_collections WHERE name='<name>'"` returns a row, skip and tell the user.

## Step 4 - Build indicators

- Invoke `fd-daas-indicators-creator` with the entities (id + `identifier_in_source`), indicators (name, op, params, `source_table`, `value_column`).
  - For a collection, iterate per member. For a large collection, pick a lead member for the indicator+dashboard and note the collection name as the universe.
  - Ask the indicators-creator to also create/attach an **indicator collection** (so the research can reference it and refresh it).
- The indicators-creator skill runs its steps (reusing `fd-daas-fetch-data` for the fetch, then table + save; **no cron**).
- Wait, then collect the `scraw_<slug>` table name(s), indicator names, and the indicator collection name.

**Skip if already done**: if `sqlite3 daas.db "SELECT name FROM indicator_rules WHERE name='<name>'"` returns a row and the `scraw_<slug>` table exists, skip and tell the user.

## Step 5 - Build dashboard

- Invoke `fd-daas-dashboard-creator` with the indicator names + `scraw_<slug>` table(s) + dashboard shape. If step 3 produced a collection, pass its name for labeling.
- Wait for it to finish, then collect the **dashboard slug**.

**Skip if already done**: if `dashboards/daas.md` already lists a dashboard for this plan, skip and tell the user.

## Step 6 - Persist the research bundle + generate report

After the components exist, persist the study and generate its report with the `research_*` MCP tools:

1. **Create the bundle** - `research_create`:
   - `name` = the research handle from the plan
   - `entity_collection_name` = the collection name from step 3 (if any)
   - `indicator_collection_name` = the indicator collection name from step 4
   - `dashboard_slug` = the slug from step 5
   - `pipeline_collection_name` = the pipeline collection name if cron fetches were set up (else omit)
   - `component_refs` = JSON string `{"rules": [...], "scraw_tables": ["scraw_<slug>", ...], "indicators": [...]}`
   - `create_missing=True` if you want the tool to scaffold any missing empty collections
   - If the research already exists, use `research_update` (or `research_add_component`) to attach the new components instead of recreating.
2. **Generate the report** - `research_generate_report(name="<research_name>")`. It writes `researches/<name>.md` and stores the markdown in the `researches` row.
3. **Surface the result** - tell the user the research name + the returned `report_path` (and the dashboard `file_url` from `research_get`).

To re-attach a component later (e.g. a new dashboard or rule), use `research_add_component(name, component_type, component_name)`.

**Run-notification (create path)** - emit this block at the end of Step 6:

    ## Run Complete
    **Skill:** fd-daas-research
    **Status:** created + reported
    **Produced:** research `<name>` -> `researches/<name>.md`; dashboard <file_url>
    **Next:** re-run anytime to refresh (`research_refresh`); ask me to tweak indicators.

## Step 7 - Refresh (repeat runs)

When the user re-issues a demand whose research already exists, do NOT rebuild components. Instead:

1. `research_refresh(name="<research_name>")` - recomputes every indicator in the indicator collection (via `daas_run_indicator`), syncs rule-based collections, and reports each pipeline item's status.
2. `research_generate_report(name="<research_name>")` - regenerates the markdown report with the updated latest values.
3. Surface the refreshed `report_path`.

**Run-notification (refresh path)** - emit this block at the end of Step 7:

    ## Run Complete
    **Skill:** fd-daas-research
    **Status:** refreshed + reported
    **Produced:** updated `researches/<name>.md` (latest values recomputed)
    **Next:** re-run anytime to refresh again.

## Gotchas

- **This skill orchestrates; it does not write `scraw_*` tables, rule scripts, or HTML itself.** Component building happens in the delegated creator skills; the `research_*` tools only bundle, persist, report, and refresh.
- **The collection step is group-only.** Don't force a collection on single-entity research.
- **No cron by default.** Indicators refresh on demand via `research_refresh`, not on a schedule. Only set `pipeline_collection_name` if a cron fetch pipeline was explicitly created.
- **Pass context forward explicitly** - the membership rule, the entity_id + identifier_in_source + indicator specs, the `scraw_<slug>` table names + collection name + dashboard slug + indicator rule names, all into `research_create`/`component_refs`.
- **Skip-if-already-done**: check `entity_collections` + `indicator_rules` + `scraw_*` tables + `dashboards/daas.md` before each delegation, and check `researches` for the bundle before creating vs. refreshing.
- **Auto-detect before building.** Before analyzing, list `daas-doc/research/*.md` (prior brainstorm plans) and `SELECT name, status FROM researches` (existing bundles). A matching research -> refresh (Step 7); a matching plan -> pre-fill Step 1; neither -> build fresh. Always emit the run-notification block (create or refresh) at the end.
- **Dangling refs are reported, not fatal** - `research_get` lists any attached component that no longer exists under `dangling`; re-attach or remove with `research_add_component`/`research_remove_component`.
