## REMOVED Requirements

### Requirement: Indicator rule persistence in the shared schema
**Reason**: The `process-mcp` server is deleted; `indicator_rules` ownership moves to `daas-mcp`.
**Migration**: See `daas-indicators` — "Indicator rule persistence in the shared schema". Table stays in `mcp/daas.db` with no schema change.

### Requirement: Math operation catalog
**Reason**: `list_indicator_ops` relocates to `daas-mcp`.
**Migration**: Call `list_indicator_ops` on `daas-mcp`. Catalog unchanged.

### Requirement: Indicator rule CRUD tools with validation
**Reason**: `create_indicator`/`list_indicators`/`get_indicator`/`update_indicator`/`delete_indicator` relocate to `daas-mcp`.
**Migration**: Call the same five tools on `daas-mcp`. Signatures unchanged.

### Requirement: run_indicator computes and upserts into observations
**Reason**: `run_indicator` relocates to `daas-mcp`.
**Migration**: Call `run_indicator` on `daas-mcp`. The `--run-indicator` CLI branch moves to `mcp/daas-mcp/server.py`; cron task commands update from `mcp/process-mcp` to `mcp/daas-mcp` (see `migrate_process_cron.py`).

### Requirement: Ad-hoc calculate tool
**Reason**: `calculate` relocates to `daas-mcp`.
**Migration**: Call `calculate` on `daas-mcp`. Signature unchanged.

### Requirement: SQL-injection guard on dynamic identifiers
**Reason**: The guard is now enforced inside `daas-mcp`.
**Migration**: See `daas-indicators` — "SQL-injection guard on dynamic identifiers". Behavior unchanged.

### Requirement: Cron-driven execution via CLI branch
**Reason**: The `--run-indicator` CLI branch moves to `daas-mcp`'s arg parser.
**Migration**: Use `uv run --directory mcp/daas-mcp python server.py --run-indicator <name>`.

### Requirement: observations sink reuses the daas indicator store
**Reason**: The `observations` sink is now owned by `daas-mcp` natively.
**Migration**: See `daas-indicators` — "observations sink reuses the daas indicator store". Behavior unchanged.

## ADDED Requirements

### Requirement: Capability relocated to daas-indicators
The `process-mcp-indicators` capability SHALL be considered relocated: all indicator tools (`list_indicator_ops`, `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`, `calculate`) and the `--run-indicator` CLI branch SHALL be served by `daas-mcp` under the `daas-indicators` capability. No `process-mcp` server SHALL be registered in `.mcp.json`. The `indicator_rules` table SHALL remain in `mcp/daas.db` (owned by `daas-mcp`) with no schema change.

#### Scenario: indicator tools are hosted by daas-mcp
- **WHEN** a client calls `run_indicator` after the relocation
- **THEN** the tool is served by `daas-mcp`, not a separate `process-mcp` process

#### Scenario: no process-mcp in .mcp.json
- **WHEN** `.mcp.json` is read after the relocation
- **THEN** no `process-mcp` entry is present, and `daas-mcp` exposes the indicator tools
