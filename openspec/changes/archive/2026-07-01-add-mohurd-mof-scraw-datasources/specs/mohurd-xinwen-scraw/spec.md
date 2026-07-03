## ADDED Requirements

### Requirement: MOHURD xinwen archive crawler exists

The system SHALL provide a scraw script at `mcp/scrapling-uv-mcp/scripts/mohurd_xinwen_archive.py` (mirrored to `mcp/scrapling-docker-mcp/scripts/`) that crawls the MOHURD `/xinwen/` archive across three sections (`jsyw` 部门动态, `gzdt` 工作动态, `dfxx` 地方信息), paginates each section until exhausted or the page cap is reached, and emits a JSON array of records to stdout.

#### Scenario: Default crawl is bounded to 50 pages per section

- **WHEN** the script is run with no arguments
- **THEN** each of the 3 sections is crawled to at most 50 pages
- **AND** the total record count and per-section spread are logged to stderr

#### Scenario: --all crawls all pages

- **WHEN** the script is run with `--all` (or `--max-pages 0`)
- **THEN** every section is crawled until the section returns a 404 or an empty list

#### Scenario: Records carry the agreed columns

- **WHEN** the script emits a record
- **THEN** the record SHALL have keys `section`, `title`, `date`, `url`
- **AND** `url` SHALL be absolute and end in `.html` or `.pdf`
- **AND** `title` SHALL come from the `<a title="...">` attribute (never truncated)
- **AND** `date` SHALL be `YYYY-MM-DD` parsed from the per-item `<span class="date-info">`

### Requirement: MOHURD datasource is registered in daas.db

The system SHALL register a `datasources` row named `mohurd_xinwen_archive` in `mcp/daas.db`, with one `datasource_columns` row per emitted field, placed under a `网页抓取 / Web Scraw` category, with a matching `scraw_configs` recipe row.

#### Scenario: Datasource row exists and points at the script

- **WHEN** the registration step has run
- **THEN** `datasources` has a row with `name='mohurd_xinwen_archive'`
- **AND** its `config_json.scraper_script` points at `mcp/scrapling-uv-mcp/scripts/mohurd_xinwen_archive.py`
- **AND** `category_id` resolves to a category whose name is `网页抓取`

#### Scenario: Columns are documented with source_field

- **WHEN** the registration step has run
- **THEN** `datasource_columns` has rows for `section`, `title`, `date`, `url`
- **AND** the `url` column has `is_primary_key=1`
- **AND** every column has a non-empty `description` and `source_field`

### Requirement: Verification before registration

The crawler MUST be run and its output reviewed (record count, date range, sample) before the datasource is registered. A run that returns zero records for any section SHALL NOT be registered until the cause is identified and fixed or the section is removed from scope.

#### Scenario: A section returns zero records

- **WHEN** a section's crawl returns 0 records on the verification run
- **THEN** the registration step SHALL NOT proceed for that section
- **AND** the cause SHALL be diagnosed (selector, URL filter, JS-rendered list, etc.) or the section dropped from scope before registering
