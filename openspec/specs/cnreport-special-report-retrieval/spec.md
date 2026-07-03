# cnreport-special-report-retrieval Specification

## Purpose

Provide a `get_special_report` MCP tool in `mcp/cnreport-mcp/` that retrieves a non-periodic ("special") CNINFO disclosure — such as a prospectus (`招股说明书`), acquisition report (`收购报告书`), or earnings forecast (`业绩预告`) — for a CN-A-share company, optionally extracting a named section from the report's PDF. Builds on the `cnreport-report-type-catalog` registry for category resolution and reuses the existing `report-outline-extraction` pipeline for section extraction, rather than reimplementing PDF parsing.

## Requirements

### Requirement: get_special_report retrieves a special-type report for a company

The system SHALL expose a `get_special_report(ticker_or_name, category, year=None, section=None, limit=5)` MCP tool that resolves a CN-A-share company and retrieves a disclosure of a given special `category` (any non-periodic CNINFO type, e.g. `招股说明书`, `收购报告书`, `业绩预告`). The `category` argument SHALL accept either a Chinese name from the catalog or a raw CNINFO code. The tool SHALL query CNINFO's `hisAnnouncement` endpoint filtered by that category, select the most recent matching filing (or the first matching filing within the `year` window when `year` is given), and return its metadata including `stock_code`, `company_name`, `category`, `pdf_url`, and (when `section` is omitted) the list of matched filings.

#### Scenario: Retrieve a special report by Chinese category name

- **WHEN** `get_special_report(ticker_or_name="600519", category="招股说明书")` is called
- **THEN** it returns a dict whose `category` is `招股说明书` and whose `pdf_url` points at a CNINFO static-cdn PDF, with no `error` field

#### Scenario: Retrieve a special report by raw category code

- **WHEN** `get_special_report(ticker_or_name="600519", category="category_zgsm_szsh")` is called
- **THEN** the result is identical to passing the equivalent Chinese name

#### Scenario: Unknown category returns an error

- **WHEN** `get_special_report(ticker_or_name="600519", category="不存在的类型")` is called
- **THEN** it returns an `error` field indicating the category is not in the catalog, without making a network call

#### Scenario: No matching filing returns an error

- **WHEN** `get_special_report(ticker_or_name="600519", category="招股说明书", year=1900)` is called and CNINFO returns no announcements
- **THEN** it returns an `error` field indicating no matching filing was found

#### Scenario: Unknown company returns an error

- **WHEN** `get_special_report(ticker_or_name="ZZZZZZ", category="招股说明书")` is called
- **THEN** it returns an `error` field indicating no company matched

### Requirement: get_special_report supports optional section extraction

When `section` is supplied, `get_special_report` SHALL fetch the resolved filing's PDF, parse its outline, and extract the body text of the section matching the `section` selector (exact title, regex, or 1-based ordinal — the same selector grammar as `extract_section` / `get_section`). The return dict SHALL include `pdf_url`, `outline_entry`, `text`, and `char_count`. When `section` is omitted, the tool SHALL NOT download the PDF and SHALL return only filing metadata + `pdf_url`.

#### Scenario: Extract a named section from a special report

- **WHEN** `get_special_report(ticker_or_name="600519", category="招股说明书", section="募集资金运用")` is called and the section exists
- **THEN** the returned `text` contains that section's body and `outline_entry` describes the matched heading

#### Scenario: Section selector does not match

- **WHEN** `get_special_report(ticker_or_name="600519", category="招股说明书", section="No Such Section")` is called
- **THEN** it returns an `error` field indicating no section matched, plus an `available` list of outline titles and the `pdf_url`

#### Scenario: No section means no PDF download

- **WHEN** `get_special_report(ticker_or_name="600519", category="招股说明书")` is called without `section`
- **THEN** the return dict contains `pdf_url` and filing metadata but no `text`/`char_count`/`outline_entry` fields, and no PDF body is fetched

### Requirement: get_special_report reuses the existing outline pipeline

The section-extraction path of `get_special_report` SHALL reuse the existing `fetch_source → parse_outline → resolve_selector → extract_section_text` functions from `cnreport_tools`. It SHALL NOT reimplement PDF fetching, outline parsing, or section slicing.

#### Scenario: Section extraction goes through the shared pipeline

- **WHEN** `get_special_report(…, section="X")` extracts a section
- **THEN** the implementation calls the same `fetch_source`, `parse_outline`, `resolve_selector`, and `extract_section_text` functions used by `get_section` and `extract_section`, with no duplicated PDF-parsing logic

### Requirement: get_special_report never raises

The `get_special_report` tool SHALL catch exceptions from network, parsing, or missing-dependency paths and return a dict with an `error` string field instead of raising, matching the convention of the other cnreport-mcp tools.

#### Scenario: Network failure surfaces as an error field

- **WHEN** CNINFO is unreachable and `get_special_report` is called
- **THEN** the tool returns `{"error": "<message>"}` and the MCP server remains healthy
