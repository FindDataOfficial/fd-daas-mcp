## ADDED Requirements

### Requirement: Full-text search over report content
The system SHALL provide a tool `search_reports` that runs a full-text query against one or more `cnreport-{year}` indices and returns matching documents with highlights, source fields, and a total hit count.

#### Scenario: Search by keyword
- **WHEN** the agent calls `search_reports` with query `"营业收入"`
- **THEN** the system returns matching documents with highlighted snippets and the total hit count

#### Scenario: Search scoped to a year
- **WHEN** the agent calls `search_reports` with `year=2024`
- **THEN** only the `cnreport-2024` index is queried

### Requirement: Structured filtering
The `search_reports` tool SHALL support filtering by `company`, `stock_code`, `section`, and `year` in addition to free-text query.

#### Scenario: Filter by company and section
- **WHEN** the agent calls `search_reports` with `company="贵州茅台"` and `section="合并资产负债表"`
- **THEN** only documents matching both filters are returned

### Requirement: Pagination
The `search_reports` tool SHALL support `from`/`size` pagination and SHALL cap `size` at a configurable maximum (default 50).

#### Scenario: Paginate results
- **WHEN** the agent calls `search_reports` with `from=50, size=25`
- **THEN** the system returns the third page of up to 25 results

### Requirement: Delete index tool
The system SHALL provide a tool `delete_index` that drops a `cnreport-{year}` index and removes its `EsIndexMeta` row, requiring an explicit confirmation argument.

#### Scenario: Delete with confirmation
- **WHEN** the agent calls `delete_index` with `year=2023` and `confirm=true`
- **THEN** the `cnreport-2023` index is deleted and its `EsIndexMeta` row removed

#### Scenario: Delete without confirmation
- **WHEN** `delete_index` is called without `confirm=true`
- **THEN** the system returns an error and does not delete the index
