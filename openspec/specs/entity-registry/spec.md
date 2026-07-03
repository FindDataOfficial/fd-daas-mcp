# entity-registry Specification

## Purpose
TBD - created by archiving change add-entity-datasource-link. Update Purpose after archive.
## Requirements
### Requirement: Entity table stores stocks and countries
The system SHALL store entities in a single `entities` table in `daas.db` with an `entity_type` discriminator (`stock` | `country`), a canonical `code` (6-digit A-share code, 5-digit HK code, US ticker, or ISO 3166-1 alpha-2 country code), a display `name`, and nullable market-specific fields (`ticker`, `exchange`, `country_code`, `isin`). The system SHALL enforce `UNIQUE(entity_type, code)` so upserts are idempotent.

#### Scenario: Stock entity row
- **WHEN** the sync upserts A-share 600519 (Kweichow Moutai)
- **THEN** the `entities` table holds one row with `entity_type='stock'`, `code='600519'`, `name='贵州茅台'`, `exchange='SSE'`, `country_code='CN'`

#### Scenario: Country entity row
- **WHEN** the sync upserts the United States
- **THEN** the `entities` table holds one row with `entity_type='country'`, `code='US'`, `name='United States'`

#### Scenario: Idempotent upsert
- **WHEN** the sync runs twice for the same `(entity_type, code)`
- **THEN** the table contains exactly one row for that key, with the second run's fields applied as an update

### Requirement: Search entities
The system SHALL expose a `search_entities(query, entity_type=None, limit=20)` daas-mcp tool that returns entities matching the query against `name`, `ticker`, `code`, and `aliases_json` (case-insensitive, substring match), optionally filtered by `entity_type`.

#### Scenario: Search by name fragment
- **WHEN** `search_entities(query="茅台")` is called
- **THEN** the system returns stock entities whose `name` or aliases contain `茅台`, each with `id`, `entity_type`, `code`, `name`, `ticker`, `exchange`, `country_code`

#### Scenario: Search by ticker
- **WHEN** `search_entities(query="AAPL")` is called
- **THEN** the system returns the Apple stock entity matched on `ticker` or `code`

#### Scenario: Filter by entity type
- **WHEN** `search_entities(query="US", entity_type="country")` is called
- **THEN** the system returns only country entities matching `US`

#### Scenario: No matches
- **WHEN** `search_entities(query="zzznope")` matches nothing
- **THEN** the system returns `{"entities": [], "count": 0}`

### Requirement: Get entity
The system SHALL expose a `get_entity(entity_id)` daas-mcp tool that returns the full detail of one entity, including its aliases and metadata.

#### Scenario: Existing entity
- **WHEN** `get_entity(entity_id=42)` is called for an existing row
- **THEN** the system returns `id`, `entity_type`, `code`, `name`, `ticker`, `exchange`, `country_code`, `isin`, `status`, `aliases`, `metadata`, `created_at`, `updated_at`

#### Scenario: Entity not found
- **WHEN** `get_entity(entity_id=999999)` is called for a missing id
- **THEN** the system returns `{"success": false, "error": "entity not found"}`

### Requirement: List entities
The system SHALL expose a `list_entities(entity_type=None, exchange=None, country_code=None, limit=100, offset=0)` daas-mcp tool that returns entities filtered by type, exchange, or country, paginated.

#### Scenario: List all stocks on an exchange
- **WHEN** `list_entities(entity_type="stock", exchange="SSE", limit=10)` is called
- **THEN** the system returns up to 10 stock entities on SSE, with total count

#### Scenario: Paginate
- **WHEN** `list_entities(entity_type="stock", limit=100, offset=100)` is called
- **THEN** the system returns the second page of 100 stock entities

