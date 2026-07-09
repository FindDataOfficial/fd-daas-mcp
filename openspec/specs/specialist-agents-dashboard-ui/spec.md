# specialist-agents-dashboard-ui Specification

## Purpose
Dashboard pages, API routes, and nav entry for managing leader-mcp specialist agents (list / create / detail / edit / delete / enable-disable), reading from mcp/daas.db via sql.js and writing via leader-mcp MCP tools.

## Requirements

### Requirement: Agents navigation entry

The dashboard navigation (`dashboard/src/components/nav.tsx`) SHALL include an "Agents" entry linking to `/agents`, placed alongside the other top-level pages (Chat, Collections, Databases, Cron Tasks, Workflows, Process, Datasources, Settings).

#### Scenario: Agents link is visible in the nav

- **WHEN** any dashboard page renders
- **THEN** the left-hand nav contains an "Agents" link pointing to `/agents`
- **AND** visiting `/agents` marks the nav entry active

### Requirement: Agent list page

The dashboard SHALL provide a `/agents` route (Next.js server component) that lists every row in the `specialist_agents` table, ordered by `name` ascending. For each agent the page SHALL show the agent `name`, `upstream`, `model` (or "default (shared LLM)" when `null`), `enabled` toggle, and an `upstream_missing` marker when the bound `upstream` is no longer present in `leader_upstreams`. The page SHALL render a "New agent" link to `/agents/new` and an empty-state message when no agents exist. The page SHALL read directly from `mcp/daas.db` via the existing sql.js path (`getDb('daas')` + `queryAll`) and SHALL NOT spawn `leader-mcp` to render.

#### Scenario: List agents with model and upstream state

- **WHEN** the user visits `/agents` and `specialist_agents` contains two rows: `edgar-agent` (upstream `edgartools`, model `fast`, enabled) and `yfinance-agent` (upstream `yfinance`, model `null`, enabled)
- **THEN** both agents are listed ordered by `name`
- **AND** `edgar-agent` shows model `fast` and `yfinance-agent` shows "default (shared LLM)"
- **AND** each row shows an enable/disable toggle

#### Scenario: Upstream-missing marker

- **WHEN** an agent's `upstream` value is not present in `leader_upstreams` (e.g. the upstream row was removed)
- **THEN** the list row shows a visible `upstream_missing` marker next to the upstream name

#### Scenario: Empty state

- **WHEN** the user visits `/agents` and the `specialist_agents` table is empty
- **THEN** the page renders an empty-state message (e.g. "No agents yet") instead of a table

#### Scenario: List page renders without leader-mcp

- **WHEN** `leader-mcp` cannot start (e.g. its venv is missing) and the user visits `/agents`
- **THEN** the page still renders the agent list from `mcp/daas.db` reads without error

### Requirement: Agent create page

The dashboard SHALL provide a `/agents/new` route (Next.js server component) that renders a form with fields for `name`, `upstream`, `role`, `goal`, `backstory`, `model`, and `enabled`. The `upstream` field SHALL be a `<select>` populated from `list_data_mcps()` and the `model` field SHALL be a `<select>` populated from `list_agent_models()` (including the three tier aliases `high` / `balance` / `fast`, every configured `LEADER_MODELS` entry name, and an explicit "default (shared LLM)" option that submits `model=null`). When `leader-mcp` is unavailable, the form SHALL fall back to free-text inputs for `upstream` and `model` and SHALL show an amber banner explaining the fallback. Submitting the form SHALL `POST` to `/api/agents` with `{action: "create", ...}`.

#### Scenario: Dropdowns populated from leader-mcp

- **WHEN** the user visits `/agents/new` and `leader-mcp` is available with upstreams `yfinance`, `edgartools` and models `fast`, `high`, `glm`
- **THEN** the `upstream` select lists `yfinance` and `edgartools`
- **AND** the `model` select lists `high`, `balance`, `fast`, `glm`, and "default (shared LLM)"

#### Scenario: Free-text fallback when leader-mcp is down

