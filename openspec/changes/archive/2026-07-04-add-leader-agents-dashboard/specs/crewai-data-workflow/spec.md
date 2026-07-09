## MODIFIED Requirements

### Requirement: Specialist data agent registry

The system SHALL persist a registry of specialist CrewAI agents in a `specialist_agents` table in `mcp/daas.db` (created via `Base.metadata.create_all`, no Alembic). Each row SHALL bind exactly one agent to one data-fetch MCP upstream: columns `name` (unique), `upstream` (the `leader_upstreams.name` this agent fetches from — soft reference, no FK), `role`, `goal`, `backstory`, `model` (a tier alias `high`/`balance`/`fast`, OR a named entry from `LEADER_MODELS`, OR `null` = shared `LLM_*` fallback), `enabled`, `created_at`, `updated_at`. MCP tools `create_specialist_agent(name, upstream, role, goal, backstory=None, model=None, enabled=True)`, `list_specialist_agents()`, `update_specialist_agent(name, role=None, goal=None, backstory=None, model=_UNSET, enabled=None, upstream=None)`, and `delete_specialist_agent(name)` SHALL provide full CRUD access. `create_specialist_agent` SHALL reject an `upstream` that is not present in `leader_upstreams` (enabled or disabled) with a clear error and SHALL reject duplicate `name`. `update_specialist_agent` SHALL treat every field as optional (omitted fields unchanged), SHALL reject an unknown `name` with a clear error, SHALL re-validate a changed `upstream` against `leader_upstreams`, and SHALL distinguish `model` omitted (unchanged) from `model=None` (clear the override → shared `LLM_*` fallback); `model` (when provided as a non-null string) SHALL be validated as a safe identifier. `delete_specialist_agent` SHALL reject with a clear error when any `workflow_steps.agent` row still references the agent's `name` (soft reference, no FK), naming the referencing workflow(s), and SHALL remove the row otherwise. A seed script `seed_specialist_agents.py` SHALL upsert one default specialist agent per enabled `leader_upstreams` row (idempotent on `name`), so that after seeding every enabled data-fetch MCP has a usable agent. The seeded default agent's `model` SHALL be the `fast` tier alias (not `null`), so seeded agents default to the fast model for data-fetch steps; re-running the seed script SHALL preserve any user-set per-agent `model` (including a different tier alias or concrete name).

#### Scenario: Create a specialist agent for an enabled upstream
- **WHEN** `create_specialist_agent(name="edgar-agent", upstream="edgartools", role="SEC EDGAR specialist", goal="Fetch EDGAR filings and company facts", backstory="...", model="fast")` is called and `edgartools` exists in `leader_upstreams`
- **THEN** a row exists in `specialist_agents` with `upstream="edgartools"`, `model="fast"`, `enabled=1`
- **AND** `list_specialist_agents()` returns an entry for `edgar-agent`

#### Scenario: Reject unknown upstream
- **WHEN** `create_specialist_agent(name="x", upstream="nope", ...)` is called and `nope` is not in `leader_upstreams`
- **THEN** the system returns `{"error": "upstream 'nope' not found in leader_upstreams"}` and writes no row

#### Scenario: Reject duplicate name
- **WHEN** `create_specialist_agent(name="edgar-agent", ...)` is called and `edgar-agent` already exists
- **THEN** the system returns `{"error": "specialist agent 'edgar-agent' already exists"}` and does not overwrite the existing row

#### Scenario: Seed one agent per enabled upstream with the fast tier default
- **WHEN** `seed_specialist_agents.py` is run and `leader_upstreams` contains enabled rows for `yfinance`, `edgartools`, `akshare`
- **THEN** `specialist_agents` contains one row per enabled upstream (names like `yfinance-agent`, `edgartools-agent`, `akshare-agent`)
- **AND** each seeded row has `model="fast"`
- **AND** re-running the script updates existing rows rather than inserting duplicates
- **AND** if a user has set an agent's `model` to a different value (e.g. `"high"` or a concrete name), re-running the seed preserves that value

#### Scenario: Update editable fields on an existing agent
- **WHEN** `update_specialist_agent(name="edgar-agent", role="New role", goal="New goal", model="high")` is called and `edgar-agent` exists
- **THEN** the row's `role`, `goal`, and `model` are updated to the provided values
- **AND** the row's `upstream`, `backstory`, and `enabled` are unchanged
- **AND** the row's `updated_at` is advanced
- **AND** the tool returns the updated agent row

#### Scenario: Clear the model override with model=None
- **WHEN** `update_specialist_agent(name="edgar-agent", model=None)` is called on an agent whose `model` is `"fast"`
- **THEN** the row's `model` column becomes `NULL`
- **AND** the agent resolves to the shared `LLM_*` fallback at run time

#### Scenario: Update with model omitted leaves the override unchanged
- **WHEN** `update_specialist_agent(name="edgar-agent", role="New role")` is called (no `model` argument) on an agent whose `model` is `"fast"`
- **THEN** the row's `model` remains `"fast"`

#### Scenario: Update re-validates a changed upstream
- **WHEN** `update_specialist_agent(name="edgar-agent", upstream="nope")` is called and `nope` is not in `leader_upstreams`
- **THEN** the system returns `{"error": "upstream 'nope' not found in leader_upstreams"}` and the row's `upstream` is unchanged

#### Scenario: Update unknown agent
- **WHEN** `update_specialist_agent(name="ghost-agent", role="...")` is called and `ghost-agent` does not exist
- **THEN** the system returns `{"error": "specialist agent 'ghost-agent' not found"}` and writes no row

#### Scenario: Toggle enabled via update
- **WHEN** `update_specialist_agent(name="edgar-agent", enabled=False)` is called on an enabled agent
- **THEN** the row's `enabled` becomes `0`
- **AND** the agent is skipped by workflow runners on subsequent runs

#### Scenario: Delete an agent not referenced by any workflow step
- **WHEN** `delete_specialist_agent(name="edgar-agent")` is called and no `workflow_steps` row has `agent = "edgar-agent"`
- **THEN** the row is removed from `specialist_agents`
- **AND** `list_specialist_agents()` no longer returns `edgar-agent`

#### Scenario: Delete refused when a workflow step references the agent
- **WHEN** `delete_specialist_agent(name="edgar-agent")` is called and a `workflow_steps` row has `agent = "edgar-agent"`
- **THEN** the system returns an error naming the referencing workflow(s) (e.g. `{"error": "specialist agent 'edgar-agent' is referenced by workflow(s): aapl-due-diligence"}`)
- **AND** the row is not removed from `specialist_agents`

#### Scenario: Delete unknown agent
- **WHEN** `delete_specialist_agent(name="ghost-agent")` is called and `ghost-agent` does not exist
- **THEN** the system returns `{"error": "specialist agent 'ghost-agent' not found"}` and writes no row
