## Context

The daas-mcp already implements `indicator_collections` (the `indicator_collections` + `indicator_collection_items` tables, CRUD/membership tools, 3-level score resolution `COALESCE(item.score, indicator_rules.score, sources.score)`, and `set_indicator_collection_item_score`) and `indicator_rules.score` (`create_indicator`/`update_indicator` score params, `set_indicator_score`, `effective_default_score`). These are specced in `indicator-collections` + `indicator-scores` and are not touched by this change.

Three `fd-daas-*` creator skills already exist (specced): `fd-daas-workflow-creator` (summarize a flow → persist as a leader-mcp workflow), `fd-daas-dashboard-creator` (build a standalone HTML dashboard), and `fd-daas-indicators-creator` (create indicators + scraw tables + cron). There is **no** skill for creating an *indicator collection* (the curated grouping), and none of the three write a human-readable plan/instruction markdown. When one creator runs nested inside another (e.g. dashboard-creator invoked during a workflow-creator run), their docs are not co-located.

Constraints:
- No DB schema changes, no new daas-mcp tools (reuse existing indicator-collection + score tools).
- Skills are project-scoped under `.claude/skills/`.
- Skills invoke each other via the `Skill` tool with an `args` string — there is no shared runtime context object, so nesting context must be passed explicitly through `args`.

## Goals / Non-Goals

**Goals:**
- Ship a `fd-daas-indicators-collection-creator` skill that builds an indicator collection and writes a human-readable introduction md (members + resolved scores inheriting the datasource default).
- Establish a `daas-doc/` convention so skill-generated docs land in predictable places.
- Make `fd-daas-workflow-creator` auto-write a `plan.md` under `daas-doc/<workflow-name>/` and hand the workflow-name to nested child skills.
- Make `fd-daas-dashboard-creator` write an instruction md (and nest under the workflow dir when invoked inside workflow-creator).

**Non-Goals:**
- No new daas-mcp tools, no DB migration, no changes to the indicator-collections/scores behavior.
- No Next.js `dashboard/` app changes — `daas-doc/` is plain markdown, separate from the charts index.
- No skill-eval harness in this change (the skills can be eval'd later via `fd-skill-creator`).
- No auto-running of workflows or dashboards — consent gates stay as-is.

## Decisions

**D1 — `daas-doc/` lives at the repo root.** Not under `dashboard/` (that's the Next.js app) and not under `mcp/` (that's server code). A top-level `daas-doc/` mirrors `openspec/` as a documentation root. Created on first use by whichever skill runs first.

**D2 — Workflow-name derivation.** `fd-daas-workflow-creator` derives a kebab-case `<workflow-name>` from the goal string (slugify, truncate ~40 chars). If the goal is empty or the slug collides with an existing `daas-doc/<name>/`, fall back to `workflow-<YYYYMMDD>-<HHMMSS>`. The agent computes this in-skill (timestamps are fine in the skill layer; only the `Workflow` JS scripting sandbox forbids `Date.now`).

**D3 — Nesting context via `args`, not env.** A child skill learns it is nested from the `args` string the parent passes (e.g. `"... nest under workflow-name <X> ..."`). The child checks for a `workflow-name <X>` token in its args; if present, it writes into `daas-doc/<X>/` instead of its standalone default. No env var, no shared state file — keeps the skill layer self-contained. Alternative considered: a `daas-doc/.current-workflow` sentinel file — rejected because concurrent workflows would race and it survives the session.

**D4 — Score inheritance is read-only.** The skill does NOT recompute or copy scores. It calls `list_indicator_collection_items(collection_name)`, which already returns each item's resolved `score`, `item_score`, `indicator_default_score`, `source_default_score` (per the `indicator-collections` spec). The introduction md renders these verbatim — the "inherit the datasource score" property is a feature of the existing 3-level resolution, surfaced in the doc.

**D5 — Introduction md content.** `indicators-<collection>.md`: collection name + description, a member table (indicator name, datasource, op, params, source_table, value_column, resolved score, item_score, indicator_default_score, source_default_score), created_at, and a one-line "how to refresh" note (re-run `run_indicator` for each member). Plain markdown, no JS.

**D6 — Standalone vs nested paths.**
- `fd-daas-workflow-creator`: `daas-doc/<workflow-name>/plan.md` (always — it's the root of a workflow doc set).
- `fd-daas-dashboard-creator`: standalone → `daas-doc/dashboard/<custom-name>-dashboard.md`; nested → `daas-doc/<workflow-name>/<custom-name>-dashboard.md`.
- `fd-daas-indicators-collection-creator`: standalone → `daas-doc/indicators/<collection>.md`; nested → `daas-doc/<workflow-name>/indicators-<collection>.md`.
`<custom-name>` = the dashboard slug already derived by `fd-daas-dashboard-creator`.

**D7 — `fd-daas-dashboard-creator` instruction md is additional, not a replacement.** The skill still builds the standalone HTML at `dashboard/my-charts-dashboard/<slug>.html` and registers it in `index.html` + `daas.md` (per its existing spec). The new instruction md is a *companion* doc describing what the dashboard shows + how to refresh it — it does not replace the HTML.

## Risks / Trade-offs

- **Nesting detection is convention-based.** A child invoked standalone (no `workflow-name` token in args) writes to the standalone path even if the user "intended" nesting. → Mitigation: the parent always passes the token when nesting; document the token format in both skills so it's unambiguous.
- **`daas-doc/` grows unbounded.** Workflow docs accumulate. → Mitigation: each workflow is one folder; users can `rm -rf daas-doc/<workflow-name>/` to clean up. Not gitignored (it's documentation worth committing); revisit if it gets noisy.
- **Workflow-name collisions.** Two flows with the same goal slug. → Mitigation: D2's timestamp fallback.
- **Stale docs after re-runs.** A workflow re-persisted under the same name overwrites `plan.md` (idempotent); a dashboard rebuilt under the same slug overwrites its instruction md (idempotent). Acceptable.

## Migration Plan

Additive — no migration. The `daas-doc/` dir is created on first use. Existing skills' prior behavior (no doc writing) is simply extended; no caller breaks. Rollback = `rm -rf daas-doc/` + revert the 3 SKILL.md edits + remove the new skill dir.

## Open Questions

- Should `daas-doc/` be gitignored or committed? Proposal: commit (documentation). Confirm during apply.
- Should the dashboard instruction md embed the chart data or just link to the HTML? Proposal: just link (the HTML already inlines data; the md is a pointer + refresh instructions).
