## MODIFIED Requirements

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

## ADDED Requirements

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
