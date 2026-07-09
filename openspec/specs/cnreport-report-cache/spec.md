# cnreport-report-cache Specification

## Purpose

On-disk cache for downloaded annual reports in `mcp/cnreport-mcp/` (`report_cache.py`). Every report fetch — `list_outline`, `extract_section`, `get_section`, `get_special_report`, `get_financial_statements` — checks the cache before downloading and stores the PDF + extracted text + outline on a miss, so repeated section extractions don't re-download or re-`pypdf`-parse. Keyed by `{stock_code}_{year}_{form}_{announcement_id}` (URL-hash fallback for raw URL sources; local paths never cached), under `CNREPORT_CACHE_DIR` (default `mcp/cnreport-mcp/.cache/reports/`). No TTL — CNINFO reports are immutable post-publication. Managed via `list_cache` / `clear_cache`.

## Requirements

### Requirement: Cache downloaded reports on disk
The system SHALL maintain an on-disk cache of downloaded annual reports. When a report is requested, the system SHALL first check the cache; on a hit, return the cached extracted text without re-downloading or re-running `pypdf`; on a miss, download the PDF, extract its text, store both the PDF and the extracted text (plus an outline snapshot) in the cache, and return the text.

#### Scenario: Cache miss downloads and stores
- **WHEN** a report is fetched for the first time and no cache entry exists
- **THEN** the system downloads the PDF, extracts text via `pypdf`, stores the `.pdf`, a `.txt`, and a `.outline.json` under a stable filename, and returns the extracted text

#### Scenario: Cache hit reuses stored text
- **WHEN** the same report is fetched again and a cache entry exists
- **THEN** the system returns the cached `.txt` content without making an HTTP request and without re-running `pypdf`

#### Scenario: Cache key uses stock/year/form/announcement_id
- **WHEN** a convenience tool (`get_section`, `get_special_report`, `get_financial_statements`) fetches a report with provenance available
- **THEN** the cache file is named `{stock_code}_{year}_{form}_{announcement_id}.{ext}` so the cache folder is human-browseable

#### Scenario: URL-hash fallback for raw source
- **WHEN** `extract_section` or `list_outline` is called with a raw URL `source` and no stock/year provenance
- **THEN** the cache file is named `url_{sha1(url)[:16]}.{ext}` derived from the URL

#### Scenario: Local-path source is never cached
- **WHEN** the `source` is a local file path
- **THEN** the system reads the file directly and does not write anything to the cache

#### Scenario: Cache directory is created on first miss
- **WHEN** a cache miss occurs and the cache directory does not exist
- **THEN** the system creates the directory before writing the cache files

### Requirement: Configurable cache location
The system SHALL read the cache directory from the `CNREPORT_CACHE_DIR` environment variable; when unset, default to `mcp/cnreport-mcp/.cache/reports/`.

#### Scenario: Default cache directory
- **WHEN** `CNREPORT_CACHE_DIR` is not set
- **THEN** reports are cached under `mcp/cnreport-mcp/.cache/reports/`

#### Scenario: Custom cache directory
- **WHEN** `CNREPORT_CACHE_DIR` is set to an absolute path
- **THEN** reports are cached under that path instead of the default

### Requirement: Cache management tools
The system SHALL provide `list_cache` and `clear_cache` tools to inspect and evict cached reports.

#### Scenario: List cached reports
- **WHEN** `list_cache()` is called
- **THEN** the system returns each cached report's `stock_code`, `year`, `form`, `announcement_id`, `cached_at` (file mtime), and `size` (sum of its `.pdf`+`.txt`+`.outline.json`)

#### Scenario: Clear all cached reports
- **WHEN** `clear_cache()` is called with no arguments
- **THEN** all cache files are deleted and the count removed is returned

#### Scenario: Clear by company
- **WHEN** `clear_cache(stock_code="600519")` is called
- **THEN** only cache entries whose filename starts with that stock code are deleted

#### Scenario: Clear by company and year
- **WHEN** `clear_cache(stock_code="600519", year=2023)` is called
- **THEN** only cache entries matching that stock code and year are deleted

