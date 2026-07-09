## Context

leader-mcp already persists specialist CrewAI agents in `specialist_agents` (`mcp/daas.db`) and exposes `create_specialist_agent` + `list_specialist_agents` over MCP. The dashboard already has a working pattern for a sibling domain — workflows — where list/detail pages read directly from `mcp/daas.db` via sql.js (`getDb('daas')` + `queryAll`) and writes go through a Next.js API route that calls leader-mcp tools via `getMCPTools()` and then `invalidateDb('daas')` (see `dashboard/src/app/api/workflows/[name]/runs/route.ts`). The process-rules pages further establish a CRUD UI pattern: server-component list, `new` + `[name]/edit` forms driven by a shared `*-form.tsx` client component, an `enabled-toggle` client component, and form dropdowns populated from leader-mcp with a free-text fallback when the MCP is unavailable.

Two gaps make "manage agents from the dashboard" impossible today:

1. **No update/delete tooling in leader-mcp.** `workflow_database.py` has `create` / `upsert` / `get` / `list` for specialist agents but no `update` or `delete`, and only `create` + `list` are registered as MCP tools. So an agent's `role`/`goal`/`model`/`enabled` cannot be edited after creation, and an agent cannot be removed.
2. **No dashboard surface.** There is no `/agents` route, no nav entry, and no API routes.

This change closes both: it adds the two missing MCP tools (and their DB methods) and adds the dashboard UI that uses them.

## Goals / Non-Goals

**Goals:**
- Full CRUD for specialist agents from the dashboard: list, create, view detail, edit, enable/disable, delete.
- Add `update_specialist_agent` + `delete_specialist_agent` to leader-mcp with the same validation chokepoints as `create` (identifier guard, upstream soft-ref check).
- Keep the read path spawn-free (sql.js direct read) so pages render even if leader-mcp's venv is broken — matching the workflows dashboard contract.
- Populate form dropdowns from leader-mcp (`list_data_mcps`, `list_agent_models`) with a graceful free-text fallback.

**Non-Goals:**
- Renaming an agent (name is immutable on update; rename = delete + create, mirroring process rules).
- Editing the `LEADER_MODELS` registry or model tiers from the dashboard — only the agent's `model` *pointer* is editable.
- Managing `leader_upstreams` rows from this page (that belongs to the gateway domain; `list_data_mcps` is read-only here).
- A batch seed/re-seed button (the seed script remains the CLI path; `seed_specialist_agents.py` is unchanged).
- Live "test run an agent" from the detail page (out of scope; agents run inside workflows).

## Decisions

### D1: Writes go through leader-mcp tools, not direct sql.js writes
The dashboard's mutating API routes call `update_specialist_agent` / `delete_specialist_agent` / `create_specialist_agent` via `getMCPTools()`, then `invalidateDb('daas')`. leader-mcp stays the single validation chokepoint (identifier regex, upstream soft-ref, workflow-step reference check).

- *Alternatives considered:*
  - **Direct sql.js writes from the API route.** Rejected: bypasses the upstream soft-ref check and the `workflow_steps.agent` reference check, and diverges from the established workflows-runs write path. The dashboard's sql.js handle is treated as read-only for cross-process-owned tables.
  - **A Python sidecar (`agent_writer.py`, like `collection_writer.py`).** Rejected: leader-mcp already owns this domain and already runs as the write tool server for workflows; a second writer would duplicate validation. A sidecar is only warranted when no MCP owns the table (collections), which is not the case here.

### D2: Add update/delete to leader-mcp, mirroring process-mcp's `update_rule` / `delete_rule`
`update_specialist_agent(name, role=None, goal=None, backstory=None, model=None, enabled=None, upstream=None)` — every field optional; omitted fields are unchanged. `delete_specialist_agent(name)` removes the row. Both re-use `_validate_ident` and `_upstream_names()`.

- *Alternatives considered:*
  - **A separate `enable_specialist_agent` / `disable_specialist_agent` pair.** Rejected: folding `enabled` into `update` is simpler and the UI's enable/disable toggle just calls `update` with `enabled`. Mirrors process rules where the toggle posts to the update endpoint.
  - **Allowing rename inside update.** Rejected: `name` is the soft-ref key for `workflow_steps.agent`; renaming would silently break workflows. Name stays immutable (same as process rule names).

