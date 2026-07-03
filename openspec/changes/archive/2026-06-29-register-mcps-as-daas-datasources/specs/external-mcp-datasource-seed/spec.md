## ADDED Requirements

### Requirement: Seed script registers four sibling MCPs as daas datasources

The system SHALL provide a single seed script at `mcp/daas-mcp/seed_external_mcps.py` that, when executed, ensures the four sibling MCPs (`edgartools-mcp`, `edinet-mcp`, `yfinance-mcp`, `cnstats-mcp`) are represented in `daas.db` as datasources with their natural form/section structure, all created through the existing `RegistryService` (no raw SQL).

#### Scenario: Fresh database receives all four datasources

- **WHEN** the seed script is run against a `daas.db` containing only the original `ckan` / `cnstats` / `worldbank` rows and no rows in `categories` / `datasource_forms` / `datasource_sections`
- **THEN** `list_sources` returns at least six rows including `edgar`, `edinet`, `yfinance`, `cnstats`, `ckan`, `worldbank`
- **AND** every newly seeded source has a non-null `category_id`
- **AND** `edgar`, `edinet`, `yfinance`, `cnstats` each have at least one row in `datasource_forms`

#### Scenario: Existing `cnstats` row is reused, not duplicated

- **WHEN** the seed script runs and a row with `name='cnstats'` already exists in `sources`
- **THEN** the script SHALL NOT insert a second `cnstats` row
- **AND** the script SHALL update only the `category_id` on the existing row and create its forms/sections under that row's `id`

### Requirement: Seed is fully idempotent across re-runs

The seed script SHALL be safe to re-run any number of times. A second invocation immediately following a successful first invocation MUST NOT change any row counts and MUST exit with status 0.

#### Scenario: Second run is a no-op on row counts

- **GIVEN** the seed script has completed successfully once against `daas.db`
- **WHEN** the seed script is invoked a second time with no other writes between runs
- **THEN** counts of rows in `sources`, `categories`, `datasource_forms`, `datasource_sections`, `datasource_collections`, `datasource_collection_items` SHALL be identical before and after the second run
- **AND** the second run's exit status SHALL be 0

#### Scenario: Edited section instruction is updated, not duplicated

- **GIVEN** a section already exists from a previous seed run
- **AND** the seed script's source code has changed that section's `instruction` string
- **WHEN** the seed script runs
- **THEN** the section row's `instruction` field SHALL be overwritten with the new value
- **AND** no additional row SHALL be created for the same `(form_id, section_name)` pair

### Requirement: Category tree groups datasources by purpose and region

The seed SHALL create a two-level category tree under which the four datasources are assigned:
- `Filings → US-SEC` contains `edgar`
- `Filings → JP-EDINET` contains `edinet`
- `Market-Data → Global` contains `yfinance`
- `Macro → China` contains `cnstats`

#### Scenario: Category tree reports correct grouping

- **WHEN** `get_category_tree()` is called after seeding
- **THEN** the returned tree contains exactly the top-level nodes `Filings`, `Market-Data`, and `Macro` introduced by this seed (other top-levels may exist from prior seeds)
- **AND** `Filings` has children `US-SEC` and `JP-EDINET`
- **AND** `Market-Data` has child `Global`
- **AND** `Macro` has child `China`
- **AND** each of those leaf categories reports `datasource_count >= 1`

### Requirement: EDGAR datasource exposes filing forms with item-level sections

The `edgar` datasource SHALL have forms `10-K`, `10-Q`, `8-K`, and `4`. The `10-K` form SHALL include at minimum sections for `Item 1 Business`, `Item 1A Risk Factors`, `Item 7 MD&A`, `Item 7A Quantitative and Qualitative Disclosures About Market Risk`, and `Item 8 Financial Statements and Supplementary Data`. Each section's `instruction` SHALL name the `edgartools-mcp` tool an agent should call to retrieve that section.

#### Scenario: 10-K item sections are discoverable

- **WHEN** `search_datasources(source_name="edgar", form="10-K", section="Item 1A")` is called
- **THEN** the result contains a row whose `section_name` starts with `Item 1A`
- **AND** that row's `instruction` contains the substring `mcp=edgartools-mcp`
- **AND** the same `instruction` names a tool from the set published by `edgartools-mcp` (`get_company`, `list_filings`, `get_filing`, `get_financials`, `get_insider_trades`)

### Requirement: EDINET datasource exposes doc-type forms with parser-mapped sections

