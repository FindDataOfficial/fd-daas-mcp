# process-mcp-indicators Specification

## Purpose
TBD - the process-mcp-indicators requirements are being removed (tools relocated to daas-mcp). This spec is emptied by the move-process-tools-to-daas change.
## Requirements
### Requirement: Capability relocated to daas-indicators
The `process-mcp-indicators` capability SHALL be considered relocated: all indicator tools (`list_indicator_ops`, `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`, `calculate`) and the `--run-indicator` CLI branch SHALL be served by `daas-mcp` under the `daas-indicators` capability. No `process-mcp` server SHALL be registered in `.mcp.json`. The `indicator_rules` table SHALL remain in `mcp/daas.db` (owned by `daas-mcp`) with no schema change.

#### Scenario: indicator tools are hosted by daas-mcp
- **WHEN** a client calls `run_indicator` after the relocation
- **THEN** the tool is served by `daas-mcp`, not a separate `process-mcp` process

#### Scenario: no process-mcp in .mcp.json
- **WHEN** `.mcp.json` is read after the relocation
- **THEN** no `process-mcp` entry is present, and `daas-mcp` exposes the indicator tools

