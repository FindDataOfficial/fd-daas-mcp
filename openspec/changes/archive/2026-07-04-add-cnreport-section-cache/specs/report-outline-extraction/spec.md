## MODIFIED Requirements

### Requirement: List annual report outline
The system SHALL provide a tool that fetches a Chinese annual report from a URL or local path and returns its outline (目录) as a flat list of `{level, title, ordinal}` entries, using the configured scrapling fetcher for URLs. The fetch SHALL consult the report cache first; on a cache hit, the system returns the cached extracted text without re-downloading or re-parsing; on a cache miss, the system downloads, stores the result in the cache, and returns it.

#### Scenario: List outline from a URL
- **WHEN** the agent calls `list_outline` with a report URL and `fetcher="uv"`
- **THEN** the system fetches the document via `scrapling-uv-mcp`, parses the 目录/bookmarks, and returns a list of outline entries with their level and ordinal position

#### Scenario: List outline from a local file
- **WHEN** the agent calls `list_outline` with a local `.pdf`/`.html` path
- **THEN** the system reads the file directly (no fetcher, no cache write) and returns the outline entries

#### Scenario: Unsupported source
- **WHEN** the source is neither a URL nor an existing local path
- **THEN** the system returns an error describing the invalid source without fetching

#### Scenario: Repeated outline call reuses the cache
- **WHEN** `list_outline` is called with the same URL a second time
- **THEN** the system returns the outline parsed from the cached extracted text without re-downloading the PDF
