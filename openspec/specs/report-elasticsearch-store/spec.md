## ADDED Requirements

### Requirement: Index report records into Elasticsearch
The system SHALL provide a tool `index_records` that writes extracted/processed report records into the `cnreport-{year}` Elasticsearch index with a fixed mapping, deriving the document `_id` from `{report_id}:{section_id}:{seq}`.

#### Scenario: Index a batch of records
- **WHEN** the agent calls `index_records` with a list of records and a year
- **THEN** the system bulk-indexes them into `cnreport-{year}` and returns the count of succeeded/failed documents

#### Scenario: Index creates mapping on first use
- **WHEN** the target index does not exist
- **THEN** the system creates it with the standard `cnreport` mapping (ik_smart analyzer with standard fallback) before indexing

### Requirement: Idempotent indexing
Re-indexing the same record (same `_id`) SHALL update the document in place rather than create a duplicate.

#### Scenario: Re-index an existing record
- **WHEN** a record with the same `_id` is indexed again
- **THEN** the document is updated and the index document count does not increase

### Requirement: Graceful degradation without Elasticsearch
All ES tools SHALL return a descriptive connection error when Elasticsearch is unreachable, and SHALL NOT crash the MCP server or affect non-ES tools.

#### Scenario: ES unavailable
- **WHEN** `index_records` is called and Elasticsearch is unreachable
- **THEN** the tool returns an error describing the connection failure, and other tools (`list_outline`, `ai_extract`) continue to work

### Requirement: Record index metadata
The system SHALL record each indexed document set in `EsIndexMeta` (`index_name`, `doc_count`, `created_at`, `mapping_hash`) in `mcp/daas.db`.

#### Scenario: After a successful index
- **WHEN** a bulk index completes
- **THEN** an `EsIndexMeta` row is upserted with the index name, document count, and mapping hash
