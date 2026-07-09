# cnreport-financial-statements Specification

## Purpose

Provide `get_financial_statements(ticker, year, form)` in `mcp/cnreport-mcp/` — a convenience tool that extracts the three major financial-statement sections (三大报表: 利润表 / 资产负债表 / 现金流量表) as **text** from a CN-A-share annual-report PDF via the table of contents. Complements `cnreport-company-api`'s `get_financials` (akshare's structured numbers) with the report's actual section text. Prefers consolidated (`合并`) titles, falls back to un-prefixed, and reports any not found. Fetches go through the `cnreport-report-cache`.

## Requirements

### Requirement: Extract the three major financial statements
The system SHALL provide `get_financial_statements(ticker_or_name, year, form="年度报告")` that resolves the company's filing PDF (via the report cache), parses the table of contents, locates the three major financial-statement sections — income statement (利润表), balance sheet (资产负债表), and cash flow statement (现金流量表) — and returns each section's body text, outline entry, and character count. The system SHALL prefer the consolidated (`合并`) title for each statement and fall back to the un-prefixed title. The system SHALL return section text only, never PDF bytes.

#### Scenario: All three statements found (consolidated)
- **WHEN** `get_financial_statements("600519", 2023)` is called and the report TOC contains `合并利润表`, `合并资产负债表`, and `合并现金流量表`
- **THEN** the system returns each statement's body text under `statements.income_statement`, `statements.balance_sheet`, and `statements.cashflow`, each carrying `title`, `outline_entry`, `char_count`, and `text`

#### Scenario: Falls back to un-prefixed titles
- **WHEN** the TOC contains `利润表`, `资产负债表`, and `现金流量表` but no `合并`-prefixed versions
- **THEN** the system extracts those un-prefixed sections and returns them under the same statement keys

#### Scenario: Missing statement reported with available titles
- **WHEN** one or more of the three statements cannot be located in the TOC
- **THEN** the system returns a `missing` array naming the missing statements, includes an `available` array listing every outline title, and omits the missing statements from the `statements` object

#### Scenario: Returns text only, never PDF bytes
- **WHEN** any statement is extracted
- **THEN** the response for that statement contains `text` (body content) and `char_count`, and never contains PDF bytes or a base64-encoded PDF

#### Scenario: Company not found
- **WHEN** `ticker_or_name` does not resolve to a company
- **THEN** the system returns an `error` without making a network call

#### Scenario: Filing not found
- **WHEN** no filing exists for the resolved company, year, and form
- **THEN** the system returns an `error` describing the missing filing

#### Scenario: Reuses the report cache
- **WHEN** the report for `(ticker, year, form)` is already in the cache
- **THEN** the system does not re-download the PDF and uses the cached extracted text to locate and extract the three sections

