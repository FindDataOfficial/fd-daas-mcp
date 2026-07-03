# cnreport-company-api Specification

## Purpose

Provide an edgartools-style company API for Chinese A-share annual reports in `mcp/cnreport-mcp/`. Adds CNINFO-backed company lookup, filings listing, filing fetch, structured financials (via akshare), and a high-level section retrieval convenience — the CN counterpart to `edgartools-mcp` (US) and `dartlab-mcp` (KR). Sits alongside the existing PDF/AI/ES tools without changing them.

## Requirements

### Requirement: cnreport-mcp exposes an edgartools-style company API

The `mcp/cnreport-mcp/server.py` FastMCP server SHALL register five company-API tools — `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_section` — alongside the existing PDF/AI/ES tools. The five company-API tools SHALL constitute the China-A-share counterpart of `edgartools-mcp`'s company surface. Existing tools (`list_outline`, `extract_section`, `ai_extract`, `index_records`, `search_reports`, `delete_index`) SHALL remain registered and behave unchanged. Two additional disclosure tools — `list_report_types` (see `cnreport-report-type-catalog`) and `get_special_report` (see `cnreport-special-report-retrieval`) — SHALL also be registered, bringing the total to thirteen tools.

#### Scenario: Server starts and registers all thirteen tools

- **WHEN** the server is started with `uv run --directory mcp/cnreport-mcp python server.py`
- **THEN** the thirteen tools — six existing PDF/AI/ES, five company-API, plus `list_report_types` and `get_special_report` — are all registered and callable over stdio

#### Scenario: Server uses FastMCP stdio transport

- **WHEN** the server is started
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, matching the other purpose-built MCPs

### Requirement: get_company resolves a CN-A-share company

