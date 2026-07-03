# cn-ministry-scraw-sources Specification

## Purpose
Scrapers + daas database registration for Chinese central-government ministry open-information archives. Adds 9 new ministry scrapers (人民银行, 发改委, 海关总署, 外汇局, 工信部, 自然资源部, 生态环境部, 应急部, 科技部) and registers the 5 existing scraw scripts (住建部, 商务部, 农业农村部, 财政部, 交通运输部) that are currently unregistered in `mcp/daas.db`. Every source follows the established `MANIFEST → create_datasource → register.py` contract.

## ADDED Requirements

### Requirement: Each target ministry has a MANIFEST-bearing crawler script

The system SHALL provide a scraw script at `mcp/scrapling-uv-mcp/scripts/<name>.py` (mirrored to `mcp/scrapling-docker-mcp/scripts/<name>.py`) for each of the 14 sources — the 9 new ministry archives (`pbc_zhengce_archive`, `ndrc_zcfg_archive`, `customs_zwgk_archive`, `safe_tjxx_archive`, `miit_zcwj_archive`, `mnr_zwgk_archive`, `mee_zcwj_archive`, `mem_zcwj_archive`, `most_tzgg_archive`) and the 5 existing scripts (`mohurd_xinwen_archive`, `fetch_mofcom_news`, `moa_govpublic_archive`, `mof_gkml_archive`, `mot_shuju_archive`). Each script SHALL define a module-level `MANIFEST = ScrawManifest(...)` (from `scraw_contract`) whose `name` equals the script basename, and SHALL emit a JSON array of records to stdout with the agreed columns. The 3 existing pre-MANIFEST scripts (`mohurd_xinwen_archive`, `mof_gkml_archive`, `fetch_mofcom_news`) SHALL have a `MANIFEST` added without changing their crawl behavior.

#### Scenario: Default crawl is bounded to 50 pages

- **WHEN** a script is run with no arguments
- **THEN** each archive/section it crawls is capped at 50 pages
- **AND** the total record count and per-section spread are logged to stderr

#### Scenario: --all crawls without a page cap

- **WHEN** a script is run with `--all` (or `--max-pages 0`)
- **THEN** every archive/section is crawled until a 404, an empty page, or the last partial page

#### Scenario: MANIFEST contract is satisfied

- **WHEN** `register.py <name> --check` is run
- **THEN** it loads the script's `MANIFEST` without error
- **AND** `MANIFEST.name` equals the script basename
- **AND** `MANIFEST.columns` lists at least a `title`, `date`, and `url` column
- **AND** the `url` column has `primary_key=True`
- **AND** every column has a non-empty `description` and `source_field`

#### Scenario: Records carry the agreed columns

- **WHEN** the script emits a record
- **THEN** the record SHALL have a `url` that is absolute
- **AND** a `title` derived from the page's link markup
- **AND** a `date` that is `YYYY-MM-DD`, derived from the URL `t<YYYYMMDD>_` token when present and falling back to the visible date span
- **AND** any ministry-specific columns declared in the `MANIFEST` (e.g. `section`, `subsection`, `department`)

### Requirement: Each scraw source is registered in daas.db

The system SHALL register each of the 14 sources in `mcp/daas.db` with: one `sources` row (via `mcp__daas-mcp__create_datasource`, whose `config_json` is `MANIFEST.to_config_json()`), N `datasource_columns` rows + an upserted `scraw_configs` recipe row (via `register.py <name>`), and a `category_id` resolving to the `网页抓取` category.

#### Scenario: sources row exists and points at the script

- **WHEN** registration has run for a source
- **THEN** the `sources` table has a row with `name = <MANIFEST.name>`
- **AND** its `config` blob's `scraper_script` points at `mcp/scrapling-uv-mcp/scripts/<name>.py`
- **AND** its `config.type` is `scraw` and `config.runtime` is `uv`
- **AND** `category_id` resolves to a category whose name is `网页抓取`

#### Scenario: Columns and scraw recipe are written

- **WHEN** `register.py <name>` has run
- **THEN** `datasource_columns` has one row per `MANIFEST.columns` entry for that `table_name`
- **AND** the `url` column has `is_primary_key=1`
- **AND** every column has a non-empty `description` and `source_field`
- **AND** `scraw_configs` has a row with `name = <MANIFEST.name>` whose `columns_json` matches `MANIFEST.to_scraw_columns()`

#### Scenario: Registration is idempotent

- **WHEN** `register.py <name>` is run a second time
- **THEN** `datasource_columns` rows for that source are replaced (not duplicated)
- **AND** `scraw_configs` is updated in place (no duplicate insert)

### Requirement: Verification before registration

Each crawler MUST be run and its output reviewed (total record count, per-section spread, date range, sample record) before its datasource is registered. A source whose verification run returns zero records, or where every record is missing `date`, SHALL NOT be registered until the cause is identified and fixed or the failing section is removed from scope.

#### Scenario: A verification run returns zero records

- **WHEN** a script's verification run returns 0 records
- **THEN** the registration step SHALL NOT proceed for that source
- **AND** the cause SHALL be diagnosed (wrong selector, JS-rendered list, AJAX-fed grid, over-narrow URL filter) or the source dropped from scope before registering

#### Scenario: Records are missing dates

- **WHEN** more than a small fraction of records lack a `date` after the URL-token and span fallbacks are exhausted
- **THEN** the registration step SHALL NOT proceed
- **AND** the date source SHALL be re-examined before registering
