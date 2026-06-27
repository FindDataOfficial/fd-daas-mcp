## ADDED Requirements

### Requirement: MCP server exposes trading analysis tools

The system SHALL provide a FastMCP server at `mcp/trading-mcp/server.py` that registers at least 5 tools discoverable by Claude Code.

#### Scenario: Server starts and registers tools

- **WHEN** the server starts with `python3 server.py`
- **THEN** all tools (`analyze_ticker`, `bull_bear_debate`, `risk_debate`, `full_pipeline`, `list_personas`) are registered and callable

#### Scenario: Server follows existing MCP pattern

- **WHEN** the server is started
- **THEN** it uses FastMCP with stdio transport, matching the pattern of `mcp/leader-mcp/server.py` and `mcp/akshare-mcp/server.py`

### Requirement: Self-registration in unified registry

The system SHALL upsert tool entries into `daas.db` on startup with `harness="trading"`, making tools discoverable via `leader-mcp`.

#### Scenario: First startup registers tools

- **WHEN** the server starts and no trading tools exist in the database
- **THEN** rows are inserted into the `functions` table with `harness="trading"` and `command` matching each tool name

#### Scenario: Subsequent startups are idempotent

- **WHEN** the server starts and trading tools already exist
- **THEN** existing rows are updated (upserted), no duplicates are created

### Requirement: Structured output schemas

The system SHALL define Pydantic models for all agent outputs in `schemas.py`.

#### Scenario: Persona analysis has required fields

- **WHEN** an investor persona completes analysis
- **THEN** the output conforms to a schema with fields: `ticker`, `investor_name`, `action` (BUY/HOLD/SELL), `conviction` (1-10), `thesis`, `key_metrics`, `risks`

#### Scenario: Pipeline decision has required fields

- **WHEN** the full pipeline completes
- **THEN** the output conforms to a schema with fields: `ticker`, `rating` (Buy/Overweight/Hold/Underweight/Sell), `executive_summary`, `investment_thesis`, `risk_assessment`
