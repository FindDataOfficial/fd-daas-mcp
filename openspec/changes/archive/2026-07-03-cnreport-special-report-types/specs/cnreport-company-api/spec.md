## MODIFIED Requirements

### Requirement: cnreport-mcp exposes an edgartools-style company API

The `mcp/cnreport-mcp/server.py` FastMCP server SHALL register five company-API tools — `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_section` — alongside the existing PDF/AI/ES tools. The five company-API tools SHALL constitute the China-A-share counterpart of `edgartools-mcp`'s company surface. Existing tools (`list_outline`, `extract_section`, `ai_extract`, `index_records`, `search_reports`, `delete_index`) SHALL remain registered and behave unchanged. Two additional disclosure tools — `list_report_types` (see `cnreport-report-type-catalog`) and `get_special_report` (see `cnreport-special-report-retrieval`) — SHALL also be registered, bringing the total to thirteen tools.

#### Scenario: Server starts and registers all thirteen tools

- **WHEN** the server is started with `uv run --directory mcp/cnreport-mcp python server.py`
- **THEN** the thirteen tools — six existing PDF/AI/ES, five company-API, plus `list_report_types` and `get_special_report` — are all registered and callable over stdio

#### Scenario: Server uses FastMCP stdio transport

- **WHEN** the server is started
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, matching the other purpose-built MCPs

### Requirement: list_filings lists a company's disclosures

The `list_filings(ticker_or_name, form=None, category=None, year=None, limit=20)` tool SHALL list disclosures for a company via CNINFO's `hisAnnouncement` endpoint. Filtering SHALL accept either `form` (the four periodic report names — `年度报告`, `半年度报告`, `第一季度报告`, `第三季度报告` — or a free-text title substring) or `category` (any CNINFO category code or Chinese name from the `cnreport-report-type-catalog` registry, e.g. `招股说明书` or `category_ndbg_szsh`). `form` and `category` SHALL be mutually exclusive: supplying both SHALL return an `error` without a network call. When `category` is supplied, the system SHALL resolve it via the registry and send the resolved code as CNINFO's `category` filter. Each entry SHALL include `announcement_id`, `title`, `form`, `published`, `pdf_url`, and `stock_code`. Results SHALL be capped at `limit`.

#### Scenario: List recent filings

- **WHEN** `list_filings(ticker_or_name="600519", limit=5)` is called
- **THEN** it returns at most 5 filing entries, each with an `announcement_id` and `pdf_url`

#### Scenario: Filter by form type

- **WHEN** `list_filings(ticker_or_name="600519", form="年度报告", limit=3)` is called
- **THEN** every returned entry's `title` or `form` indicates an 年度报告

#### Scenario: Filter by year

- **WHEN** `list_filings(ticker_or_name="600519", form="年度报告", year=2023)` is called
- **THEN** every returned entry's `published` date falls in the announcement window for FY2023 (typically 2024-01 through 2024-06)

#### Scenario: Filter by category name

- **WHEN** `list_filings(ticker_or_name="600519", category="招股说明书", limit=3)` is called
- **THEN** the system resolves `招股说明书` to its CNINFO code via the catalog, sends that code as the `category` filter, and returns matching filings

#### Scenario: Filter by raw category code

- **WHEN** `list_filings(ticker_or_name="600519", category="category_ndbg_szsh", limit=3)` is called
- **THEN** the result is identical to `list_filings(ticker_or_name="600519", form="年度报告", limit=3)`

#### Scenario: Unknown category returns an error

- **WHEN** `list_filings(ticker_or_name="600519", category="不存在的类型")` is called
- **THEN** it returns an `error` field indicating the category is not in the catalog, without making a network call

#### Scenario: Supplying both form and category returns an error

- **WHEN** `list_filings(ticker_or_name="600519", form="年度报告", category="招股说明书")` is called
- **THEN** it returns an `error` field indicating only one of `form` or `category` may be supplied, without making a network call
