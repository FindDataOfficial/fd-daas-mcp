## ADDED Requirements

### Requirement: combine-mcp serves one selected composite

The system SHALL provide a FastMCP stdio server at `mcp/combine-mcp/server.py` that reads a composite name from the `COMPOSITE` environment variable at startup and serves that composite's curated tool surface.

#### Scenario: Server starts with a composite

- **WHEN** `COMPOSITE=trading-plus` is set and the server starts
- **THEN** the server loads the `trading-plus` composite's upstreams, selected tools, and chains from `daas.db` and registers them as served tools

#### Scenario: No composite selected

- **WHEN** `COMPOSITE` is unset and no composite exists
- **THEN** the server starts with only management tools registered and SHALL log that no composite is active

### Requirement: Management tools are always present

The system SHALL register composite-management tools on every combine-mcp instance regardless of the active composite: `list_composites`, `create_composite`, `list_upstreams`, `add_upstream`, `remove_upstream`, `list_available_tools`, `add_tool`, `remove_tool`, `list_composite_tools`, `add_chained_tool`, `remove_chained_tool`, `list_chained_tools`.

#### Scenario: Curate a composite at runtime

- **WHEN** `add_upstream("example", "akshare", transport="stdio", command="uv", args=[...])` then `add_tool("example", "akshare", "stock_zh_a_hist")` are called
- **THEN** the rows are persisted to `daas.db` and the tool SHALL be served on the next process start with the `COMPOSITE=example` instance

### Requirement: Served tool names avoid collisions via namespace prefix

The system SHALL expose proxied upstream tools under the name `<upstream>_<tool>` using the FastMCP mount namespace, so that two upstreams exposing the same tool name do not collide.

#### Scenario: Two upstreams expose the same tool name

- **WHEN** `akshare` and `daas` both expose a tool named `fetch_data` and both are added to a composite
- **THEN** the composite SHALL expose `akshare_fetch_data` and `daas_fetch_data` as distinct tools

Note: An explicit alias overriding the exposed name is deferred to a later change; namespace prefixing already prevents collisions. The `composite_tools.alias` column is retained in the schema but unused in v1.
