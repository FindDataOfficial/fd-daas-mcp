## REMOVED Requirements

### Requirement: Env-driven multi-model registry
**Reason**: The `process-mcp` server is deleted; its LLM-extraction tools and model registry relocate to `daas-mcp`.
**Migration**: Use the `daas-llm-extraction` capability. The `PROCESS_MODELS` env-var name is unchanged.

### Requirement: list_models tool
**Reason**: `list_models` is no longer exposed by `process-mcp` (server deleted).
**Migration**: Call `list_models` on `daas-mcp`. Result shape unchanged.

### Requirement: extract_text handles long text without truncation loss
**Reason**: `extract_text` relocates to `daas-mcp`.
**Migration**: Call `extract_text` on `daas-mcp`. Signature unchanged.

### Requirement: extract_image via a vision model
**Reason**: `extract_image` relocates to `daas-mcp`.
**Migration**: Call `extract_image` on `daas-mcp`. Signature unchanged.

### Requirement: extract_file reads a local file and forwards to text extraction
**Reason**: `extract_file` relocates to `daas-mcp`.
**Migration**: Call `extract_file` on `daas-mcp`. Signature unchanged.

### Requirement: OpenAI-compatible endpoint with JSON fallback
**Reason**: The LLM-call transport is owned by `daas-mcp` after the relocation.
**Migration**: Behavior unchanged; the requirement now lives under `daas-llm-extraction`.

### Requirement: Persisted processing rules in the shared schema
**Reason**: `process_rules`/`process_results` ownership moves to `daas-mcp`. Tables stay in `mcp/daas.db`.
**Migration**: See `daas-llm-extraction` — "Persisted processing rules in the shared schema". Table names retained.

### Requirement: Source-data table naming rule and discovery
**Reason**: `list_source_tables` relocates to `daas-mcp`.
**Migration**: Call `list_source_tables` on `daas-mcp`. The `scraw_<slug>` convention is unchanged.

### Requirement: Rule CRUD tools
**Reason**: `create_rule`/`list_rules`/`get_rule`/`update_rule`/`delete_rule` relocate to `daas-mcp`.
**Migration**: Call the same five tools on `daas-mcp`. Signatures unchanged.

### Requirement: run_rule is incremental and idempotent
**Reason**: `run_rule` relocates to `daas-mcp`.
**Migration**: Call `run_rule` on `daas-mcp`. The `--run-rule` CLI branch moves to `mcp/daas-mcp/server.py`.

### Requirement: SQL-injection guard on dynamic identifiers
**Reason**: The guard is now enforced inside `daas-mcp`.
**Migration**: See `daas-llm-extraction` — "SQL-injection guard on dynamic identifiers". Behavior unchanged.

### Requirement: Cron-driven execution via CLI branch
**Reason**: The `--run-rule` CLI branch moves to `daas-mcp`'s arg parser.
**Migration**: Use `uv run --directory mcp/daas-mcp python server.py --run-rule <name>`.

### Requirement: daas integration is traceability only
**Reason**: The "daas-traceability exemption" framing is moot once the tools live inside `daas-mcp`.
**Migration**: See `daas-llm-extraction` — "LLM extraction writes only process_results". The LLM path still does not write `observations`.

## ADDED Requirements

### Requirement: Capability relocated to daas-llm-extraction
The `process-mcp-server` capability SHALL be considered relocated: all LLM-extraction tools (`list_models`, `list_source_tables`, `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`) and the `--run-rule` CLI branch SHALL be served by `daas-mcp` under the `daas-llm-extraction` capability. No `process-mcp` server SHALL be registered in `.mcp.json`. The `process_rules` and `process_results` tables SHALL remain in `mcp/daas.db` (owned by `daas-mcp`) with no schema change. The `PROCESS_MODELS` env-var name SHALL be retained for backward compatibility.

#### Scenario: LLM-extraction tools are hosted by daas-mcp
- **WHEN** a client calls `extract_text` after the relocation
- **THEN** the tool is served by `daas-mcp`, not a separate `process-mcp` process

#### Scenario: no process-mcp in .mcp.json
- **WHEN** `.mcp.json` is read after the relocation
- **THEN** no `process-mcp` entry is present, and `daas-mcp` exposes the LLM-extraction tools
