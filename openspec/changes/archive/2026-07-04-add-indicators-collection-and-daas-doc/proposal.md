## Why

The daas-mcp already supports `indicator_collections` (grouping indicators with 3-level score inheritance: item override → indicator default → datasource default) and `indicator_rules.score`, but there is no skill guiding the creation of an indicators collection or producing a human-readable introduction for it. Meanwhile, the three `fd-daas-*` creator skills (workflow / dashboard / indicators-collection) each produce valuable planning artifacts — workflow plans, dashboard build instructions, indicator introductions — that today live in ad-hoc locations with no shared doc convention. When one creator runs nested inside another (e.g. `fd-daas-dashboard-creator` invoked during a `fd-daas-workflow-creator` run), there is no rule for co-locating their docs under the workflow's folder. This change adds the missing skill, a shared `daas-doc/` convention, and doc-writing + nesting behavior to the two existing creator skills.

## What Changes

- **New skill `fd-daas-indicators-collection-creator`** — drives the existing daas-mcp tools (`create_indicator_collection`, `add_indicator_to_collection`, `list_indicator_collection_items`) to build an indicators collection, surfaces each member's resolved score (which already inherits the datasource score via the 3-level resolution), and writes a human-readable `indicators-<collection>.md` introduction (members, resolved scores, source tables, ops, params). When run inside `fd-daas-workflow-creator`, writes the md into the workflow's `daas-doc/<workflow-name>/` folder with the workflow-name prefix.
- **New `daas-doc/` convention** — a top-level `daas-doc/` directory for skill-generated human-readable docs. Layout: `daas-doc/<workflow-name>/plan.md` (workflow-creator), `daas-doc/<workflow-name>/<custom-name>-dashboard.md` (dashboard-creator nested), `daas-doc/<workflow-name>/indicators-<collection>.md` (indicators-collection-creator nested). Standalone defaults: `daas-doc/dashboard/<custom-name>-dashboard.md` and `daas-doc/indicators/<collection>.md`.
- **Modify `fd-daas-workflow-creator`** — derive a kebab-case `<workflow-name>` (from the goal, falling back to a timestamp), create `daas-doc/<workflow-name>/plan.md` capturing the summarized flow + persisted workflow name + step list + tier, and pass the workflow-name as nesting context to any child creator skills it invokes.
- **Modify `fd-daas-dashboard-creator`** — after building the standalone HTML, also write an instruction `<custom-name>-dashboard.md` under `daas-doc/dashboard/` (slug, source tables, refresh cadence, `file://` URL, how to refresh). When nested inside `fd-daas-workflow-creator`, write it under `daas-doc/<workflow-name>/` instead.

## Capabilities

### New Capabilities
- `fd-daas-indicators-collection-creator`: A skill that creates an indicator collection via the existing daas-mcp tools, surfaces each member's resolved score (inheriting the datasource default), and writes a human-readable introduction md.
- `daas-doc`: The `daas-doc/` directory convention + workflow-scoped nesting rules shared by the creator skills (where each skill's doc lands, standalone vs nested).

### Modified Capabilities
- `fd-daas-workflow-creator`: Add auto-creation of `plan.md` under `daas-doc/<workflow-name>/`, workflow-name derivation, and nesting-context handoff to child creator skills.
- `fd-daas-dashboard-creator`: Add an instruction-md write under `daas-doc/` (and nesting into the workflow dir when invoked inside workflow-creator).

## Impact

- **New files**: `.claude/skills/fd-daas-indicators-collection-creator/SKILL.md` (+ optional `references/`).
- **Modified files**: `.claude/skills/fd-daas-workflow-creator/SKILL.md`, `.claude/skills/fd-daas-dashboard-creator/SKILL.md`.
- **New convention**: `daas-doc/` directory at repo root, created on first use.
- **No DB schema changes** — `indicator_collections`, `indicator_collection_items`, and `indicator_rules.score` already exist per the `indicator-collections` / `indicator-scores` specs.
- **No new daas-mcp tools** — the existing CRUD + score tools are sufficient; the skill only orchestrates them.