### D3: `model=None` semantics on update — clear vs. omit
On `update_specialist_agent`, **omitting** `model` leaves the stored value unchanged; passing `model=None` (JSON `null`) explicitly clears the override so the agent falls back to the shared `LLM_*` path. This distinction matters because "use the shared fallback" is a legitimate, intentional choice a user makes from the UI (e.g. a "clear model" button). The MCP tool signature uses a sentinel: `model` is `Optional[str]` with default `_UNSET`, so the tool can distinguish "not provided" from "provided as null".

### D4: Delete refuses when a workflow step still references the agent
`workflow_steps.agent` is a soft reference (no FK). Deleting an agent that a step points at would silently break `run_workflow` / `run_workflow_step` (the runner does `db.get_specialist_agent(step["agent"])` and errors with `{"error": "specialist agent '<name>' not found"}` at run time). `delete_specialist_agent` SHALL query `workflow_steps` for rows with `agent = name` first and reject the delete with a clear error naming the referencing workflows, so the user deletes or re-points the step first. No cascade.

### D5: Reads stay direct sql.js (no leader-mcp spawn on render)
The list and detail pages `SELECT` from `specialist_agents` directly via sql.js, joining/aggregating in SQL where useful (e.g. a `upstream_missing` derivation is already stored by `list_specialist_agents`, but for the page we compute it inline from `leader_upstreams`). This matches the workflows list-page contract: the page renders even if leader-mcp cannot start.

- *Alternative considered:* call `list_specialist_agents()` over MCP at render time. Rejected: adds a process spawn per page load and breaks the "renders without leader-mcp" guarantee.

### D6: Form dropdowns populated server-side from leader-mcp, with free-text fallback
The `new` and `edit` pages are server components that call `list_data_mcps()` and `list_agent_models()` once (via `getMCPTools()`) to populate `<select>` options for `upstream` and `model`. If leader-mcp is unavailable, the form degrades to free-text inputs (mirroring `rule-form.tsx`'s `mcpError` banner). The `model` dropdown includes the three tier aliases (`high` / `balance` / `fast`) plus every `LEADER_MODELS` entry name, plus an explicit "default (shared LLM)" option that submits `model=null`.

### D7: API route shape mirrors workflows runs
- `POST /api/agents` — body `{action: "create", name, upstream, role, goal, backstory?, model?, enabled?}` → `create_specialist_agent`.
- `POST /api/agents/[name]` — body `{action: "update", ...fields}` OR `{action: "toggle"}` → `update_specialist_agent`. (One route for both edit + toggle, like process rules.)
- `DELETE /api/agents/[name]` → `delete_specialist_agent`.
Every successful mutation calls `invalidateDb('daas')` before returning, so the next server-component render re-reads the file.

## Risks / Trade-offs

- **[Soft-ref integrity on delete]** A workflow step can point at a deleted agent's name if deletion bypasses the check. → Mitigation: `delete_specialist_agent` queries `workflow_steps.agent` and refuses; the dashboard's DELETE route surfaces the error verbatim.
- **[Stale sql.js cache after a write through leader-mcp]** leader-mcp writes in a separate process; the dashboard's cached sql.js `Database` would show stale data. → Mitigation: every mutating API route calls `invalidateDb('daas')` (same pattern as `api/workflows/[name]/runs/route.ts`).
- **[leader-mcp unavailable when rendering the form]** Dropdowns would be empty. → Mitigation: free-text fallback + an amber `mcpError` banner (mirrors `rule-form.tsx`). List/detail pages don't depend on leader-mcp at all (sql.js reads).
- **[Distinguishing `model=null` from "leave unchanged" over JSON]** A naive `Optional[str]` default can't tell "key absent" from "key present and null". → Mitigation: server-side `_UNSET` sentinel in the tool signature; the API route only forwards `model` when the client explicitly sends the key (the form's "default" option sends `null`).
- **[Concurrency]** Two dashboard tabs editing the same agent can race (last write wins, no version column). → Mitigation: acceptable — same granularity as process rules and workflows; `updated_at` is bumped on every write for visibility. Not adding optimistic locking now.

## Migration Plan

- **Deploy**: additive only. New MCP tools are registered alongside the existing ones; new dashboard routes + nav entry are net-new files; no schema change (`specialist_agents` already has every editable column). No data backfill.
- **Rollback**: remove the two tool registrations from `server.py`, delete `dashboard/src/app/agents/` and `dashboard/src/app/api/agents/`, revert the `nav.tsx` line. Existing agents, the seed script, and all workflows continue to work unchanged.

## Open Questions

None material. (Detail: whether to also expose `get_specialist_agent` as an MCP tool — not needed; the detail page reads via sql.js, and `list_specialist_agents` already returns full rows.)
