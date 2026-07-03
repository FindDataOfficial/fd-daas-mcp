# mof-gkml-scraw Specification

## Purpose
TBD - created by syncing change add-mohurd-mof-scraw-datasources. Update Purpose after archive.
## Requirements
### Requirement: MOF gkml archive crawler exists

The system SHALL provide a scraw script at `mcp/scrapling-uv-mcp/scripts/mof_gkml_archive.py` (mirrored to `mcp/scrapling-docker-mcp/scripts/`) that crawls the MOF `/gkml/` 信息公开 archive across the four sections — 通知公告 (with sub-archives `bulinggonggao/tongzhitonggao/`, `czbl/`, `czbgg/`), 财政数据 (`caizhengshuju/`), 财政文告 (`caizhengwengao/`), 财经论坛 (`diaochayanjiu/`) — paginates each sub-archive until exhausted or the page cap is reached, and emits a JSON array of records to stdout.

#### Scenario: Default crawl is bounded to 50 pages per sub-archive

- **WHEN** the script is run with no arguments
- **THEN** each sub-archive is crawled to at most 50 pages
- **AND** the total record count and per-section/per-sub-archive spread are logged to stderr

#### Scenario: --all crawls all pages

- **WHEN** the script is run with `--all` (or `--max-pages 0`)
- **THEN** every sub-archive is crawled until 404 or an empty page list

#### Scenario: Pagination follows the MOF index_N.htm offset-by-1 rule

- **WHEN** the crawler advances past page 1
- **THEN** page 2 is fetched at `index_1.htm`, page 3 at `index_2.htm`, etc., relative to the sub-archive base
- **AND** a 404 or empty list terminates that sub-archive's crawl

#### Scenario: Records carry the agreed columns

- **WHEN** the script emits a record
- **THEN** the record SHALL have keys `section`, `subsection`, `title`, `date`, `url`, `doc_type`
- **AND** `url` SHALL be absolute and resolve to a `.htm`, `.html`, or `.pdf` resource
- **AND** `title` SHALL come from the `<a title="...">` attribute
- **AND** `date` SHALL be `YYYY-MM-DD`, derived from the URL `t(\d{8})_` token when present, falling back to the sibling `<span>` text
- **AND** `doc_type` SHALL be `pdf` when the URL path ends in `.pdf`, otherwise `html`

### Requirement: MOF datasource is registered in daas.db

The system SHALL register a `datasources` row named `mof_gkml_archive` in `mcp/daas.db`, with one `datasource_columns` row per emitted field, placed under a `网页抓取 / Web Scraw` category, with a matching `scraw_configs` recipe row.

#### Scenario: Datasource row exists and points at the script

- **WHEN** the registration step has run
- **THEN** `datasources` has a row with `name='mof_gkml_archive'`
- **AND** its `config_json.scraper_script` points at `mcp/scrapling-uv-mcp/scripts/mof_gkml_archive.py`
- **AND** `category_id` resolves to a category whose name is `网页抓取`

#### Scenario: Columns are documented with source_field

- **WHEN** the registration step has run
- **THEN** `datasource_columns` has rows for `section`, `subsection`, `title`, `date`, `url`, `doc_type`
- **AND** the `url` column has `is_primary_key=1`
- **AND** every column has a non-empty `description` and `source_field`

### Requirement: Verification before registration

The crawler MUST be run and its output reviewed (record count, per-section spread, date range, sample) before the datasource is registered. A run that returns zero records for any sub-archive SHALL NOT be registered until the cause is identified and fixed or the sub-archive is removed from scope.

#### Scenario: A sub-archive returns zero records

- **WHEN** a sub-archive's crawl returns 0 records on the verification run
- **THEN** the registration step SHALL NOT proceed for that sub-archive
- **AND** the cause SHALL be diagnosed or the sub-archive dropped from scope before registering
