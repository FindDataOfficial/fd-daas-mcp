## ADDED Requirements

### Requirement: Entity-datasource link table
The system SHALL store many-to-many links between `entities` and the daas `sources` table in an `entity_datasource_links` table with columns `entity_id` (FK → `entities.id`, CASCADE), `source_id` (FK → `sources.id`, CASCADE), `identifier_in_source` (the value to plug into that datasource's lookup tool), `coverage` (`full` | `partial` | `none`, default `full`), `metadata_json`, `last_fetched_at`, enforced `UNIQUE(entity_id, source_id)`.

#### Scenario: Link row
- **WHEN** Apple (stock) is linked to the `edgar` datasource
- **THEN** `entity_datasource_links` holds a row with `identifier_in_source='AAPL'`, `coverage='full'`, referencing the Apple entity id and the `edgar` source id

#### Scenario: Unique per pair
- **WHEN** the same `(entity_id, source_id)` is linked twice
- **THEN** the second call updates the existing row (upsert) rather than creating a duplicate

#### Scenario: Cascade on entity delete
- **WHEN** an entity is deleted
- **THEN** all its `entity_datasource_links` rows are deleted by the foreign-key cascade

### Requirement: Get entity coverage
The system SHALL expose a `get_entity_coverage(entity_id)` daas-mcp tool that, for each datasource linked to the entity, returns the `source` name, `identifier_in_source`, the list of available sections (each with `form_type`, `section_name`, and routing `instruction`), and a `column_count` with `columns` aggregated from `daas_function_columns` for that source's `daas_functions`. For sources with no `daas_functions`, the system SHALL return `column_count=0` and a `column_hint` naming the sibling MCP and tool parsed from the section instruction.

#### Scenario: Coverage for a US stock
- **WHEN** `get_entity_coverage(entity_id=<Apple>)` is called
- **THEN** the system returns the `edgar` and `yfinance` datasources, each with `identifier_in_source`, their sections' routing instructions, and a `column_hint` naming `edgartools-mcp` / `yfinance-mcp` and the relevant tool (since these sources have no `daas_functions`)

#### Scenario: Coverage includes real columns for daas-internal sources
- **WHEN** `get_entity_coverage(entity_id=<China country>)` is called and `cnstats` is linked
- **THEN** the system returns `cnstats` with a `column_count > 0` and a `columns` list drawn from `daas_function_columns` for `cnstats`'s registered functions

#### Scenario: Routing instruction is directly usable
- **WHEN** the coverage result includes an edgar section
- **THEN** the section's `instruction` is a routing grammar string with the entity's `identifier_in_source` substituted for the `<ask-agent>` placeholder (e.g. `mcp=edgartools-mcp tool=get_company param=ticker_or_cik=AAPL`)

#### Scenario: Entity with no links
- **WHEN** `get_entity_coverage(entity_id=<unlinked>)` is called for an entity with no datasource links
- **THEN** the system returns `{"entity_id": ..., "datasources": [], "count": 0}`

### Requirement: Manual link entity to datasource
The system SHALL expose a `link_entity_datasource(entity_id, source_name, identifier_in_source, coverage="full", metadata=None)` daas-mcp tool that creates or updates a link row, resolving `source_name` to the `sources` table.

#### Scenario: Create a link
- **WHEN** `link_entity_datasource(entity_id=42, source_name="yfinance", identifier_in_source="AAPL")` is called
- **THEN** a link row is created with the resolved `source_id`, `identifier_in_source='AAPL'`, `coverage='full'`

#### Scenario: Update an existing link
- **WHEN** `link_entity_datasource` is called for an already-linked `(entity_id, source_name)` pair with a new `identifier_in_source`
- **THEN** the existing row is updated with the new identifier and coverage

#### Scenario: Unknown source
- **WHEN** `link_entity_datasource(entity_id=42, source_name="nope")` references a source that does not exist
- **THEN** the system returns `{"success": false, "error": "source 'nope' not found"}`

### Requirement: Unlink entity from datasource
The system SHALL expose an `unlink_entity_datasource(entity_id, source_name)` daas-mcp tool that deletes the link row between the entity and the named source.

#### Scenario: Remove a link
- **WHEN** `unlink_entity_datasource(entity_id=42, source_name="yfinance")` is called for an existing link
- **THEN** the link row is deleted and the system returns `{"success": true}`

#### Scenario: Link not found
- **WHEN** `unlink_entity_datasource` is called for a pair that is not linked
- **THEN** the system returns `{"success": false, "error": "link not found"}`
