## Context

This change adds five agent skills under `.claude/skills/` that orchestrate the project's existing MCP surface (`daas-mcp`, `cron-mcp`, `leader-mcp`, `dashboard-mcp`) into end-to-end workflows. The MCP tools already exist and are documented in `CLAUDE.md`; the gap is workflow-level guidance — which tool to call, in what order, with which gotchas in mind.

Skill conventions are established by `fd-skill-creator` (`/Users/chengsishi/code/cli-anything/.claude/skills/fd-skill-creator/SKILL.md`) and the existing `fd-daas-*` skills:

- Project scope: skills live at `.claude/skills/<name>/SKILL.md`.
- YAML frontmatter: `name` + a pushy `description` (the primary trigger mechanism) with explicit English + Chinese trigger phrases.
- Body: imperative instructions, < 500 lines, references to bundled `scripts/` / `references/` only when a file would otherwise be repeated every invocation.
- Skills compose: `fd-daas-research` delegates to `fd-daas-indicators-creator` + `fd-daas-dashboard-creator`; `fd-daas-indicators-creator` builds on `fd-daas-fetch-data`.

The daas MCP surface these skills drive:

- **Entity → datasource coverage**: `search_entities`, `get_entity`, `list_entities`, `get_entity_coverage` (returns `identifier_in_source` + sections + column hints per linked source).
- **Indicators**: `create_indicator` / `run_indicator` (persists a binding + writes the `observations` table); `calculate` (ad-hoc, no persist). Indicator rules accept any table in `daas.db`, not only `scraw_*`.
- **Pipeline collections** (managed fetch + cron): `create_pipeline_collection` → `add_pipeline_item` (binds `source_mcp` + `tool` + `arguments_json` → `scraw_<slug>` storage table + upsert keys + cron cadence; **enabling an item triggers an immediate backfill** and an idempotent cron-mcp `create_task` + `create_schedule`). `enable_pipeline_item` / `disable_pipeline_item` / `update_pipeline_item` / `sync_pipeline_cron`.
- **Workflows** (leader-mcp): `build_workflow_from_goal` (LLM decomposes a goal into specialist-agent steps; falls back to a deterministic single-step workflow without an LLM), `create_workflow` + `add_workflow_step` (manual), `run_workflow` / `run_workflow_step`, `get_workflow_run`.
- **Dashboard**: the Next.js app at `dashboard/` (sql.js + MCP-tools wiring via `getMCPTools()`).

## Goals / Non-Goals

**Goals:**

- Ship five skills that each drive a complete workflow end-to-end without the user having to remember the tool sequence.
- Each skill composes cleanly with the others (research → indicators-creator + dashboard-creator; indicators-creator → fetch-data).
- Each `description` is pushy enough to reliably trigger on both English and Chinese phrasings of the intent, including near-miss cases.
- Each skill encodes the gotchas that bit previous manual runs (e.g. `create_datasource` writes `sources` not `datasources`; enabling a pipeline item backfills immediately; `build_workflow_from_goal` falls back when no LLM is configured).
- Skills are testable: each spec scenario maps to a verifiable outcome.

**Non-Goals:**

- **No new MCP tools.** The skills consume the existing `daas-mcp` / `cron-mcp` / `leader-mcp` / `dashboard-mcp` tools. If a workflow needs a tool that does not exist, the skill surfaces the gap to the user rather than inventing one.
- **No schema or DB changes.** `mcp/daas.db` is touched only through existing tools.
- **No user-scope skills.** All five live in `.claude/skills/` (project scope), per `fd-skill-creator`.
- **No skill eval harness in this change.** Test prompts and the `fd-skill-creator` eval loop are run during `/opsx:apply` (or ad-hoc), but the eval workspace is not shipped as part of the change.
- **No reimplementation of `fd-skill-creator`.** These five are content skills; the meta-skill stays as-is.

## Decisions

### D1: One capability per skill (5 specs), not one bundled spec

Each skill is independently invokable and has a distinct workflow + tool set. Five focused specs keep the requirement→scenario→test mapping clean and let `/opsx:apply` implement them in any order. A bundled spec would couple unrelated workflows and make deltas harder.

*Alternative considered*: a single `fd-daas-skills` capability with five requirement groups. Rejected because the skills compose rather than share behavior, and a single spec would force one set of scenarios to cover five unrelated flows.

### D2: Skills reference MCP tools by their exact `mcp__<server>__<tool>` names

Each skill's body names the tools it calls verbatim (e.g. `mcp__daas-mcp__get_entity_coverage`, `mcp__daas-mcp__add_pipeline_item`). This makes the skill self-documenting and lets the model confirm tool availability via `ToolSearch` before calling. No Python/TS wrapper scripts are introduced unless a step would otherwise require copying the same multi-line sequence across skills — none qualify in this change.

### D3: Pushy `description` with EN + ZH trigger phrases, mirroring `fd-daas-scrapling-scraw-creator`

