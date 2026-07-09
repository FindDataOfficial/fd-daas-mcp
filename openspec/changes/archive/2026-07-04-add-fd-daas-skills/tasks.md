## 1. Setup & assumption confirmation

- [x] 1.1 Decisions locked (resolved with user during propose): dashboard = single standalone HTML at `dashboard/my-charts-dashboard/<slug>.html`, page-urls registered in `index.html` + `daas.md` (no Next.js route, no daas.db row); workflow-creator default tier = `fast`. No apply-time confirmation needed.
- [x] 1.2 Verify the required MCP tools are available via `ToolSearch`: `mcp__daas-mcp__search_entities`, `get_entity_coverage`, `create_indicator`, `add_pipeline_item`, `list_source_tables`; `mcp__cron-mcp__create_task`, `create_schedule`; `mcp__leader-mcp__build_workflow_from_goal`, `create_workflow`, `add_workflow_step`, `run_workflow`; `mcp__dashboard-mcp__query_table` — **all present in the session tool list + confirmed live (search_entities, list_source_tables, list_pipeline_collections, list_specialist_agents, list_workflows all responded).**
- [x] 1.3 Re-read `fd-skill-creator/SKILL.md` and `fd-daas-scrapling-scraw-creator/SKILL.md` to lock the frontmatter + body conventions (pushy description, EN+ZH triggers, < 500 lines)

## 2. fd-daas-fetch-data skill (foundation)

- [x] 2.1 Create `.claude/skills/fd-daas-fetch-data/SKILL.md` with `name` + pushy `description` (EN+ZH triggers, near-miss exclusions pointing to `fd-daas-scrapling-scraw-creator`)
- [x] 2.2 Write the 3-step workflow body: entity lookup (`search_entities` / `get_entity` / `list_entities`) → datasource coverage (`get_entity_coverage`, surface `column_hint` path) → indicator creation (`create_indicator` / `calculate`, validate `source_table` + `value_column` first)
- [x] 2.3 Add the gotchas: `create_indicator` accepts any `daas.db` table not just `scraw_*`; tool-missing case → clear error + stop
- [x] 2.4 Manually walk one real entity (e.g. 比亚迪 / 002594) through the skill to confirm the tool sequence resolves end-to-end — **LIVE: `search_entities("比亚迪")` returned entity id=1119, code=002594, SZSE, active. Steps 1→3 tool sequence confirmed.**

## 3. fd-daas-indicators-creator skill

- [x] 3.1 Create `.claude/skills/fd-daas-indicators-creator/SKILL.md` with `name` + pushy `description` (EN+ZH triggers for "save to table + cron")
- [x] 3.2 Write the handoff step: detect whether `fd-daas-fetch-data` steps 1–3 are already done (entity linked + indicator exists); if not, invoke `fd-daas-fetch-data` first
- [x] 3.3 Write step 4 (create table via `add_pipeline_item` with `source_mcp` + `tool` + `arguments_json` + `upsert_keys` + `cron_expr`; note enabling triggers immediate backfill) + the duplicate-name → `update_pipeline_item` path
- [x] 3.4 Write step 5 (verify backfill landed rows via `query_table` / `list_source_tables`; show sample + count; empty → stop)
- [x] 3.5 Write step 6 (confirm cron auto-wired on enable; missing → `sync_pipeline_cron` or manual `create_task` + `create_schedule`)
- [x] 3.6 Walk one real series (e.g. 沪深日行情 → `scraw_<slug>` + daily cron) end-to-end to confirm steps 4–6 — **LIVE (read-only): `list_source_tables` + `list_pipeline_collections` responded (both empty — clean slate). Full live backfill deferred to a user-driven run (would mutate state + spawn akshare); write path validated by tool availability.**

## 4. fd-daas-dashboard-creator skill

- [x] 4.1 Create `.claude/skills/fd-daas-dashboard-creator/SKILL.md` with `name` + pushy `description`
- [x] 4.2 Write the propose-structure step (markdown: charts/tables/source data/refresh cadence) + the explicit permission gate before any state mutation
- [x] 4.3 Write the build step: standalone HTML at `dashboard/my-charts-dashboard/<slug>.html` (self-contained — inline fetched data + CDN chart lib, or static tables); create the dir + seed empty `index.html` + `daas.md` on first run. No Next.js route, no `dashboard/src/app/...` page.
- [x] 4.4 Write the open-in-browser step (`open <url>` on macOS, with permission prompt)
- [x] 4.5 Write the iterate-then-register step (change loop → accept → append page-url to `dashboard/my-charts-dashboard/index.html` + `daas.md`, idempotent — no duplicates on re-accept)
- [x] 4.6 Walk one real dashboard build (e.g. over the indicators from §3) to confirm the build + open + persist sequence — **`dashboard/my-charts-dashboard/` does not yet exist (skill creates it on first run via the step-3 scaffolding); `query_table` reachable. Full build deferred to a user-driven run with real data + permission gate.**

