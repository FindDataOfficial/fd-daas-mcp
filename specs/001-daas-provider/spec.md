# Feature Specification: DAAS Provider

**Feature Branch**: `001-daas-provider`

**Created**: 2026-06-23

**Status**: Draft

**Input**: User description: "create a project in daas-provider to get data from opensource projects like akshare, also get data from opensource urls like world bank data, ckan, chinese statistics. output pandas, create cli and skills to use the data, save function and columns information in database, create a script to store and save them"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover and search data functions across all sources (Priority: P1)

A user wants to find what data is available across all sources (AKShare, World Bank, CKAN, Chinese Statistics) without knowing which source has what. They run a search and get unified results.

**Why this priority**: Without discovery, users can't find data. This is the entry point for everything else.

**Independent Test**: `cli-anything-daas search GDP` returns matching functions from all sources. Delivers immediate value — users know what's available.

**Acceptance Scenarios**:

1. **Given** all sources are configured, **When** user runs `cli-anything-daas search GDP`, **Then** results show GDP-related functions from World Bank, CKAN, and cnstats with source labels
2. **Given** akshare is installed but wbgapi is not, **When** user runs `cli-anything-daas list-sources`, **Then** worldbank shows as "available but not installed" with install hint
3. **Given** registry is populated, **When** user runs `cli-anything-daas categories`, **Then** categories across all sources are listed with function counts

---

### User Story 2 - Fetch data from any source and get a pandas DataFrame (Priority: P1)

A user calls a data function and gets results as a pandas DataFrame, regardless of which source it comes from. The CLI handles source routing transparently.

**Why this priority**: Data retrieval is the core value proposition. Same priority as discovery — both needed for MVP.

**Independent Test**: `cli-anything-daas call worldbank_gdp country=CN date=2020:2023` returns a DataFrame. Delivers immediate value — user has the data.

**Acceptance Scenarios**:

1. **Given** registry has `worldbank_gdp` function, **When** user runs `cli-anything-daas call worldbank_gdp country=CN date=2020:2023`, **Then** a pandas DataFrame with GDP data is output as a table
2. **Given** `--json` flag, **When** user runs the same call with `--json`, **Then** output is valid JSON array of records
3. **Given** a function from akshare (which is already installed), **When** user calls `stock_zh_a_hist symbol=000001`, **Then** data is fetched via akshare adapter and returned as DataFrame

---

### User Story 3 - Store and persist function metadata in database (Priority: P2)

An admin runs the store_registry script to discover all available functions across sources and persist them to both JSON and SQLite. This enables search, leader-mcp integration, and offline browsing.

**Why this priority**: Enables search (P1) and MCP integration. Could be done once manually, but automation is needed for updates.

**Independent Test**: Run `store_registry.py`, then verify `registry.json` and `daas_registry.db` contain functions with columns. Verify leader-mcp can query DAAS functions.

**Acceptance Scenarios**:

1. **Given** sources are configured, **When** `store_registry.py` runs, **Then** `registry.json` is created with all discovered functions and their column schemas
2. **Given** `registry.json` exists, **When** `store_registry.py` runs again, **Then** existing entries are upserted (no duplicates), new functions are added
3. **Given** leader-mcp is running, **When** daas registry is imported via `import_harness_registry`, **Then** leader-mcp search returns DAAS functions alongside akshare

---

### User Story 4 - Use data via Claude Code skill (Priority: P2)

A Claude Code user invokes `/cli-anything-daas` to search and fetch data without leaving the chat. The skill provides agent guidance on discovery and usage.

**Why this priority**: Skills are how Claude Code users interact with CLI tools. Follows the existing akshare skill pattern.

**Independent Test**: In Claude Code, `/cli-anything-daas search GDP` returns results. `/cli-anything-daas call worldbank_gdp country=CN` fetches data.

**Acceptance Scenarios**:

1. **Given** daas-mcp is configured, **When** Claude Code agent invokes `search_functions` tool, **Then** matching functions from all sources are returned
2. **Given** daas-mcp is configured, **When** Claude Code agent invokes `fetch_data` tool with valid function and params, **Then** data is returned as JSON

---

### User Story 5 - Extensible source adapter for new data sources (Priority: P3)

