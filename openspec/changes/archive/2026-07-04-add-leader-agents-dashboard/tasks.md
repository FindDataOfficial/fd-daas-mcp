## 1. leader-mcp: update + delete specialist agent (DB layer)

- [x] 1.1 Add `WorkflowDatabase.update_specialist_agent(name, role=None, goal=None, backstory=None, model=_UNSET, enabled=None, upstream=None)` to `mcp/leader-mcp/workflow_database.py`: look up by `name` (return `{"error": "specialist agent '<name>' not found"}` if missing); validate `upstream` against `_upstream_names()` when a new value is provided; validate `model` (when a non-null string) and `upstream` identifier via `_validate_ident`; distinguish `model=_UNSET` (unchanged) from `model=None` (clear → `NULL`); apply only the provided fields; advance `updated_at`; return `row.to_dict(upstream_missing=...)`.
- [x] 1.2 Add `WorkflowDatabase.delete_specialist_agent(name)` to `workflow_database.py`: look up by `name` (return not-found error if missing); query `workflow_steps` for rows with `agent == name` and, if any exist, return `{"error": "specialist agent '<name>' is referenced by workflow(s): <names>"}` (distinct workflow names, sorted) without deleting; otherwise delete the row and return `{"deleted": name}`.
- [x] 1.3 Export the `_UNSET` sentinel (module-level) so the tool layer can share the same "omitted vs. null" semantics.

## 2. leader-mcp: update + delete specialist agent (MCP tool layer)