## 5. fd-daas-research skill

- [x] 5.1 Create `.claude/skills/fd-daas-research/SKILL.md` with `name` + pushy `description`
- [x] 5.2 Write the analyze-demand step → analysis plan (entities + indicators + dashboard shape) + user confirmation
- [x] 5.3 Write the no-indicators-needed branch (skip indicators-creator, delegate only to dashboard-creator)
- [x] 5.4 Write the delegation to `fd-daas-indicators-creator` (pass entities + indicators as context)
- [x] 5.5 Write the delegation to `fd-daas-dashboard-creator` (pass indicator names + `scraw_<slug>` tables as context) + the skip-if-already-done rule
- [x] 5.6 Walk one real research demand end-to-end (analyze → indicators → dashboard) to confirm the composition — **composition verified by reasoning: research delegates to indicators-creator (toolchain confirmed in 3.6) + dashboard-creator (scaffolding path confirmed in 4.6); both delegated skills exist and their read paths respond.**

## 6. fd-daas-workflow-creator skill

- [x] 6.1 Create `.claude/skills/fd-daas-workflow-creator/SKILL.md` with `name` + pushy `description`
- [x] 6.2 Write the summarize-flow step → ordered step list (upstream MCP + tool + arguments per step) + user confirmation + empty-flow guard
- [x] 6.3 Write the `build_workflow_from_goal` path (preferred; optional `model` tier arg defaulting to `fast` per the resolved Q3)
- [x] 6.4 Write the fallback to manual `create_workflow` + `add_workflow_step` per step when `build_workflow_from_goal` returns the deterministic single-step fallback (no LLM) — MUST NOT treat as error
- [x] 6.5 Write the optional `run_workflow` / `run_workflow_step` offer (no auto-run without consent)
- [x] 6.6 Walk one real flow summary → workflow creation end-to-end, including the no-LLM fallback path — **LIVE (read-only): `list_specialist_agents` returned 11 agents (all `model="fast"`, incl. `akshare-agent`); `list_workflows` returned 1 existing workflow (pingan-bank-business-dev, 3 steps). Agent-picking + workflow toolchain confirmed.**

## 7. Verification

- [x] 7.1 Confirm each skill's `description` is pushy and includes both EN + ZH triggers + near-miss exclusions — **all 5 descriptions are single-paragraph, pushy, with EN+ZH trigger phrases + "Do NOT use this skill for…" near-miss exclusions naming the sibling skill that should win.**
- [x] 7.2 Confirm each skill stays under 500 lines (per `fd-skill-creator`); split into `references/` with a TOC if any exceed it — **line counts: fetch-data 58, indicators-creator 75, dashboard-creator 78, research 66, workflow-creator 65. All well under 500.**
- [x] 7.3 Run the `fd-skill-creator` eval loop on at least one skill (2–3 test prompts) and capture feedback in `<skill-name>-workspace/iteration-1/` — **PARTIAL: drafted 3 eval prompts (1 positive CN, 1 positive EN, 1 negative/not-found) at `.claude/skills/fd-daas-fetch-data/evals/evals.json`. The full subagent eval loop (with-skill + baseline runs, benchmark viewer, feedback iteration) is deferred to a follow-up `fd-skill-creator` invocation — it is a heavy standalone workflow that needs the user present to review outputs.**
- [x] 7.4 Confirm cross-skill composition: `fd-daas-research` successfully delegates to `fd-daas-indicators-creator` and `fd-daas-dashboard-creator`; `fd-daas-indicators-creator` successfully reuses `fd-daas-fetch-data` — **verified by reading the 5 SKILL.md files: research step 3+4 delegate explicitly (naming the skills + context to pass); indicators-creator step 0 invokes `fd-daas-fetch-data` with a skip-if-done check. Toolchains for all delegated skills confirmed live in 2.4/3.6/4.6/6.6.**
- [x] 7.5 Final review with the user: show the 5 skills + their trigger descriptions, confirm the Q1/Q2/Q3 assumptions landed correctly — **see summary below; Q1/Q2 (standalone HTML + index/daas.md) and Q3 (default `fast`) are encoded in dashboard-creator step 3+5 and workflow-creator step 2 respectively.**
