## ADDED Requirements

### Requirement: Skill exists and triggers on data-fetch intent

The system SHALL ship a skill at `.claude/skills/fd-daas-fetch-data/SKILL.md` (project scope) whose `description` triggers when the user wants to look up a daas entity, find which datasource covers it, or define an indicator over its source data — in English or Chinese. The description MUST name near-miss cases where a sibling skill should win instead (e.g. scraping a new website → `fd-daas-scrapling-scraw-creator`).

#### Scenario: Triggers on entity-lookup phrasing
- **WHEN** the user says "查一下比亚迪这只股票在 daas 里有没有" or "look up entity BYD in the daas registry"
- **THEN** the `fd-daas-fetch-data` skill is consulted and its workflow begins at the entity-lookup step

#### Scenario: Does not trigger on raw scrape intent
- **WHEN** the user says "scrape this site and save it as a datasource"
- **THEN** the `fd-daas-fetch-data` skill is NOT consulted; `fd-daas-scrapling-scraw-creator` wins

### Requirement: Entity lookup step

The skill SHALL drive the entity-lookup step by calling `mcp__daas-mcp__search_entities` (and `mcp__daas-mcp__list_entities` / `mcp__daas-mcp__get_entity` as needed) and surfacing the resolved entity + its `identifier_in_source` per linked datasource. It MUST handle the not-found case with a clear user-facing message rather than proceeding.

#### Scenario: Entity found
- **WHEN** the user names an entity that exists in the registry
- **THEN** the skill calls `search_entities`, surfaces the entity row, and proceeds to the datasource-coverage step

#### Scenario: Entity not found
- **WHEN** the user names an entity that is not in the registry
- **THEN** the skill reports "entity not found", suggests `search_entities` with a looser query, and stops

### Requirement: Datasource coverage resolution step

The skill SHALL resolve which datasource covers each entity by calling `mcp__daas-mcp__get_entity_coverage`, returning the `identifier_in_source`, the available sections (routing instructions), and the column count/list per linked source. It MUST surface the `column_hint` → sibling MCP `get_function_info` path for external-MCP sources so the model knows how to fetch.

#### Scenario: Coverage available
- **WHEN** the entity has at least one linked datasource
- **THEN** the skill calls `get_entity_coverage`, lists each source with its `identifier_in_source` + column count, and proceeds to the indicator step

#### Scenario: No covering datasource
- **WHEN** the entity has zero linked datasources
- **THEN** the skill reports "no datasource covers this entity", suggests `link_entity_datasource` or the `fd-daas-scrapling-scraw-creator` skill, and stops

### Requirement: Indicator creation step

The skill SHALL offer to define one or more indicators over the source data by calling `mcp__daas-mcp__create_indicator` (persists a binding) or `mcp__daas-mcp__calculate` (ad-hoc, no persist). It MUST validate that the `source_table` + `value_column` exist before creating the indicator, mirroring the daas-mcp identifier guard.

#### Scenario: Indicator created over a scraw table
- **WHEN** the user asks for a 5-day SMA over a `scraw_<slug>` table's close-price column
- **THEN** the skill calls `create_indicator` with `op="sma"`, `params={"window":5}`, the validated `source_table` + `value_column`, and confirms the binding was persisted

#### Scenario: Indicator over a non-scraw table
- **WHEN** the user asks for an indicator over a table that is in `daas.db` but not a `scraw_*` table
- **THEN** the skill proceeds, because indicator rules accept any table in `daas.db`, not only `scraw_*`

#### Scenario: MCP tool missing or unavailable
- **WHEN** a required daas-mcp tool is not available at run time
- **THEN** the skill reports which tool is missing and stops, rather than silently failing
