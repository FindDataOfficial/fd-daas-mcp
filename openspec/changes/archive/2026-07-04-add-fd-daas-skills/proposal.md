## Why

The daas MCP surface is broad — entities, datasource coverage, indicators, pipeline collections, dashboards, workflows — and each end-to-end task requires a specific tool sequence with non-obvious gotchas (e.g. `create_datasource` writes the `sources` table, not the legacy `datasources` table; indicator rules accept any table but `create_rule` validates `scraw_<slug>` existence first; pipeline items trigger an immediate backfill on enable). Today a user must rediscover the right tool for each step and the correct order every session. These five `fd-daas-*` skills codify the proven sequences so Claude can drive each workflow end-to-end without re-deriving it, composing into each other (`research` orchestrates `indicators-creator` + `dashboard-creator`; `indicators-creator` builds on `fetch-data`).

## What Changes

- **Add** `.claude/skills/fd-daas-fetch-data/` — a skill that drives the entity → datasource-coverage → indicator workflow using `search_entities` / `get_entity_coverage` / `create_indicator`.
- **Add** `.claude/skills/fd-daas-indicators-creator/` — a skill that extends `fd-daas-fetch-data` with the table/save/cron steps: `add_pipeline_item` (creates `scraw_<slug>` + backfills) → `enable_pipeline_item` → `cron-mcp` `create_task` + `create_schedule`.
- **Add** `.claude/skills/fd-daas-dashboard-creator/` — a skill that proposes a dashboard layout as text, asks permission, builds the dashboard, offers to open it in the default browser, and persists the dashboard URL. Iterates on user changes before saving.
- **Add** `.claude/skills/fd-daas-research/` — a skill that analyzes a demand, produces an analysis plan + indicator demand, then delegates to `fd-daas-indicators-creator` and `fd-daas-dashboard-creator`.
- **Add** `.claude/skills/fd-daas-workflow-creator/` — a skill that summarizes an executed flow and persists it as a leader-mcp workflow via `build_workflow_from_goal` / `create_workflow` + `add_workflow_step`.
- **No MCP code changes** — the skills only consume existing tools on `daas-mcp`, `cron-mcp`, `leader-mcp`, and `dashboard-mcp`. No new MCP tools, no schema changes.

## Capabilities

### New Capabilities

- `fd-daas-fetch-data`: Drive the entity → datasource-coverage → create-indicator workflow end-to-end via the daas-mcp entity + indicator tools.
- `fd-daas-indicators-creator`: Extend the fetch-data workflow with `scraw_<slug>` table creation, data persistence, and a refresh cron (daas-mcp pipeline collections + cron-mcp).
- `fd-daas-dashboard-creator`: Propose, build, preview, iterate, and persist a dashboard for daas data, with an explicit permission gate before each outward-facing step.
- `fd-daas-research`: Analyze a natural-language demand into an analysis plan + indicator demand, then orchestrate the indicators-creator and dashboard-creator skills.
- `fd-daas-workflow-creator`: Summarize a completed multi-step flow and persist it as a resumable leader-mcp workflow.

### Modified Capabilities

<!-- None. The skills only orchestrate existing MCP capabilities (daas-indicators, pipeline-collections, workflow-builder, etc.); they do not change the spec-level behavior of any existing capability. -->

## Impact

- **Code**: 5 new directories under `.claude/skills/` (each a `SKILL.md` plus optional `scripts/` / `references/`). No changes to `mcp/` or `dashboard/`.
- **APIs / dependencies**: Skills call existing MCP tools — `mcp__daas-mcp__*` (entities, indicators, pipeline collections), `mcp__cron-mcp__create_task` / `create_schedule`, `mcp__leader-mcp__build_workflow_from_goal` / `create_workflow` / `add_workflow_step`, `mcp__dashboard-mcp__*`. No new tools required.
- **Assumptions** (resolved with the user during `/opsx:propose`):
  - `fd-daas-dashboard-creator` — each dashboard is a single standalone HTML file at `dashboard/my-charts-dashboard/<slug>.html` (no Next.js route; the existing `dashboard/` app is untouched). Every page-url is registered in `dashboard/my-charts-dashboard/index.html` (charts index) and `dashboard/my-charts-dashboard/daas.md` (markdown list). No `mcp/daas.db` row. See `design.md` D5.
  - `fd-daas-workflow-creator` — `build_workflow_from_goal` defaults to `model="fast"` (data-fetch pipelines are not reasoning-heavy); user can override to `balance` / `high`. See `design.md` D6.
  - Skills are created in **project scope** (`.claude/skills/`), per `fd-skill-creator`'s "Create the skills in the project scope."
  - Each skill ships a `description` that is deliberately "pushy" (per `fd-skill-creator` guidance) with both English and Chinese trigger phrases, mirroring `fd-daas-scrapling-scraw-creator`.
- **Systems**: none beyond the existing `mcp/daas.db`.
