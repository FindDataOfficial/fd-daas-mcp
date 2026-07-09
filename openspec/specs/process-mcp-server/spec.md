# process-mcp-server Specification

## Purpose
TBD - the process-mcp-server requirements are being removed (tools relocated to daas-mcp). This spec is emptied by the move-process-tools-to-daas change.
## Requirements
### Requirement: Capability relocated to daas-llm-extraction
The `process-mcp-server` capability SHALL be considered relocated: all LLM-extraction tools (`list_models`, `list_source_tables`, `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`) and the `--run-rule` CLI branch SHALL be served by `daas-mcp` under the `daas-llm-extraction` capability. No `process-mcp` server SHALL be registered in `.mcp.json`. The `process_rules` and `process_results` tables SHALL remain in `mcp/daas.db` (owned by `daas-mcp`) with no schema change. The `PROCESS_MODELS` env-var name SHALL be retained for backward compatibility.

#### Scenario: LLM-extraction tools are hosted by daas-mcp
- **WHEN** a client calls `extract_text` after the relocation
- **THEN** the tool is served by `daas-mcp`, not a separate `process-mcp` process

#### Scenario: no process-mcp in .mcp.json
- **WHEN** `.mcp.json` is read after the relocation
- **THEN** no `process-mcp` entry is present, and `daas-mcp` exposes the LLM-extraction tools

