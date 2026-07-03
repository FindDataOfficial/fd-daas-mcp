# edinet-mcp-server

## Purpose

Purpose-built FastMCP (stdio) server wrapping the `edinet_tools` library to expose Japan's EDINET disclosure system — entity lookup, document listings, and parsed reports — as five domain tools. Follows the purpose-built pattern (like `edgartools-mcp`/`daas-mcp`), not the registry pattern, because `edinet_tools` exposes a small object/functional model rather than a flat function catalog.

## Requirements

### Requirement: FastMCP edinet server with five purpose-built tools

The system SHALL provide a FastMCP server at `mcp/edinet-mcp/server.py` using stdio transport, exposing five tools: `search_entities`, `get_entity`, `list_documents`, `get_document`, and `supported_doc_types`, wrapping the `edinet_tools` library. This follows the purpose-built pattern (like `edgartools-mcp`/`daas-mcp`), not the registry pattern, because `edinet_tools` exposes a small object/functional model rather than a flat function catalog.

#### Scenario: Server starts and registers tools

- **WHEN** the server is started with `python3 server.py`
- **THEN** all five tools are registered and callable over stdio

#### Scenario: Server uses FastMCP stdio transport

- **WHEN** the server is started
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, matching the other MCPs

### Requirement: EDINET API key is loaded from env and enforced only for key-requiring tools

The server SHALL read `EDINET_API_KEY` from the environment (loaded from root `.env` first, then the per-MCP `.env` with `override=True`) at module load. The `list_documents` and `get_document` tools SHALL require the key and return a clear `error` advising the user to set `EDINET_API_KEY` when it is unset, rather than emitting unauthenticated document requests. The `search_entities`, `get_entity`, and `supported_doc_types` tools SHALL function without a key.

#### Scenario: Key loaded from env

- **WHEN** the server starts with `EDINET_API_KEY` set in the environment
- **THEN** the key is available to the document tools for EDINET API calls

#### Scenario: Document tool called without key surfaces a clear error

- **WHEN** `list_documents` or `get_document` is called and `EDINET_API_KEY` was never set
- **THEN** the tool returns an `error` field instructing the user to set `EDINET_API_KEY` in `.env`

#### Scenario: Entity tools work without a key

- **WHEN** `get_entity` or `search_entities` is called and `EDINET_API_KEY` is unset
- **THEN** the tool proceeds without error and returns results

### Requirement: search_entities returns entity matches

The `search_entities(query, limit=10)` tool SHALL call `edinet_tools.search(query, limit=limit)` and return a JSON-serializable list of entity matches (each with at least the EDINET code and name), handling full-width/half-width and gaiji text via the library.

#### Scenario: Name search

- **WHEN** `search_entities(query="bank", limit=5)` is called and `edinet_tools` is installed
- **THEN** it returns a list of up to 5 entity dicts matching the query

### Requirement: get_entity returns entity facts by ticker or code

The `get_entity(ticker_or_code)` tool SHALL look up an entity via `edinet_tools.entity(...)` (and SHALL fall back to `entity_by_corporate_number(...)` when the input looks like a 13-digit 法人番号) and return a JSON-serializable dict of entity facts — including name, EDINET code, and corporate number where available.

#### Scenario: Lookup by ticker

- **WHEN** `get_entity(ticker_or_code="7203")` is called and `edinet_tools` is installed
- **THEN** it returns a dict identifying Toyota Motor Corporation with its EDINET code

#### Scenario: Lookup by corporate number

- **WHEN** `get_entity` is called with a 13-digit corporate number
- **THEN** it resolves via `entity_by_corporate_number` and returns the matching entity

### Requirement: list_documents returns filings for a date

The `list_documents(date, doc_type=None, limit=50)` tool SHALL call `edinet_tools.documents(date)` and return a JSON-serializable list of filings for that date (YYYY-MM-DD), each including at least the document ID, doc-type code, and filer name. When `doc_type` is provided, the results SHALL be filtered to that EDINET document-type code.

#### Scenario: List filings for a date

- **WHEN** `list_documents(date="2026-01-20", limit=10)` is called with a valid `EDINET_API_KEY`
- **THEN** it returns a list of up to 10 filing dicts for that date

#### Scenario: Filter by document type

- **WHEN** `list_documents(date="2026-01-20", doc_type="120", limit=50)` is called
- **THEN** every returned filing has doc-type code `120`

### Requirement: get_document parses a single document

The `get_document(doc_id, doc_type_code=None, detail="standard")` tool SHALL fetch the document by ID, parse it via `doc.parse()`, and return a JSON-serializable dict of the parsed fields (preferring `to_dict()`). It SHALL honor a `detail` parameter (`minimal`/`standard`/`full`): `minimal` excludes `raw_fields`/`text_blocks`; `standard` and `full` include them. It SHALL return an `error` when the document cannot be fetched or parsed.

#### Scenario: Parse a securities report

- **WHEN** `get_document(doc_id="S100ABC")` is called with a valid `EDINET_API_KEY` and a parseable document
- **THEN** it returns a dict of parsed fields including any typed fields the parser exposes

#### Scenario: Minimal detail omits raw payloads

- **WHEN** `get_document(doc_id="S100ABC", detail="minimal")` is called
- **THEN** the returned dict excludes `raw_fields` and `text_blocks`

#### Scenario: Missing edinet-tools returns a clear error

- **WHEN** any tool is called and `edinet_tools` is not installed
- **THEN** the tool returns an `error` field with a hint to install `edinet-tools`

### Requirement: supported_doc_types returns all document-type metadata

The `supported_doc_types()` tool SHALL call `edinet_tools.supported_doc_types()` and return a JSON-serializable list of all EDINET document-type codes with their names/descriptions. It SHALL function without an API key.

#### Scenario: List all supported doc types

- **WHEN** `supported_doc_types()` is called and `edinet_tools` is installed
- **THEN** it returns a list of document-type entries covering all 42 EDINET codes

### Requirement: Results are JSON-serialized via a shared serializer

The server SHALL provide a `_serialize()` helper that converts `edinet_tools` results to JSON-serializable values: objects exposing `to_dict()` are serialized via that method; `pandas.DataFrame` becomes `{type:"dataframe", shape, columns, data: records}` with NaN→null; `pandas.Series` becomes `{type:"series",...}`; dataclasses and `__dict__`-bearing objects are flattened (depth-capped); lists/tuples have their elements serialized; everything else falls back to `str()`. Every tool SHALL return its result through `_serialize()`.

#### Scenario: Dataclass result is flattened

- **WHEN** a tool receives a parsed-report dataclass from `doc.parse()`
- **THEN** `_serialize` produces a plain dict of its fields without raising

#### Scenario: DataFrame result is converted to records

- **WHEN** a tool receives a `pandas.DataFrame`
- **THEN** `_serialize` returns a dict with `type:"dataframe"` and a `data` list of record dicts, with NaN values mapped to null
