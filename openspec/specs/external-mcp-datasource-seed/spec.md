# external-mcp-datasource-seed Specification

## Purpose

Register the sibling live-execution MCPs (`edgartools-mcp`, `edinet-mcp`, `yfinance-mcp`, `cnstats-mcp`, `cnreport-mcp`, `hkreport-mcp`) as daas datasources in `mcp/daas.db`, with a two-level category tree, per-source forms/sections carrying routing-grammar `instruction` strings, and a baseline `core` collection — all via a single idempotent seed script that is reversible with `--unseed`.
## Requirements
### Requirement: Seed script registers four sibling MCPs as daas datasources

The system SHALL provide a single seed script at `mcp/daas-mcp/seed_external_mcps.py` that, when executed, ensures the six sibling MCPs (`edgartools-mcp`, `edinet-mcp`, `yfinance-mcp`, `cnstats-mcp`, `cnreport-mcp`, `hkreport-mcp`) are represented in `daas.db` as datasources with their natural form/section structure, all created through the existing `RegistryService` (no raw SQL).

#### Scenario: Fresh database receives all six datasources

- **WHEN** the seed script is run against a `daas.db` containing only the original `ckan` / `cnstats` / `worldbank` rows and no rows in `categories` / `datasource_forms` / `datasource_sections`
- **THEN** `list_sources` returns at least eight rows including `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport`, `hkex`, `ckan`, `worldbank`
- **AND** every newly seeded source has a non-null `category_id`
- **AND** `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport`, `hkex` each have at least one row in `datasource_forms`

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

The seed SHALL create a two-level category tree under which the five datasources are assigned:
- `Filings → US-SEC` contains `edgar`
- `Filings → JP-EDINET` contains `edinet`
- `Filings → CN-Cninfo` contains `cnreport`
- `Market-Data → Global` contains `yfinance`
- `Macro → China` contains `cnstats`

#### Scenario: Category tree reports correct grouping

- **WHEN** `get_category_tree()` is called after seeding
- **THEN** the returned tree contains exactly the top-level nodes `Filings`, `Market-Data`, and `Macro` introduced by this seed (other top-levels may exist from prior seeds)
- **AND** `Filings` has children `US-SEC`, `JP-EDINET`, and `CN-Cninfo`
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

The seed SHALL create one collection named `core` that wires together a curated set of (datasource, section) pairs spanning all five datasources, so an agent can retrieve a baseline cross-MCP view with a single `list_collection(name="core")` call.

#### Scenario: Core collection spans all five sources

- **WHEN** `list_collection(collection_name="core")` is called after seeding
- **THEN** the returned items reference all five sources `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport` at least once each
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

### Requirement: CNReport datasource exposes the Annual-Report form with standard 年报 sections

The `cnreport` datasource SHALL have a single form `Annual-Report` whose sections cover the standard structure of a Chinese A-share annual report (年度报告). The form SHALL include at minimum sections for `重要提示、目录及释义`, `公司简介和主要财务指标`, `管理层讨论与分析`, `公司治理`, `环境与社会责任`, `重要事项`, `股份变动及股东情况`, `财务报告`, and `其他报告`. Each section's `instruction` SHALL name the `cnreport-mcp` tool an agent should call to retrieve that section, with the section's title (or its heading prefix) pre-bound as the `selector` parameter and `source` left as `<ask-agent>`.

#### Scenario: Annual report sections are discoverable

- **WHEN** `search_datasources(source_name="cnreport", form="Annual-Report", section="管理层讨论与分析")` is called
- **THEN** the result contains a row whose `section_name` matches `管理层讨论与分析`
- **AND** that row's `instruction` contains the substring `mcp=cnreport-mcp`
- **AND** the same `instruction` names a tool from the set published by `cnreport-mcp` (one of `list_outline`, `extract_section`, `ai_extract`, `index_records`, `search_reports`, `delete_index`)
- **AND** the `instruction` contains `param=source=<ask-agent>` so the agent supplies the report URL or path
- **AND** the `instruction` contains a `param=selector=` token whose value is non-empty (the seed pre-binds the section selector)

#### Scenario: All Annual-Report sections satisfy the routing grammar

- **WHEN** every section row under the `cnreport` source's `Annual-Report` form is inspected
- **THEN** each `instruction` matches the grammar `mcp=<name> tool=<name> (param=<key>=<value>)*`
- **AND** each `instruction` names `cnreport-mcp` and one of its published tools