- **WHEN** the user visits `/agents/new` and `leader-mcp` cannot start
- **THEN** the `upstream` and `model` fields render as free-text inputs
- **AND** an amber banner explains that leader-mcp is unavailable

#### Scenario: Submit creates an agent

- **WHEN** the user fills in `name="edgar-agent"`, `upstream="edgartools"`, `role=...`, `goal=...`, `model="fast"` and submits
- **THEN** the browser POSTs to `/api/agents` with `{action: "create", name: "edgar-agent", upstream: "edgartools", ...}`
- **AND** on success the user is redirected to `/agents/edgar-agent`

### Requirement: Agent detail page

The dashboard SHALL provide a `/agents/[name]` route that resolves an agent by its unique `name` (`decodeURIComponent`-decoded path param) and renders the agent's `name`, `upstream` (with an `upstream_missing` marker when the bound upstream no longer exists), `role`, `goal`, `backstory`, `model` (or "default (shared LLM)" when `null`), `enabled`, `created_at`, and `updated_at`. The page SHALL provide a link to `/agents/[name]/edit` and a delete control. When the agent `name` does not exist, the page SHALL render a clear "agent not found" state. The page SHALL read directly from `mcp/daas.db` and SHALL NOT spawn `leader-mcp` to render.

#### Scenario: Detail page shows agent fields

- **WHEN** the user visits `/agents/edgar-agent` for an existing agent
- **THEN** the page renders the agent's name, upstream, role, goal, backstory, model, enabled state, created_at, and updated_at
- **AND** links to `/agents/edgar-agent/edit` are visible

#### Scenario: Null model is shown as the shared fallback

- **WHEN** an agent has `model = null`
- **THEN** the detail page renders the model as "default (shared LLM)"

#### Scenario: Unknown agent name

- **WHEN** the user visits `/agents/nope` and no row exists in `specialist_agents` with `name = "nope"`
- **THEN** the page renders an "agent not found" state

### Requirement: Agent edit page

The dashboard SHALL provide a `/agents/[name]/edit` route that renders the same form as `/agents/new` pre-filled with the agent's current values, except that the `name` field SHALL be disabled (immutable). Submitting the form SHALL `POST` to `/api/agents/[name]` with `{action: "update", ...}`. The `model` field SHALL include the "default (shared LLM)" option so the user can clear the override (submitting `model=null`).

#### Scenario: Edit form is pre-filled and name is locked

- **WHEN** the user visits `/agents/edgar-agent/edit` for an existing agent with `model="fast"`
- **THEN** the form fields are pre-filled with the agent's current values
- **AND** the `name` field is disabled with a note that it cannot be renamed
- **AND** the `model` select is set to `fast`

#### Scenario: Clearing the model override

- **WHEN** the user selects "default (shared LLM)" in the model dropdown and submits
- **THEN** the browser POSTs to `/api/agents/edgar-agent` with `{action: "update", model: null}`
- **AND** on success the agent's `model` column is `NULL` and the detail page shows "default (shared LLM)"

### Requirement: Agent enable/disable toggle

The dashboard list page SHALL render an enable/disable toggle for each agent row. Toggling SHALL `POST` to `/api/agents/[name]` with `{action: "toggle"}`. A disabled agent SHALL remain listed but is skipped by workflow runners (its `enabled` flag is `0`).

#### Scenario: Disable an enabled agent

- **WHEN** the user clicks the toggle on an enabled agent `edgar-agent`
- **THEN** the browser POSTs to `/api/agents/edgar-agent` with `{action: "toggle"}`
- **AND** on success the agent's `enabled` column is `0` and the toggle re-renders as "off"

#### Scenario: Enable a disabled agent

- **WHEN** the user clicks the toggle on a disabled agent
- **THEN** the agent's `enabled` column becomes `1` and the toggle re-renders as "on"

### Requirement: Agent create API route

