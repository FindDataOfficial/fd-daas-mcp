## MODIFIED Requirements

### Requirement: Seed script registers four sibling MCPs as daas datasources

The system SHALL provide a single seed script at `mcp/daas-mcp/seed_external_mcps.py` that, when executed, ensures the five sibling MCPs (`edgartools-mcp`, `edinet-mcp`, `yfinance-mcp`, `cnstats-mcp`, `cnreport-mcp`) are represented in `daas.db` as datasources with their natural form/section structure, all created through the existing `RegistryService` (no raw SQL).

#### Scenario: Fresh database receives all five datasources

- **WHEN** the seed script is run against a `daas.db` containing only the original `ckan` / `cnstats` / `worldbank` rows and no rows in `categories` / `datasource_forms` / `datasource_sections`
- **THEN** `list_sources` returns at least seven rows including `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport`, `ckan`, `worldbank`
- **AND** every newly seeded source has a non-null `category_id`
- **AND** `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport` each have at least one row in `datasource_forms`

#### Scenario: Existing `cnstats` row is reused, not duplicated

- **WHEN** the seed script runs and a row with `name='cnstats'` already exists in `sources`
- **THEN** the script SHALL NOT insert a second `cnstats` row
- **AND** the script SHALL update only the `category_id` on the existing row and create its forms/sections under that row's `id`

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

### Requirement: Seed creates a baseline `core` collection

The seed SHALL create one collection named `core` that wires together a curated set of (datasource, section) pairs spanning all five datasources, so an agent can retrieve a baseline cross-MCP view with a single `list_collection(name="core")` call.

#### Scenario: Core collection spans all five sources

- **WHEN** `list_collection(collection_name="core")` is called after seeding
- **THEN** the returned items reference all five sources `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport` at least once each
- **AND** every item resolves to a real `(source, section)` pair (no orphans)

## ADDED Requirements

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