Per `fd-skill-creator`, Claude under-triggers skills, so each description explicitly lists trigger phrases in both languages and names the near-miss cases where the skill should *not* fire (e.g. `fd-daas-fetch-data` should win over `fd-daas-scrapling-scraw-creator` when the user wants an indicator over an existing entity, not a new scrape).

### D4: `fd-daas-fetch-data` is the foundation; `fd-daas-indicators-creator` reuses it rather than duplicating

`fd-daas-indicators-creator` step 1 is "use the `fd-daas-fetch-data` skill." The indicators-creator skill therefore documents the handoff (steps 1–3 already done) and continues at step 4. This preserves the intentional `1, 4, 5, 6` numbering from `skill-demand.md`.

### D5: `fd-daas-dashboard-creator` — standalone HTML, no Next.js route

Resolved with the user (was apply-time Q1 + Q2):

1. **Propose structure** as markdown (charts/tables, source data, refresh cadence) and ask permission.
2. **Build** a single standalone HTML file at `dashboard/my-charts-dashboard/<slug>.html` — **no Next.js route, no `dashboard/src/app/...` page, no new dashboard app.** The HTML is self-contained: inline the fetched data + a chart lib via CDN (or static tables). The existing Next.js `dashboard/` app is left untouched.
3. **Open** via `open <url>` (macOS — the project host is darwin).
4. **Register the page-url** in two places (this replaces the original "persist to daas.db" idea — no DB row):
   - `dashboard/my-charts-dashboard/index.html` — the "charts page" index that links to every `<slug>.html`.
   - `dashboard/my-charts-dashboard/daas.md` — a markdown list of all dashboard page-urls (same set as the index, in markdown form, so it's diff-friendly and readable outside a browser).

Rollback is `rm -rf dashboard/my-charts-dashboard/`. No `mcp/daas.db` persistence target is used for dashboards.

### D6: `fd-daas-workflow-creator` prefers `build_workflow_from_goal`, falls back to manual construction

The skill first tries `mcp__leader-mcp__build_workflow_from_goal(goal, name?, description?, model="fast")` — **default tier is `fast`** (resolved with the user, was Q3), since the workflow is a data-fetch pipeline, not a reasoning-heavy task; the user can override to `balance` / `high` for harder decompositions. When the leader-mcp LLM is unconfigured (the deterministic single-step fallback kicks in), or when the user wants explicit control over steps, the skill falls back to `create_workflow` + `add_workflow_step` per step, then `run_workflow` to execute. The skill explains *why* the fallback exists (no LLM → deterministic direct router keeps data flowing) so the model chooses correctly rather than blindly retrying.

### D7: No bundled scripts or references in v1

Each skill stays under 500 lines and inlines its workflow. If a skill grows past that (e.g. `fd-daas-dashboard-creator` accumulates template snippets), it gets a `references/` file with a TOC at that point — not preemptively.

## Risks / Trade-offs

- **[Dashboard-creator ambiguity]** → The demand text is the loosest of the five. Mitigation: D5 documents the assumption explicitly; the spec scenario for "persist URL" is written so it can be satisfied by either a daas.db row or a dashboard config file — the apply step confirms the target with the user before generating code.
- **[Skill drift when MCP tools change]** → Skills hardcode `mcp__<server>__<tool>` names. If a tool is renamed, the skill silently breaks at run time. Mitigation: each skill's first step is a tool-availability check via `ToolSearch`; the spec scenario "MCP tool missing" requires a clear user-facing error, not a silent failure.
- **[Description over-triggering]** → Pushy descriptions can fire on near-misses (e.g. `fd-daas-fetch-data` firing when the user just wants `search_functions`). Mitigation: each description names the cases where it should *not* fire and which sibling skill should win.
- **[Composition depth]** → `research` → `indicators-creator` → `fetch-data` is three skills deep. Each handoff must pass context (which entities, which indicators already created) explicitly. Mitigation: each composing skill's first step is "read what the prior skill already did" and skips completed steps (mirrors the `fd-daas-indicators-creator` "if 1–3 already done, run 4–6" rule).
- **[LLM-dependent fallbacks]** → `build_workflow_from_goal` and `ask_data_crew` fall back to deterministic paths when no LLM is configured. The skills must not treat the fallback as an error. Mitigation: skills explain the fallback in the body and proceed through it.

## Migration Plan

No migration — these are net-new files. Rollback is `rm -rf .claude/skills/fd-daas-{fetch-data,indicators-creator,dashboard-creator,research,workflow-creator}/`.

## Open Questions

<!-- Q1, Q2, Q3 resolved with the user during /opsx:propose:
     - Q1 + Q2 (dashboard-creator): single standalone HTML at dashboard/my-charts-dashboard/<slug>.html;
       page-urls registered in dashboard/my-charts-dashboard/index.html + daas.md; no Next.js route, no daas.db row. See D5.
     - Q3 (workflow-creator default tier): fast. See D6.
     No outstanding questions. -->