The dashboard SHALL provide a `POST /api/agents` route that accepts `{action: "create", name, upstream, role, goal, backstory?, model?, enabled?}`, calls leader-mcp's `create_specialist_agent` via `getMCPTools()`, and returns the created agent on success or `{error: ...}` with an appropriate status on failure. On success the route SHALL call `invalidateDb('daas')` so subsequent server-component renders re-read the file. If `leader-mcp` cannot start, the route SHALL return `502` with `{error: "leader-mcp unavailable: ..."}`.

#### Scenario: Successful create

- **WHEN** the route receives `{action: "create", name: "edgar-agent", upstream: "edgartools", role: "...", goal: "...", model: "fast"}`
- **THEN** it calls `create_specialist_agent` with those arguments and returns `200` with the created agent row
- **AND** the dashboard's cached `daas` sql.js handle is invalidated

#### Scenario: Duplicate name surfaces as a 400

- **WHEN** the route receives a create for a name that already exists
- **THEN** leader-mcp returns `{"error": "specialist agent '...' already exists"}`
- **AND** the route returns `400` with that error

#### Scenario: leader-mcp unavailable

- **WHEN** `getMCPTools()` throws because leader-mcp cannot start
- **THEN** the route returns `502` with `{error: "leader-mcp unavailable: ..."}`

### Requirement: Agent update API route

The dashboard SHALL provide a `POST /api/agents/[name]` route that accepts either `{action: "update", role?, goal?, backstory?, model?, enabled?, upstream?}` or `{action: "toggle"}`. For `action: "update"`, the route SHALL forward only the fields present in the body to leader-mcp's `update_specialist_agent` (so omitted fields are unchanged), where `model: null` explicitly clears the override. For `action: "toggle"`, the route SHALL call `update_specialist_agent` with `enabled` flipped from the agent's current value. On success the route SHALL call `invalidateDb('daas')`.

#### Scenario: Update fields

- **WHEN** the route receives `{action: "update", role: "New role", model: "high"}` for `edgar-agent`
- **THEN** it calls `update_specialist_agent(name="edgar-agent", role="New role", model="high")`
- **AND** returns `200` with the updated row
- **AND** invalidates the cached `daas` handle

#### Scenario: Clear model override

- **WHEN** the route receives `{action: "update", model: null}` for an agent whose model is `fast`
- **THEN** it calls `update_specialist_agent(name="...", model=None)` and the agent's `model` column becomes `NULL`

#### Scenario: Toggle flips enabled

- **WHEN** the route receives `{action: "toggle"}` for an agent whose `enabled` is `1`
- **THEN** it calls `update_specialist_agent(name="...", enabled=False)` and the agent's `enabled` becomes `0`

#### Scenario: Update unknown agent

- **WHEN** the route receives an update for a name that does not exist
- **THEN** leader-mcp returns `{"error": "specialist agent '...' not found"}`
- **AND** the route returns `400` with that error

### Requirement: Agent delete API route

The dashboard SHALL provide a `DELETE /api/agents/[name]` route that calls leader-mcp's `delete_specialist_agent`. On success the route SHALL call `invalidateDb('daas')` and return `200`. If leader-mcp refuses the delete because a `workflow_steps.agent` row still references the agent, the route SHALL return `400` with that error verbatim so the dashboard can surface it.

#### Scenario: Successful delete

- **WHEN** the route receives `DELETE /api/agents/edgar-agent` and no workflow step references `edgar-agent`
- **THEN** it calls `delete_specialist_agent(name="edgar-agent")` and returns `200`
- **AND** invalidates the cached `daas` handle

#### Scenario: Delete refused when referenced by a workflow step

- **WHEN** the route receives `DELETE /api/agents/edgar-agent` and a `workflow_steps` row has `agent = "edgar-agent"`
- **THEN** leader-mcp returns an error naming the referencing workflow(s)
- **AND** the route returns `400` with that error
- **AND** the agent row is not removed

#### Scenario: Delete unknown agent

- **WHEN** the route receives `DELETE /api/agents/nope` and no agent with that name exists
- **THEN** the route returns `400` with `{"error": "specialist agent 'nope' not found"}`
