# fd-daas-indicators-collection-creator Specification

## Purpose
TBD - created by archiving change add-indicators-collection-and-daas-doc. Update Purpose after archive.
## Requirements
### Requirement: Skill exists and triggers on indicator-collection-creation intent

The system SHALL ship a skill at `.claude/skills/fd-daas-indicators-collection-creator/SKILL.md` (project scope) whose `description` triggers when the user wants to create a curated collection of indicators and document it — in English or Chinese. The skill SHALL orchestrate the existing daas-mcp indicator-collection tools; it MUST NOT re-implement them.

#### Scenario: Triggers on collection-creation phrasing

- **WHEN** the user says "把这几个指标存成一个 collection" or "create an indicators collection for these"
- **THEN** the `fd-daas-indicators-collection-creator` skill is consulted

### Requirement: Create collection and add members via existing daas-mcp tools

The skill SHALL create the collection with `mcp__daas-mcp__create_indicator_collection(name, description?)` and add each member with `mcp__daas-mcp__add_indicator_to_collection(collection_name, indicator_name, score?, reason?)`. It SHALL show the proposed collection (name + members) to the user and get confirmation before writing. It MUST surface a daas-mcp error and skip the member (without creating the collection) when a proposed member indicator does not exist in `indicator_rules`.

#### Scenario: Create a collection and add members

- **WHEN** the user confirms the proposed members list
- **THEN** the skill creates the collection, adds each member, and reports the collection name + member count

#### Scenario: Unknown indicator rejected

- **WHEN** a proposed member indicator does not exist in `indicator_rules`
- **THEN** the skill surfaces the daas-mcp error and does not create the collection for that member

### Requirement: Surface resolved scores inheriting the datasource default

For each member, the skill SHALL call `mcp__daas-mcp__list_indicator_collection_items(collection_name)` and surface the resolved `score`, `item_score`, `indicator_default_score`, and `source_default_score` (the existing 3-level resolution: item override → indicator default → datasource `sources.score`). The skill MUST NOT recompute or copy scores — it renders the tool's resolved values verbatim, so the "inherit the datasource score" property is the existing resolution surfaced in the doc.

#### Scenario: Member with NULL item + NULL indicator scores inherits datasource

- **WHEN** a member has `item_score = null` and `indicator_default_score = null` and its datasource `sources.score = 0.6`
- **THEN** the skill surfaces that member with resolved `score = 0.6` and `source_default_score = 0.6`

### Requirement: Write a human-readable introduction markdown

The skill SHALL write an `indicators-<collection>.md` introduction file containing: collection name + description, a member table (indicator name, datasource, op, params, source_table, value_column, resolved score, item_score, indicator_default_score, source_default_score), created date, and a one-line refresh note ("re-run `mcp__daas-mcp__run_indicator(name)` for each member"). The file MUST be plain markdown (no JS, no external fetch). Standalone, it lives at `daas-doc/indicators/<collection>.md` (creating the dir on first use).

#### Scenario: Standalone introduction md written

- **WHEN** the skill runs standalone (no `workflow-name` token in `args`)
- **THEN** the file is written to `daas-doc/indicators/<collection>.md` and the path is reported to the user

#### Scenario: Member table includes resolved scores

- **WHEN** the introduction md is written
- **THEN** each member row shows the resolved `score` and the three raw score fields (`item_score`, `indicator_default_score`, `source_default_score`) for transparency

### Requirement: Nest under the workflow dir when invoked inside workflow-creator

When the skill's `args` contain a `workflow-name <X>` token (passed by `fd-daas-workflow-creator`), the skill SHALL write the introduction md to `daas-doc/<X>/indicators-<collection>.md` instead of the standalone path, so the doc co-locates with the workflow's `plan.md` and dashboard instruction md.

#### Scenario: Nested inside workflow-creator

- **WHEN** the skill is invoked with `args` containing `workflow-name my-flow`
- **THEN** the introduction md is written to `daas-doc/my-flow/indicators-<collection>.md`

#### Scenario: Standalone when no workflow-name token

- **WHEN** the skill is invoked with no `workflow-name` token in `args`
- **THEN** the introduction md is written to `daas-doc/indicators/<collection>.md`
