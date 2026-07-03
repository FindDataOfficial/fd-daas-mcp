## MODIFIED Requirements

### Requirement: daas integration is traceability only
A processing rule MAY carry a `datasource` name (daas `sources.name`) for traceability. The LLM extraction path (`create_rule`, `update_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`) SHALL NOT read from or write to any daas registry table (`sources`, `daas_functions`, `observations`, `datasource_*`). The source-of-truth for which table to read is `process_rules.source_table`; the daas `sources.config.scraw_config` slug is what makes the rule and the datasource point at the same scraped data. The indicator path (`create_indicator`, `update_indicator`, `run_indicator`, `calculate`) is exempt from this constraint and SHALL write computed indicators to `observations` as specified by the `process-mcp-indicators` capability.

#### Scenario: daas tables are untouched by run_rule
- **WHEN** `run_rule` processes a rule whose `datasource="news_finance"`
- **THEN** no `sources`, `daas_functions`, or `observations` row is created or modified

#### Scenario: process_results is queryable via dashboard-mcp
- **WHEN** a caller runs `dashboard-mcp.query_table(database="daas", table="process_results")`
- **THEN** the extracted records are returned as rows

#### Scenario: indicator path is exempt and writes observations
- **WHEN** `run_indicator` runs an indicator rule
- **THEN** `observations` rows MAY be created by the indicator path, and this does not violate the LLM extraction path's traceability-only guarantee