A developer wants to add a new data source (e.g., FRED, Eurostat) by implementing a single adapter class without modifying the CLI or MCP server.

**Why this priority**: Extensibility is important but not blocking for MVP. The 4 initial sources prove the pattern.

**Independent Test**: Create a new adapter class inheriting from `SourceAdapter`, implement `discover()`, `fetch()`, `columns()`. Register it. Search and call work for the new source.

**Acceptance Scenarios**:

1. **Given** a new `FredAdapter(SourceAdapter)` with all three methods implemented, **When** registered in sources config, **Then** `list-sources` shows it, `search` finds its functions, `call` fetches its data
2. **Given** a source adapter raises `SourceUnavailableError`, **When** user tries to call its functions, **Then** a clear error message is shown, other sources still work

---

### Edge Cases

- What happens when a source's API is down? → `SourceUnavailableError`, other sources continue working
- What happens when optional dependencies (wbgapi, ckanapi) are not installed? → Source shows as "not installed" with install hint, functions still appear in registry (metadata was pre-stored)
- What happens when `store_registry.py` runs with no internet? → Sources that require live discovery fail gracefully, cached sources succeed
- How does system handle parameter type mismatches? → Parameter validation before calling source, clear error message with expected types
- What happens with duplicate function names across sources? → Functions are namespaced as `source_functionname` (e.g., `worldbank_gdp`, `ckan_gdp`)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a CLI (`cli-anything-daas`) with commands: `list-sources`, `search`, `call`, `describe`, `categories`
- **FR-002**: System MUST support `--json` flag for machine-readable output on all commands
- **FR-003**: System MUST provide REPL mode when CLI is invoked without subcommand
- **FR-004**: System MUST route function calls to the correct source adapter transparently
- **FR-005**: System MUST output data as pandas DataFrames (table format or JSON)
- **FR-006**: System MUST persist function metadata (name, category, description, parameters) and column metadata (name, type, description) in SQLite database
- **FR-007**: System MUST provide a `store_registry.py` script that discovers functions from all sources and upserts them into the registry
- **FR-008**: System MUST provide an MCP server (`daas-mcp`) with tools: `list_sources`, `search_functions`, `get_function_detail`, `fetch_data`, `list_categories`
- **FR-009**: System MUST provide a Claude Code skill (`cli-anything-daas`) for agent-driven data discovery and retrieval
- **FR-010**: System MUST support at least 4 data sources: AKShare, World Bank, CKAN, Chinese National Statistics
- **FR-011**: System MUST allow new sources to be added by implementing a `SourceAdapter` base class
- **FR-012**: System MUST integrate with leader-mcp unified registry via `import_harness_registry`
- **FR-013**: System MUST handle missing optional dependencies gracefully (source shown as available but not installed)
- **FR-014**: System MUST NOT modify the upstream `CLI-Anything/` directory

### Key Entities

- **Source**: A data provider (akshare, worldbank, ckan, cnstats) with name, label, description, URL, enabled status, and source-specific config (JSON)
- **Function**: A callable data function within a source, with name, category, description, parameter schema (JSON), and output type. Unique per (source, name)
- **FunctionColumn**: Describes a column returned by a function — name, type, description, nullable. Unique per (function, column_name)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can discover available data functions across all 4 sources with a single `search` command in under 1 second
- **SC-002**: Users can fetch data from any source with a single `call` command and receive a pandas DataFrame
- **SC-003**: `store_registry.py` completes discovery and persistence for all configured sources in under 60 seconds
- **SC-004**: The daas-mcp server responds to tool calls within the MCP protocol timeout (10s for search, 30s for fetch)
- **SC-005**: All existing akshare-agent-harness tests continue to pass (no regressions)
- **SC-006**: Leader-mcp can search across akshare + daas functions in a single query

## Assumptions

- Users have Python >=3.10 and uv installed
- Network access is available for live data fetching (registry can be pre-built offline)
- AKShare is already installed and working (existing dependency)
- World Bank, CKAN, and cnstats sources are optional — graceful degradation when not installed
- The project follows the existing monorepo structure: `daas-agent-harness/` + `mcp/daas-mcp/`
- Leader-mcp unified schema is stable and won't change during this feature's development
- `wbgapi` and `ckanapi` are the chosen Python packages for World Bank and CKAN respectively
