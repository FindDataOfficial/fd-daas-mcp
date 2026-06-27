## ADDED Requirements

### Requirement: MCP client connects to leader-mcp via stdio

The system SHALL spawn a long-lived MCP client that connects to `leader-mcp` (configurable) via stdio transport, discovers all tools, and provides them to the AI SDK.

#### Scenario: Client starts and discovers tools

- **WHEN** the MCP client connects to `leader-mcp` server
- **THEN** all 12+ tools (`list_harnesses`, `search_functions`, `get_function_detail`, `list_categories`, `find_functions_by_column`, `list_datasources`, `toggle_datasource`, `save_snapshot`, `list_snapshots`, `query_snapshots`, `get_column_provenance`, `update_column_meta`) are available as AI SDK tools

#### Scenario: Client is a singleton

- **WHEN** multiple API requests arrive concurrently
- **THEN** they share the same MCP client instance — a new Python subprocess is not spawned for each request

#### Scenario: Client reconnects on failure

- **WHEN** the MCP server process crashes or the connection drops
- **THEN** the next request automatically reconnects before processing

#### Scenario: Configurable MCP server

- **WHEN** `MCP_SERVER=akshare-mcp` is set in `.env.local`
- **THEN** the client spawns `akshare-mcp` instead of `leader-mcp`

### Requirement: MCP tools are passed to streamText

The system SHALL convert MCP tools to AI SDK tools and include them in every `streamText` call.

#### Scenario: AI calls an MCP tool

- **WHEN** user asks "list all available harnesses"
- **THEN** the AI calls `list_harnesses` tool, receives the result, and incorporates it into the response

#### Scenario: AI calls multiple tools in sequence

- **WHEN** user asks "search for stock price functions and get details for the first one"
- **THEN** the AI calls `search_functions` first, then uses the result to call `get_function_detail`

#### Scenario: Tool result is too large

- **WHEN** a tool returns more than 10KB of data
- **THEN** the system truncates the result to 10KB with a "[truncated]" marker before sending to the AI, to avoid token limits

### Requirement: Tool calls are visualized in the chat UI

The system SHALL display each tool invocation as an expandable card showing the tool name, arguments, and result.

#### Scenario: Tool call in progress

- **WHEN** the AI is executing a tool call
- **THEN** an expandable card appears showing "Calling `tool_name`..." with a loading indicator

#### Scenario: Tool call completed

- **WHEN** the tool returns a result
- **THEN** the card shows the tool name, formatted arguments, and the result (truncated if large), collapsed by default

#### Scenario: Tool call fails

- **WHEN** a tool execution fails (e.g., connection error)
- **THEN** the card shows the error message in red with a "Retry" button