The `get_company(ticker_or_name)` tool SHALL return a JSON-serializable dict describing the company — including `stock_code`, `name` (Chinese), `name_en` (if available), `org_id` (CNINFO's internal id), `exchange` (`sse` / `szse` / `bse`), and `category` — by querying the CNINFO disclosure JSON API. It SHALL accept either a 6-digit ticker (`"600519"`) or a name fragment (`"贵州茅台"`).

#### Scenario: Lookup by ticker

- **WHEN** `get_company(ticker_or_name="600519")` is called
- **THEN** it returns a dict whose `stock_code` is `"600519"` and `name` contains `"茅台"`

#### Scenario: Lookup by name fragment

- **WHEN** `get_company(ticker_or_name="贵州茅台")` is called
- **THEN** it returns a dict whose `stock_code` is `"600519"`

#### Scenario: Unknown company returns an error

- **WHEN** `get_company(ticker_or_name="ZZZZZZ")` is called
- **THEN** it returns an `error` field indicating no match was found, without raising

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

### Requirement: get_filing returns a single filing's metadata and PDF URL

The `get_filing(announcement_id, ticker_or_name=None)` tool SHALL fetch one disclosure by its CNINFO `announcement_id`, returning `announcement_id`, `title`, `form`, `published`, `pdf_url`, `stock_code`, and `company_name`. It SHALL NOT download the PDF body itself — agents needing the body call `list_outline` / `extract_section` with the returned `pdf_url`.

#### Scenario: Fetch a filing by id

- **WHEN** `get_filing(announcement_id="<id>", ticker_or_name="600519")` is called with a valid id
- **THEN** it returns the metadata dict including a `pdf_url`

#### Scenario: Unknown announcement returns an error

- **WHEN** `get_filing(announcement_id="invalid")` is called
- **THEN** it returns an `error` field indicating the filing could not be found

### Requirement: get_financials returns structured income / balance / cashflow statements

The `get_financials(ticker_or_name, statement=None, period="annual")` tool SHALL return structured financial statements for a CN-A-share company by delegating to `akshare` (`stock_financial_report_sina` for the three statements; period `annual` or `quarterly`). When `statement` is omitted, all three statements SHALL be returned; when set to `income_statement`, `balance_sheet`, or `cashflow`, only that one SHALL be returned. Each statement SHALL be serialized as `{columns: [...], data: [[...], ...]}` records, matching the shape `edgartools-mcp.get_financials` returns.

#### Scenario: All three annual statements

- **WHEN** `get_financials(ticker_or_name="600519")` is called
- **THEN** it returns `income_statement`, `balance_sheet`, and `cashflow` entries, each with `columns` and `data`

#### Scenario: Single statement

- **WHEN** `get_financials(ticker_or_name="600519", statement="balance_sheet")` is called
- **THEN** it returns only `balance_sheet` with `columns` and `data`

#### Scenario: Quarterly period

- **WHEN** `get_financials(ticker_or_name="600519", period="quarterly")` is called
- **THEN** the returned statements' `columns` include quarterly period labels (e.g. `"20240331"`)

#### Scenario: Missing akshare returns a clear error

- **WHEN** any `get_financials` call is made and `akshare` is not importable
- **THEN** the tool returns an `error` field with an install hint (`pip install akshare`)

### Requirement: get_section retrieves a named section from a company's annual report

The `get_section(ticker_or_name, year, section, form="年度报告")` tool SHALL be a convenience wrapper that (1) resolves the filing PDF URL via `list_filings(ticker_or_name, form, year)`, (2) calls the existing `extract_section(source=pdf_url, selector=section)` path, and (3) returns `{stock_code, company_name, year, form, section, pdf_url, text, outline_entry}`. It SHALL NOT re-implement outline parsing — it reuses the existing `report-outline-extraction` machinery.

#### Scenario: Fetch MD&A from the latest annual report

- **WHEN** `get_section(ticker_or_name="600519", year=2023, section="管理层讨论与分析")` is called
- **THEN** it returns a dict whose `text` contains the body of that section and whose `pdf_url` matches the resolved annual-report PDF

#### Scenario: Unknown section returns an error

- **WHEN** `get_section(ticker_or_name="600519", year=2023, section="No Such Section")` is called
- **THEN** it returns an `error` field indicating the selector did not match any outline entry

#### Scenario: No annual report for that year

- **WHEN** `get_section(ticker_or_name="600519", year=1900, section="管理层讨论与分析")` is called
- **THEN** it returns an `error` field indicating no matching filing was found

### Requirement: CNINFO and akshare access are encapsulated in client modules

The implementation SHALL keep network/registry concerns out of `cnreport_tools.py` (which already mixes outline parsing, AI extraction, and ES). CNINFO HTTP access SHALL live in a new `cninfo_client.py` module exposing `lookup_company`, `query_announcements`, `get_announcement`. akshare access SHALL live in a new `financials_client.py` module exposing `get_statements(ticker, period)`. The new tool functions in `cnreport_tools.py` SHALL be thin wrappers over these clients plus serialization.

#### Scenario: Client module is the only network entry point

- **WHEN** any of the four CNINFO-backed tools (`get_company`, `list_filings`, `get_filing`, `get_section`'s URL-resolution step) is invoked
- **THEN** all outbound HTTP calls go through `cninfo_client.py`, not directly from `cnreport_tools.py`

#### Scenario: Financials client is the only akshare entry point

- **WHEN** `get_financials` is invoked
- **THEN** the akshare import and call happen inside `financials_client.py`, never at module top-level in `cnreport_tools.py` (so the server starts even when akshare is unavailable)

### Requirement: Tools never raise — errors are returned as JSON

Every new tool SHALL catch exceptions from network, parsing, or missing-dependency paths and return a dict with an `error` string field instead of raising. This matches the pattern used by `edgartools-mcp` and `edinet-mcp` and keeps MCP transport errors distinct from upstream-source errors.

#### Scenario: Network failure surfaces as an error field

- **WHEN** CNINFO is unreachable and `get_company` is called
- **THEN** the tool returns `{"error": "<message>"}` and the MCP server remains healthy

### Requirement: Offline tests cover each new tool

`mcp/cnreport-mcp/test_cnreport.py` SHALL include offline tests for each of the five new tools, mocking `cninfo_client` (httpx-level) and `financials_client` (akshare-level) so the suite runs without network. The existing `python server.py --selfcheck` SHALL be extended to exercise the new tools against the same mocks.

#### Scenario: Test suite runs offline

- **WHEN** `uv run --directory mcp/cnreport-mcp pytest` is executed with no network
- **THEN** all new-tool tests pass, with no real HTTP traffic

#### Scenario: Self-check exercises the new tools

- **WHEN** `uv run --directory mcp/cnreport-mcp python server.py --selfcheck` is executed
- **THEN** it reports OK for each of the five new tools using the mocked clients
