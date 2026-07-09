## Why

The `leader-mcp` CrewAI data-workflow layer (`crewai-data-workflow` spec) lets users define and run multi-step specialist-agent workflows, persisted in `workflows` / `workflow_steps` / `workflow_runs` / `workflow_step_results` tables in `mcp/daas.db`. Today these can only be inspected through MCP tool calls (chat) or raw SQL — there is no dashboard surface for them. Every other first-class MCP domain in this repo already has a dashboard page (Cron at `/cron`, Datasources at `/datasources`, Databases at `/databases`, Collections at `/collections`). Workflows are the gap: a user cannot browse their workflows, read the step definitions, or review run history and per-step outputs without leaving the chat. This change adds a `/workflows` page (and detail routes) so workflows become a first-class, browsable dashboard object — on par with Cron Tasks.

## What Changes

- Add a `/workflows` list page (Next.js server component) that reads `workflows` + `workflow_runs` from `mcp/daas.db` via the existing sql.js path (`getDb('daas')` + `queryAll`), showing per-workflow stats (step count, last run status, last run time) in a table, mirroring the `/cron` list-page pattern.
- Add a `/workflows/[name]` detail page rendering the workflow's ordered `workflow_steps` (sort_order, agent, request, depends_on, on_fail, model, enabled) plus a recent-`workflow_runs` table; each run links to a run-detail page.
- Add a `/workflows/[name]/runs/[runId]` run-detail page rendering the ordered `workflow_step_results` for one run (step sort_order, status, output, error, meta, ran_at), with output rendered as pretty-printed JSON (truncated for display, expandable).
- Add a "Run all steps" control on the workflow detail page and a "Run this step" control per step, both invoking `leader-mcp`'s `run_workflow` / `run_workflow_step` MCP tools through a new `/api/workflows/[name]/runs` POST route that uses the existing `getMCPTools()` client (reusing the runner + validation; the dashboard does NOT reimplement step execution).
- Add a "Workflows" entry to the dashboard nav (`dashboard/src/components/nav.tsx`).
- Read paths use sql.js direct reads (consistent with `/cron`, `/datasources`); the run trigger uses `getMCPTools()` because only the `leader-mcp` runner executes steps (CrewAI + direct fallback, `depends_on` injection, `on_fail` policy, model-tier resolution).

## Capabilities

### New Capabilities
- `workflow-dashboard-ui`: Next.js dashboard surface for browsing `leader-mcp` data workflows — list workflows, view step definitions, view run history and per-step outputs, and trigger runs. Read-only browsing via sql.js direct reads; run execution via `leader-mcp` MCP tools.

### Modified Capabilities
<!-- None. The `crewai-data-workflow` spec covers MCP tool behavior; this change adds a dashboard UI that consumes existing tables and tools without altering their contracts. -->

## Impact

- **Code**: new files under `dashboard/src/app/workflows/` (`page.tsx`, `[name]/page.tsx`, `[name]/runs/[runId]/page.tsx`) + client components for run triggers; new API route `dashboard/src/app/api/workflows/[name]/runs/route.ts`; one-line addition to `dashboard/src/components/nav.tsx`. No changes to `mcp/leader-mcp/` or `mcp/models/` — all required tables and tools already exist.
- **APIs**: one new internal Next.js route (`POST /api/workflows/[name]/runs`) that proxies to `leader-mcp`'s `run_workflow` / `run_workflow_step`; no public API change.
- **Dependencies**: none new — uses existing `sql.js` (reads), existing `@ai-sdk/mcp` client (`getMCPTools()`), existing `tailwind` styling.
- **Systems**: reads `mcp/daas.db` (workflows, workflow_steps, workflow_runs, workflow_step_results); spawns `leader-mcp` as a stdio subprocess only when a run is triggered (reuses the cached `getMCPClient()` singleton from `mcp-client.ts`).
- **Out of scope**: creating / editing / deleting workflow definitions from the UI (use chat + `build_workflow_from_goal` / `create_workflow` / `add_workflow_step` for now); scheduling workflows via cron (already supported via `--run-workflow` CLI branch + `cron-mcp`).