The `edinet` datasource SHALL have at least one form for each EDINET doc-type code that `edinet-mcp` claims to parse (per its `supported_doc_types` tool): `120`, `130`, `140`, `150`, `160`, `170`, `180`, `350`, `360`. Each form SHALL include sections whose `instruction` names the matching `edinet-mcp` tool (`list_documents`, `get_document`, etc.).

#### Scenario: EDINET securities-report form is discoverable

- **WHEN** `search_datasources(source_name="edinet", form="120")` is called
- **THEN** at least one section is returned for that form
- **AND** the section's `instruction` contains `mcp=edinet-mcp`
- **AND** the `instruction` names a tool from the set published by `edinet-mcp` (`search_entities`, `get_entity`, `list_documents`, `get_document`, `supported_doc_types`)

### Requirement: Function-catalog MCPs use a single `default` form

`yfinance` and `cnstats` SHALL each have exactly one form named `default`, with sections grouping the upstream MCP's tools by purpose. Each section's `instruction` SHALL name the matching upstream tool.

#### Scenario: yfinance default form lists tool-grouped sections

- **WHEN** `list_forms(source_name="yfinance")` is called
- **THEN** the result contains exactly one form whose `form_type` is `default`
- **AND** that form has at least three sections
- **AND** every section's `instruction` contains `mcp=yfinance-mcp`

#### Scenario: cnstats default form lists tool-grouped sections

- **WHEN** `list_forms(source_name="cnstats")` is called
- **THEN** the result contains exactly one form whose `form_type` is `default`
- **AND** every section's `instruction` contains `mcp=cnstats-mcp`

### Requirement: Section instruction follows the routing grammar

Every section created by the seed SHALL have an `instruction` of the form `mcp=<mcp-name> tool=<tool-name>` followed by zero or more space-separated `param=<key>=<value>` tokens. For parameters the agent is expected to supply, the value SHALL be the literal `<ask-agent>`.

#### Scenario: Routing grammar is well-formed for every seeded section

- **WHEN** every section row created by the seed is inspected
- **THEN** each `instruction` begins with `mcp=` followed by a non-empty token
- **AND** the second token is `tool=` followed by a non-empty token
- **AND** any further `param=` tokens are of the form `param=<key>=<value>` with non-empty `<key>` and `<value>`

### Requirement: Seed creates a baseline `core` collection

The seed SHALL create one collection named `core` that wires together a curated set of (datasource, section) pairs spanning all four datasources, so an agent can retrieve a baseline cross-MCP view with a single `list_collection(name="core")` call.

#### Scenario: Core collection spans all four sources

- **WHEN** `list_collection(collection_name="core")` is called after seeding
- **THEN** the returned items reference all four sources `edgar`, `edinet`, `yfinance`, `cnstats` at least once each
- **AND** every item resolves to a real `(source, section)` pair (no orphans)

### Requirement: Seed supports `--unseed` rollback that does not touch unrelated rows

The seed script SHALL accept a `--unseed` flag that removes exactly the rows it owns — looked up by the same natural keys it uses for create-or-get — and SHALL NOT delete any pre-existing row (such as the original `ckan` / `cnstats` / `worldbank` seed rows or user-added rows).

#### Scenario: Unseed leaves pre-existing macro rows intact

- **GIVEN** the seed has run successfully, populating `edgar`, `edinet`, `yfinance` and adding form/section data under `cnstats`
- **AND** the original `ckan` / `cnstats` / `worldbank` rows pre-date the seed
- **WHEN** the seed script runs with `--unseed`
- **THEN** rows `edgar`, `edinet`, `yfinance` are deleted from `sources`
- **AND** the `cnstats` row remains, but its forms/sections/collection-items created by this seed are deleted
- **AND** `ckan`, `cnstats`, `worldbank` rows are still present
- **AND** the categories created by this seed are deleted (no orphan FK rows remain)

### Requirement: Seed does not depend on sibling MCPs being importable

The seed script SHALL be executable in the daas-mcp venv without any of `edgartools`, `edinet-tools`, `yfinance`, or any sibling MCP package being installed. Tool names referenced in `instruction` strings SHALL be hard-coded constants in the seed script, not introspected from sibling-MCP packages.

#### Scenario: Seed runs in a venv that lacks sibling-MCP packages

- **GIVEN** the daas-mcp venv has only the daas-mcp dependencies installed
- **WHEN** the seed script is run
- **THEN** the script imports SHALL all resolve
- **AND** the script SHALL complete with exit status 0
