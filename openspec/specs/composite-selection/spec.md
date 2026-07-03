## ADDED Requirements

### Requirement: Composite selection is persisted in the shared database

The system SHALL persist composite definitions, their upstreams, and their selected tools in `mcp/daas.db` via the shared schema package `mcp/models/`.

#### Scenario: Selection survives restart

- **WHEN** a user adds tool `stock_zh_a_hist` from upstream `akshare` to composite `example`, then restarts the `COMPOSITE=example` server
- **THEN** `stock_zh_a_hist` SHALL still be served without re-adding it

### Requirement: Upstream definitions are scoped per composite

The system SHALL scope upstream definitions to a single composite. Two composites wanting the same upstream each define their own upstream row.

#### Scenario: Same upstream in two composites

- **WHEN** composite `a` and composite `b` both need `akshare` as an upstream
- **THEN** each composite SHALL have its own `upstreams` row referencing `akshare`, independently configured

### Requirement: Available tools are enumerated live from the upstream with substring search

The system SHALL provide `list_available_tools(composite, upstream_key, query?)` that opens a `Client` to the upstream, returns the upstream's current tool list via `list_tools()`, and filters by case-insensitive substring match on tool name when `query` is provided. The response SHALL include a `total` count of tools returned.

#### Scenario: Discover tools before selecting

- **WHEN** `list_available_tools("example", "akshare")` is called with no query
- **THEN** it returns all tool names akshare-mcp currently exposes plus a `total` count, so the user can pick which to add

#### Scenario: Filter tools by substring

- **WHEN** `list_available_tools("example", "akshare", query="hist")` is called
- **THEN** it returns only the tool names containing `hist` (e.g. `stock_zh_a_hist`), with `total` reflecting the filtered count

#### Scenario: No silent truncation

- **WHEN** an upstream exposes 673 tools and no `limit`/`offset` is requested
- **THEN** the response SHALL include all 673 names and the `total` count SHALL be 673, not a capped subset

### Requirement: Selection changes apply on restart

The system SHALL rebuild the served tool surface from the database at process startup. Adding or removing a tool via management tools persists the change; the change is reflected in the served surface on the next process start.

#### Scenario: Add then serve

- **WHEN** `add_tool` writes a new `composite_tools` row while the server is running
- **THEN** the newly added tool is NOT callable on the running instance until restart, and SHALL be callable after restart
