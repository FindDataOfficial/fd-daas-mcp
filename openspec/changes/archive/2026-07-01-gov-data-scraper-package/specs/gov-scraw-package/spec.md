## ADDED Requirements

### Requirement: Standalone pip-installable package bundling the ministry scrapers

The system SHALL provide a Python package `gov-scraw` at the repo root with its own `pyproject.toml`, installable via `pip install git+<repo-url>` with no dependency on the `mcp/` tree, `mcp/models`, or any MCP server. The package SHALL vendor a trimmed `scraw_contract.py` and copies of the 11 ministry scraper scripts (MOF, PBC, NDRC, MOFCOM, MOHURD, MOT, MOA, SAFE, MNR, MEE, MEM) under `gov_scraw.scripts.*`, with crawl logic identical to the monorepo originals. The monorepo's `mcp/scrapling-uv-mcp/scripts/` SHALL remain unchanged.

#### Scenario: Install without the monorepo

- **WHEN** a user runs `pip install git+<repo-url>` into a fresh venv
- **THEN** the `gov-scraw` console script is on PATH
- **AND** `python -c "import gov_scraw"` succeeds
- **AND** no import of `mcp`, `mcp.models`, or `fastmcp` is required

#### Scenario: All 11 ministries are present

- **WHEN** `gov-scraw list` is run
- **THEN** the output contains exactly the 11 source names: `mee_gsgg_archive`, `mem_tzgg_archive`, `mnr_tzgg_archive`, `moa_govpublic_archive`, `mof_gkml_archive`, `mofcom_xwfb_archive`, `mohurd_xinwen_archive`, `mot_shuju_archive`, `ndrc_tzgg_archive`, `pbc_xinwen_archive`, `safe_whxw_archive`

#### Scenario: Monorepo scripts are untouched

- **WHEN** the change is applied
- **THEN** `git diff mcp/scrapling-uv-mcp/scripts/` shows no modifications

### Requirement: Crawl CLI delegates to each script's existing main

The system SHALL provide a `gov-scraw crawl <name>` subcommand that imports `gov_scraw.scripts.<name>` and invokes its `main()` with a synthesized `sys.argv` (forwarding `--max-pages` / `--all`), producing the same JSON array of records to stdout that the monorepo script produces.

#### Scenario: Crawl forwards page-cap flags

- **WHEN** `gov-scraw crawl mof_gkml_archive --max-pages 2` is run
- **THEN** the script's `argparse` receives `--max-pages 2`
- **AND** each archive is capped at 2 pages
- **AND** a JSON array of records is written to stdout
- **AND** per-archive counts and the total are written to stderr

#### Scenario: Crawl with unknown name fails clearly

- **WHEN** `gov-scraw crawl nope_archive` is run
- **THEN** the command exits non-zero with a message listing the available names

### Requirement: Bundled self-contained datasource registry

The system SHALL ship a generated `gov_scraw/registry/registry.db` (SQLite) and `gov_scraw/registry/registry.json` containing one row per ministry source with: identity (`name`, `label`, `url`, `description`, `category`), and its full column schema. The registry SHALL be regeneratable from the scripts' `MANIFEST`s and SHALL NOT depend on `mcp/daas.db`.

#### Scenario: Registry DB has the three tables

- **WHEN** `sqlite3 registry.db ".tables"` is run
- **THEN** the output includes `sources`, `datasource_columns`, and `scraw_configs`

#### Scenario: Registry contains all 11 sources and their columns

- **WHEN** `SELECT COUNT(*) FROM sources` is run against `registry.db`
- **THEN** it returns 11
- **AND** `SELECT COUNT(*) FROM datasource_columns` returns at least 55 (11 sources × ≥5 columns)
- **AND** each source's columns include a `url` column with `is_primary_key=1`

#### Scenario: Registry rows match the MANIFEST translation

- **WHEN** the registry is regenerated
- **THEN** `datasource_columns` rows for a source equal `MANIFEST.to_columns_json()` for that source
- **AND** `scraw_configs.columns_json` for a source equals `MANIFEST.to_scraw_columns()`

### Requirement: Read API for datasource and column discovery

The system SHALL expose `gov_scraw.list_sources()`, `gov_scraw.get_source(name)`, and `gov_scraw.get_columns(name)` that read the bundled `registry.db` read-only and return structured objects, so consumers can discover datasources and their schemas programmatically without the MCP layer.

#### Scenario: list_sources returns all sources

- **WHEN** `gov_scraw.list_sources()` is called
- **THEN** it returns a list of 11 source objects each with `name`, `label`, `url`, `description`, and `category`

#### Scenario: get_columns returns a source's schema

- **WHEN** `gov_scraw.get_columns("mof_gkml_archive")` is called
- **THEN** it returns a list of column objects each with `name`, `type`, `primary_key`, `nullable`, `description`, `source_field`, `unit`, and `semantic_type`
- **AND** one column has `name == "url"` and `primary_key == True`

#### Scenario: get_source on unknown name raises

- **WHEN** `gov_scraw.get_source("nope")` is called
- **THEN** it raises `KeyError`

### Requirement: Registry rebuild command is idempotent and derived from MANIFESTs

The system SHALL provide `gov-scraw build-registry` (and `build_registry.py`) that imports each `gov_scraw.scripts.<name>` module's `MANIFEST`, writes `sources` / `datasource_columns` / `scraw_configs` rows into `registry.db` and `registry.json`, and is idempotent (re-running produces an identical file). The `MANIFEST` is the source of truth; the DB is derived.

#### Scenario: Rebuild is idempotent

- **WHEN** `gov-scraw build-registry` is run twice in a row
- **THEN** the resulting `registry.json` is byte-identical between runs
- **AND** the logical content of `registry.db` is identical between runs (`sqlite3 ... .dump` produces no diff; only SQLite's file-change-counter header byte differs)

#### Scenario: Rebuild reflects manifest edits

- **WHEN** a column's `description` is edited in a script's `MANIFEST`
- **AND** `gov-scraw build-registry` is run
- **THEN** the corresponding `datasource_columns.description` row in `registry.db` reflects the new text

### Requirement: GitHub-ready project metadata

The system SHALL include a `README.md` (purpose, per-ministry table with name/label/URL, install via `pip install git+<url>`, CLI + API usage, registry schema, rebuild instructions, polite-crawl warning), a `LICENSE`, and a `.gitignore` that excludes Python build artifacts but keeps `registry.db` and `registry.json`.

#### Scenario: README lists every ministry

- **WHEN** the README is read
- **THEN** it contains a table row for each of the 11 sources with its name, label, and seed URL

#### Scenario: Install instructions are present

- **WHEN** the README is read
- **THEN** it contains a `pip install git+<repo-url>` command
- **AND** a `gov-scraw crawl <name>` example
- **AND** a `gov-scraw describe <name>` example
