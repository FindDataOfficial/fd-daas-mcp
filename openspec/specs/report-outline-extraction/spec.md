## ADDED Requirements

### Requirement: List annual report outline
The system SHALL provide a tool that fetches a Chinese annual report from a URL or local path and returns its outline (目录) as a flat list of `{level, title, ordinal}` entries, using the configured scrapling fetcher for URLs.

#### Scenario: List outline from a URL
- **WHEN** the agent calls `list_outline` with a report URL and `fetcher="uv"`
- **THEN** the system fetches the document via `scrapling-uv-mcp`, parses the 目录/bookmarks, and returns a list of outline entries with their level and ordinal position

#### Scenario: List outline from a local file
- **WHEN** the agent calls `list_outline` with a local `.pdf`/`.html` path
- **THEN** the system reads the file directly (no fetcher) and returns the outline entries

#### Scenario: Unsupported source
- **WHEN** the source is neither a URL nor an existing local path
- **THEN** the system returns an error describing the invalid source without fetching

### Requirement: Extract section by selector
The system SHALL provide a tool that, given a report source and a section selector (exact title, regex, or ordinal index), returns the body text of that outline node up to the next sibling.

#### Scenario: Extract by exact title
- **WHEN** the agent calls `extract_section` with selector `第三节 管理层讨论与分析`
- **THEN** the system returns the full text content of that section

#### Scenario: Extract by ordinal
- **WHEN** the agent calls `extract_section` with an ordinal index
- **THEN** the system returns the text of the outline node at that position

#### Scenario: Selector matches nothing
- **WHEN** no outline node matches the selector
- **THEN** the system returns an error listing the available section titles

### Requirement: Record extraction provenance
The system SHALL persist each extracted report and section into `mcp/daas.db` (`ReportDocument`, `ReportSection`) with source, company, stock code, year, ordinal, level, title, and parse status.

#### Scenario: First extraction of a report
- **WHEN** a report is extracted for the first time
- **THEN** a `ReportDocument` row and one `ReportSection` row per extracted section are created

#### Scenario: Re-extraction is idempotent
- **WHEN** the same report+section is extracted again
- **THEN** the existing rows are updated rather than duplicated
