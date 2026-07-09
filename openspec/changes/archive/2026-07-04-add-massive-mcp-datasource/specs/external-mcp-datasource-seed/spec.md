## ADDED Requirements

### Requirement: Massive datasource exposes the default form with three composable-tool sections

The `massive` datasource SHALL be seeded with exactly one form named `default`, whose sections correspond to the three composable tools published by `mcp_massive` v0.10.0 — `Search-Endpoints`, `Call-API`, and `Query-Data`. Each section's `instruction` SHALL follow the existing routing grammar `mcp=massive-mcp tool=<tool> param=<k>=<v>` and SHALL name the matching upstream tool. `Search-Endpoints` SHALL route to `search_endpoints` with `query=<ask-agent>`; `Call-API` SHALL route to `call_api` with `path=<ask-agent>` and `method=<ask-agent>`; `Query-Data` SHALL route to `query_data` with `sql=<ask-agent>`.

#### Scenario: default form lists the three composable-tool sections

- **WHEN** `list_forms(source_name="massive")` is called after seeding
- **THEN** the result contains exactly one form whose `form_type` is `default`
- **AND** that form has exactly three sections named `Search-Endpoints`, `Call-API`, and `Query-Data`

#### Scenario: each section routes to the matching mcp_massive tool

- **WHEN** each section under the `massive` source's `default` form is read after seeding
- **THEN** every section's `instruction` begins with `mcp=massive-mcp`
- **AND** the `Search-Endpoints` section's `instruction` contains `tool=search_endpoints` and `param=query=<ask-agent>`
- **AND** the `Call-API` section's `instruction` contains `tool=call_api`, `param=path=<ask-agent>`, and `param=method=<ask-agent>`
- **AND** the `Query-Data` section's `instruction` contains `tool=query_data` and `param=sql=<ask-agent>`

#### Scenario: All massive sections satisfy the routing grammar

- **WHEN** every section row under the `massive` source's `default` form is inspected
- **THEN** each `instruction` matches the grammar `mcp=<name> tool=<name> (param=<key>=<value>)*`
- **AND** each `instruction` names `massive-mcp` and one of `search_endpoints`, `call_api`, or `query_data`

### Requirement: massive sits under the Market-Data → Massive category

The seed SHALL create a leaf category `Massive` (label `Massive.com`) under the existing root `Market-Data` category (sibling to the existing `Global` leaf that holds `yfinance`), and SHALL assign the `massive` datasource to that leaf.

#### Scenario: massive is grouped under Market-Data → Massive

- **WHEN** `get_category_tree()` is called after seeding
- **THEN** the `Market-Data` node has a child named `Massive`
- **AND** the `Massive` leaf's datasource list contains `massive`
- **AND** the `Massive` leaf reports `datasource_count >= 1`

#### Scenario: Existing Market-Data → Global grouping is unchanged

- **WHEN** `get_category_tree()` is called after seeding
- **THEN** the `Market-Data` node still has a child named `Global`
- **AND** the `Global` leaf's datasource list still contains `yfinance`

### Requirement: massive joins the core collection

The seed script SHALL add the `massive` datasource to the existing `core` collection alongside `edgar`, `edinet`, `yfinance`, `cnstats`, `cnreport`, and `hkex`. Re-running the seed SHALL NOT duplicate the membership row.

#### Scenario: massive is a member of core after first seed

- **WHEN** the seed script runs against a fresh database and `list_collection(collection_name="core")` is queried
- **THEN** the returned items include one entry whose `source_name` is `massive`
- **AND** that item resolves to a real `(source, section)` pair under the `default` form

#### Scenario: Re-seeding does not duplicate massive membership

- **GIVEN** the seed script has completed once
- **WHEN** the seed script runs a second time
- **THEN** `list_collection(collection_name="core")` reports exactly one entry for `massive` (no duplicates)

### Requirement: `--unseed` removes the massive datasource

The seed script's `--unseed` flag SHALL remove the `massive` row from `sources` along with its associated rows in `datasource_forms`, `datasource_sections`, and `datasource_collection_items`. The leaf category `Massive` SHALL also be removed (consistent with how `--unseed` removes the other seed-owned category leaves like `US-SEC` and `HK-HKEX`). The protected pre-existing sources (`ckan`, `cnstats`, `worldbank`) SHALL remain untouched.

#### Scenario: --unseed removes massive and its forms

- **GIVEN** the seed script has run successfully and `massive` exists in `sources`
- **WHEN** the seed script is run with `--unseed`
- **THEN** `list_sources` no longer returns a row with `name='massive'`
- **AND** there are no rows in `datasource_forms` or `datasource_sections` referencing the removed source
- **AND** the `Massive` leaf category is gone from `get_category_tree()`
- **AND** `list_collection(collection_name="core")` no longer contains an item whose `source_name` is `massive`
- **AND** `ckan`, `cnstats`, and `worldbank` rows are still present