### Requirement: Core collection includes a CNReport section

The seed's `core` collection SHALL contain at least one item drawn from the `cnreport` datasource's `Annual-Report` form, so the baseline cross-MCP view returned by `list_collection(name="core")` is symmetric across filings jurisdictions (US, JP, CN).

#### Scenario: Core collection contains a cnreport row

- **WHEN** `list_collection(collection_name="core")` is called after seeding
- **THEN** at least one returned item has `source_name="cnreport"`
- **AND** that item resolves to a real `(source, section)` pair under the `Annual-Report` form

### Requirement: Unseed rollback removes CNReport rows symmetrically

The `--unseed` flag SHALL remove the rows this seed owns for `cnreport` (the source, its `Annual-Report` form, all `Annual-Report` sections, and any `core` collection items pointing at them) and the `CN-Cninfo` category leaf, while leaving the protected pre-existing sources (`ckan`, `cnstats`, `worldbank`) untouched.

#### Scenario: Unseed deletes cnreport but preserves protected rows

- **GIVEN** the seed has run successfully and `cnreport` exists in `sources`
- **WHEN** the script is invoked with `--unseed`
- **THEN** `cnreport` SHALL no longer appear in `sources`
- **AND** no row referencing `cnreport.id` SHALL remain in `datasource_forms`, `datasource_sections`, or `datasource_collection_items`
- **AND** the `CN-Cninfo` category SHALL no longer appear in `categories`
- **AND** `ckan`, `cnstats`, and `worldbank` rows SHALL still be present

### Requirement: HKEX datasource exposes HK filing and financial tool sections

The `hkex` datasource SHALL be seeded with forms `Annual Report`, `Interim Report`, `Announcement`, `Financials`, and `Calendar`. Each form SHALL have at least one section whose `instruction` field names the `hkreport-mcp` tool an agent should call, using the routing grammar `mcp=hkreport-mcp tool=<tool> param=<k>=<v>` already used by the other seeded datasources. The datasource SHALL be assigned to a leaf category `Filings → HK-HKEX` (newly added under the existing `Filings` parent).

#### Scenario: hkex forms exist after seeding

- **WHEN** the seed script runs against a fresh database
- **THEN** `list_forms(source_name="hkex")` returns at least the five forms `Annual Report`, `Interim Report`, `Announcement`, `Financials`, and `Calendar`
- **AND** every returned form has at least one section

#### Scenario: hkex section instructions route to hkreport-mcp tools

- **WHEN** any section under any `hkex` form is read after seeding
- **THEN** its `instruction` matches the grammar `mcp=hkreport-mcp tool=<tool> param=...` where `<tool>` is one of `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_disclosure_calendar`

#### Scenario: hkex sits under Filings → HK-HKEX

- **WHEN** `get_category_tree()` is called after seeding
- **THEN** the `Filings` node has a child named `HK-HKEX` whose datasource list contains `hkex`
- **AND** the leaf category reports `datasource_count >= 1`

### Requirement: hkex joins the core collection

The seed script SHALL add the `hkex` datasource to the existing `core` collection (created by the original seed) alongside `edgar`, `edinet`, `yfinance`, `cnstats`, and `cnreport`. Re-running the seed SHALL NOT duplicate the membership row.

#### Scenario: hkex is a member of core after first seed

- **WHEN** the seed script runs against a fresh database and `list_collection(collection_name="core")` is queried
- **THEN** the returned items include one entry whose `source_name` is `hkex`

#### Scenario: Re-seeding does not duplicate hkex membership

- **GIVEN** the seed script has completed once
- **WHEN** the seed script runs a second time
- **THEN** `list_collection(collection_name="core")` reports exactly one entry for `hkex` (no duplicates)

### Requirement: `--unseed` removes the hkex datasource

The seed script's `--unseed` flag SHALL remove the `hkex` row from `sources` along with its associated rows in `datasource_forms`, `datasource_sections`, and `datasource_collection_items`. The leaf category `HK-HKEX` SHALL also be removed (consistent with how `--unseed` already removes the other seed-owned categories like `US-SEC` and `CN-Cninfo`).

#### Scenario: --unseed removes hkex and its forms

- **GIVEN** the seed script has run successfully
- **WHEN** the seed script is run with `--unseed`
- **THEN** `list_sources` no longer returns a row with `name='hkex'`
- **AND** there are no rows in `datasource_forms` or `datasource_sections` referencing the removed source
- **AND** the `HK-HKEX` leaf category is gone