- [x] 2.1 Add `update_specialist_agent(...)` tool function in `mcp/leader-mcp/workflow_tools.py` with the same signature/defaults as the DB method, a docstring (mirroring `create_specialist_agent`'s style), and a `try/except ValueError → _err(exc)` body calling `get_workflow_db().update_specialist_agent(...)`.
- [x] 2.2 Add `delete_specialist_agent(name: str) -> dict` tool function in `workflow_tools.py` with docstring + `try/except ValueError` body.
- [x] 2.3 Register both tools in `mcp/leader-mcp/server.py` (`app.add_tool(update_specialist_agent)`, `app.add_tool(delete_specialist_agent)`) alongside the existing `create_specialist_agent` / `list_specialist_agents` lines, and add them to any tool-list exports/`__all__` used by `selfcheck_workflow.py`.

## 3. leader-mcp: self-check + docs

- [x] 3.1 Extend `mcp/leader-mcp/selfcheck_workflow.py` (temp DB, stub gateway) to cover: update editable fields; `model=None` clears; `model` omitted leaves unchanged; update re-validates a changed upstream; update unknown agent errors; toggle `enabled=False`; delete an unreferenced agent succeeds; delete is refused when a `workflow_steps.agent` row references the agent (insert a workflow + step first); delete unknown agent errors. Run `uv run --directory mcp/leader-mcp python selfcheck_workflow.py` via the leader-mcp venv python and confirm all checks pass.
- [x] 3.2 Update `CLAUDE.md` leader-mcp `crewai-data-workflow` bullet to list `update_specialist_agent` and `delete_specialist_agent` in the tool inventory, and note the delete-refuses-when-referenced-by-a-step behavior.

## 4. dashboard: API routes

- [x] 4.1 Create `dashboard/src/app/api/agents/route.ts` — `POST` handler accepting `{action: "create", name, upstream, role, goal, backstory?, model?, enabled?}`; `getMCPTools()` → `create_specialist_agent` (only forwarding optional keys when present); `unwrap` the result (reuse the `unwrap` helper shape from `api/workflows/[name]/runs/route.ts`); `invalidateDb('daas')` on success; return `400` on soft error, `502` if leader-mcp won't start.
- [x] 4.2 Create `dashboard/src/app/api/agents/[name]/route.ts` — `POST` handler for `{action: "update", ...}` (forward only present fields; `model: null` is a present field) and `{action: "toggle"}` (read current `enabled` from `mcp/daas.db` via sql.js, then call `update_specialist_agent` with the flipped `enabled`); `DELETE` handler calling `delete_specialist_agent`. Both `invalidateDb('daas')` on success and surface soft errors as `400`, leader-mcp-down as `502`.
- [x] 4.3 Verify both routes handle `decodeURIComponent(name)` for path param and return JSON errors consistent with the workflows runs route.

## 5. dashboard: shared form + server data

- [x] 5.1 Create `dashboard/src/app/agents/server-data.ts` exporting `getAgentOptions()` → calls `getMCPTools()` and returns `{upstreams: string[], models: {name, model, provider?, vision?}[], tiers, error?}` by invoking `list_data_mcps()` + `list_agent_models()`; returns `{error}` on failure so the form can fall back to free-text.
- [x] 5.2 Create `dashboard/src/app/agents/agent-form.tsx` ('use client') — fields for `name`, `upstream` (select or free-text fallback), `role`, `goal`, `backstory` (textarea), `model` (select including tier aliases + configured names + "default (shared LLM)" option that submits `null`, with free-text fallback), `enabled` (checkbox); `mode: 'create' | 'edit'` (name disabled in edit); submits to `/api/agents` (create) or `/api/agents/[name]` (update) and redirects to `/agents/[name]` on success; shows server errors inline. Mirror the structure of `dashboard/src/app/process/rules/rule-form.tsx`.

## 6. dashboard: pages

- [x] 6.1 Create `dashboard/src/app/agents/page.tsx` (server component) — `SELECT` from `specialist_agents` ordered by `name`; for each row render name, upstream (+ `upstream_missing` marker when the upstream is absent from `leader_upstreams`), model (or "default (shared LLM)" when null), an `EnabledToggle` (reuse the process `enabled-toggle.tsx` shape, parameterized for agents — see 6.4), and a link to `/agents/[name]`; "New agent" link to `/agents/new`; empty-state message. Read via `getDb('daas')` + `queryAll`; wrap in try/catch so a missing table renders the empty state.
- [x] 6.2 Create `dashboard/src/app/agents/new/page.tsx` (server component) — `await getAgentOptions()`, render `<AgentForm mode="create" initial={...empty} options={...} />` with the `mcpError` banner when `options.error` is set.
- [x] 6.3 Create `dashboard/src/app/agents/[name]/page.tsx` (server component) — `SELECT` the agent by `name` (`decodeURIComponent`); render all fields, the "default (shared LLM)" model rendering when null, the `upstream_missing` marker, created_at/updated_at, a link to `/agents/[name]/edit`, and a delete button (client component that `DELETE`s `/api/agents/[name]` and redirects to `/agents` on success, surfacing the refused-when-referenced error inline). Render "agent not found" when missing. Read via sql.js.
- [x] 6.4 Create `dashboard/src/app/agents/[name]/edit/page.tsx` (server component) — load the agent via sql.js (404 → not-found state), `await getAgentOptions()`, render `<AgentForm mode="edit" initial={...agent} options={...} />` with name disabled.
- [x] 6.5 Add an `EnabledToggle` for agents (either generalize `process/enabled-toggle.tsx` to accept `kind: 'rules' | 'indicators' | 'agents'` and an API base, or add a sibling `agents/enabled-toggle.tsx` that POSTs `{action: "toggle"}` to `/api/agents/[name]`). Wire it into the list page (6.1).

## 7. dashboard: nav + wiring

- [x] 7.1 Add `{ href: '/agents', label: 'Agents' }` to `LINKS` in `dashboard/src/components/nav.tsx` (place it next to Workflows/Process).
- [x] 7.2 Smoke-test the full flow: run the dashboard (`npm run dev` in `dashboard/`), visit `/agents`, create an agent via the form (pick a real upstream + model), confirm it appears in the list, edit it (change `model`, clear `model` to default, toggle enabled), delete it. Verify delete is refused when the agent is referenced by a workflow step (create a workflow step pointing at it first) and succeeds otherwise. Confirm pages still render when leader-mcp is stopped.
