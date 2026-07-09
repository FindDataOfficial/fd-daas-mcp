## Why

leader-mcp persists specialist CrewAI agents in the `specialist_agents` table (`mcp/daas.db`), but the only way to manage them today is by running `seed_specialist_agents.py` or calling `create_specialist_agent` / `list_specialist_agents` over MCP by hand. There is no UI to view, create, edit, enable/disable, or delete agents, and — more fundamentally — the MCP surface itself has no update or delete tool, so even an automated caller cannot edit or remove an existing agent. The workflows dashboard already proves the read-from-`daas.db` + write-via-leader-mcp pattern; this change extends it to agents and closes the CRUD gap in leader-mcp.

## What Changes

- Add `update_specialist_agent` and `delete_specialist_agent` MCP tools to `leader-mcp` (mirroring `process-mcp`'s `update_rule` / `delete_rule` shape), backed by new `WorkflowDatabase.update_specialist_agent` + `delete_specialist_agent` methods. `update_specialist_agent` accepts `name` (immutable) plus any of `role`, `goal`, `backstory`, `model`, `enabled`, `upstream` (each optional; `null` model clears the override → shared `LLM_*` fallback) and re-validates `upstream` against `leader_upstreams`; `delete_specialist_agent` removes the row. Deleting an agent that is referenced by an existing `workflow_steps.agent` soft-ref is rejected with a clear error (no cascade, mirroring the soft-ref contract).
- Add a dashboard "Agents" section under `/agents` with full CRUD: a list page (`/agents`), a create form (`/agents/new`), a detail page (`/agents/[name]`), and an edit form (`/agents/[name]/edit`). The list and detail pages read directly from `mcp/daas.db` via the existing sql.js path (no leader-mcp spawn to render); create/update/delete go through new Next.js API routes that call leader-mcp tools via `getMCPTools()` and then `invalidateDb('daas')`.
- Add an "Agents" entry to the dashboard nav (`dashboard/src/components/nav.tsx`).
- Form dropdowns are populated from leader-mcp: `upstream` from `list_data_mcps()`, `model` from `list_agent_models()` (which already returns the tier mapping), so the user picks from real upstreams and configured models rather than typing free text.

## Capabilities

### New Capabilities
- `specialist-agents-dashboard-ui`: Dashboard pages, API routes, and nav entry for managing leader-mcp specialist agents (list / create / detail / edit / delete / enable-disable), reading from `mcp/daas.db` via sql.js and writing via leader-mcp MCP tools.

### Modified Capabilities
- `crewai-data-workflow`: The "Specialist data agent registry" requirement currently specifies only `create_specialist_agent` + `list_specialist_agents`. Extend it to require `update_specialist_agent` (editable role/goal/backstory/model/enabled/upstream, immutable name, re-validates upstream, `null` model clears the override) and `delete_specialist_agent` (refuses to delete an agent still referenced by a `workflow_steps.agent` soft-ref).

## Impact

- **leader-mcp**: `workflow_tools.py` (two new tool functions + registration in `server.py`), `workflow_database.py` (two new methods; `delete` checks `workflow_steps.agent` before removing). No schema change — `specialist_agents` columns already cover every editable field. `_validate_ident` and the `_upstream_names()` soft-ref check are reused.
- **dashboard**: new `dashboard/src/app/agents/` page tree (list, new, `[name]`, `[name]/edit`) + new `dashboard/src/app/api/agents/` routes (POST `/api/agents` create, POST/DELETE `/api/agents/[name]` update/delete) + a shared `agent-form.tsx` client component + an `enabled-toggle` reused in shape from the process pages. One line added to `nav.tsx` `LINKS`. Reads use `getDb('daas')` + `queryAll`; writes use `getMCPTools()` → leader-mcp tool → `invalidateDb('daas')`, exactly the workflows runs pattern.
- **CLAUDE.md**: document the two new tools under the leader-mcp `crewai-data-workflow` bullet and the new dashboard route under the dashboard section.
- **No breaking changes**: `create`/`list` semantics are untouched; the seed script and existing workflows continue to work. New tools are additive.
- **Self-check**: a new offline self-check in `leader-mcp` covers update (incl. `null` model clear + upstream re-validation) and delete (incl. refusal when a workflow step references the agent); the dashboard needs no new self-check (it reuses the established read/write paths).
