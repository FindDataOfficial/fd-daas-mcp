## Context

The `leader-mcp` CrewAI data-workflow layer (spec: `crewai-data-workflow`) persists workflows in four tables in `mcp/daas.db`: `workflows`, `workflow_steps`, `workflow_runs`, `workflow_step_results` (schema in `mcp/models/models.py`, `Workflow` / `WorkflowStep` / `WorkflowRun` / `WorkflowStepResult`). MCP tools (`list_workflows`, `get_workflow`, `run_workflow`, `run_workflow_step`, `get_workflow_run`) manage them, and a `--run-workflow <name>` CLI branch drives them from `cron-mcp`. There is no dashboard surface — every other MCP domain (Cron, Datasources, Databases, Collections) has one.

The dashboard (`dashboard/`, Next.js App Router) already has the building blocks this change needs:
- **sql.js reads** for list/detail pages (`dashboard/src/lib/db.ts` → `getDb('daas')` + `queryAll`); used by `/cron`, `/datasources`, `/databases`.
- **Interactive client components** that `fetch` to `/api/...` routes then `router.refresh()` (e.g. `dashboard/src/app/cron/schedule-list.tsx`, `dashboard/src/app/cron/tasks/[id]/task-form.tsx`).
- **An MCP client singleton** (`dashboard/src/lib/mcp-client.ts` → `getMCPTools()`) that spawns `leader-mcp` as a stdio subprocess; used by `/api/chat` and `/api/collections/[name]/chat`.
- **A nav** (`dashboard/src/components/nav.tsx`) with one entry per top-level page.

Constraint: the workflow **runner** (CrewAI execution, deterministic direct fallback, `depends_on` injection, `on_fail` policy, model-tier resolution, 1 MB `output_json` cap with `_truncated` flag in `meta_json`, run/step-result persistence) lives inside `leader-mcp`. The dashboard must not reimplement it.

## Goals / Non-Goals

**Goals:**
- A `/workflows` list page showing every workflow with step count and last-run status/time.
- A `/workflows/[name]` detail page showing the ordered step definitions and recent runs.
- A `/workflows/[name]/runs/[runId]` run-detail page showing per-step results (status, output, error, meta).
- Triggering a full run (`run_workflow`) or one step (`run_workflow_step`) from the UI, reusing `leader-mcp`'s runner.
- A "Workflows" nav entry.
- Browsing (list/detail/run-detail) works from direct `daas.db` reads without requiring `leader-mcp` to start.

**Non-Goals:**
- Creating / editing / deleting workflow definitions from the UI (use chat + `build_workflow_from_goal` / `create_workflow` / `add_workflow_step`). A step-builder UX is a follow-up.
- Scheduling workflows from this page (already solved via `--run-workflow` + `cron-mcp`; the `/cron` page covers it).
- Real-time / streaming run progress. Runs are synchronous in `crewai-data-workflow`; the trigger awaits and refreshes.
- Auth / permissions (the dashboard has none today).

## Decisions

### Decision 1: Read path = sql.js direct reads (not MCP tools)

List, detail, and run-detail pages read `workflows` / `workflow_steps` / `workflow_runs` / `workflow_step_results` directly via `getDb('daas')` + `queryAll`.

**Why:** Matches the established `/cron` and `/datasources` pattern. The tables are ours and simple. Spawning `leader-mcp` (a stdio subprocess) on every page render would add cold-start latency and a failure mode that doesn't exist for `/cron`. The MCP read tools (`list_workflows`, `get_workflow`) also don't surface run history — we'd need extra round-trips for runs/results that a single SQL join gets in one shot.

**Alternatives considered:**
- `getMCPTools()` for reads — rejected: subprocess spawn cost per render, and the tools don't expose run listings.
- Adding new read-only MCP tools (`list_runs`, `get_run`) — rejected: unnecessary; the dashboard already reads sibling tables directly.

### Decision 2: Run trigger = MCP tools via `getMCPTools()` (not direct SQL, not CLI branch)

`POST /api/workflows/[name]/runs` calls `leader-mcp`'s `run_workflow` (full) or `run_workflow_step` (single step) through the existing `getMCPTools()` singleton.

**Why:** Only the `leader-mcp` runner executes steps — CrewAI + direct fallback, `depends_on` injection, `on_fail` policy, model-tier resolution, the 1 MB cap, and run/step-result persistence. Reimplementing any of that in the dashboard would duplicate and drift. `getMCPTools()` is already wired (used by chat) and reuses one cached subprocess.

**Alternatives considered:**
- `server.py --run-workflow <name>` CLI branch — rejected: it only does full `run_workflow` (no single-step), and spawning a fresh venv'd Python process per run is heavier than the cached MCP client.
- Direct SQL writes — rejected: skips the runner entirely (no step execution, no validation).

### Decision 3: Route = `/workflows/[name]` (name, not id)

Detail routes key off the workflow's unique `name` (`uq_workflow_name`).

**Why:** Names are unique and human-meaningful; matches `get_workflow(name)` MCP semantics and the existing `/collections/[name]` convention. Avoids an id→name lookup. `build_workflow_from_goal` derives kebab-case names, so they're URL-safe by construction.

**Trade-off:** a hand-created name with odd characters would need encoding; acceptable given the kebab-case convention. The API route still resolves by name (the MCP tools take `name`).

### Decision 4: `output_json` rendering = pretty JSON, truncated, expandable

On the run-detail page, each step's `output_json` is pretty-printed into a `<pre>` block, truncated to a display budget (≈5 KB) with an "Show full" toggle. The `meta_json` (fallback reason, `_truncated` flag) renders as a small badge next to the step status.

**Why:** `output_json` is the raw upstream payload, capped at 1 MB by the runner. Dumping 1 MB into the DOM makes the page unresponsive. Truncation + toggle keeps it snappy; the badge surfaces the `{"fallback":"direct",...}` and `_truncated` signals without forcing a scroll.

### Decision 5: Synchronous run trigger with refresh

The run-trigger `fetch` is awaited; on success the client calls `router.refresh()` so the new run row appears in the runs table. A spinner covers the in-flight state; errors render inline.

**Why:** `crewai-data-workflow` runs are synchronous and bounded (fast tier, 1 MB cap per step). This matches the cron toggle/delete interaction model (`fetch` → `router.refresh()`). Streaming/async runs are out of scope for the spec today.

**Trade-off:** a pathological run could approach the Next.js route timeout. Mitigation: the per-step cap and the `fast` default bound the common case; the route returns whatever `run_workflow` returns. If long runs become real, the fix is an async-run spec in `crewai-data-workflow`, not a dashboard hack.

### Decision 6: Scope = browse + run (no create/edit in v1)

The UI is read + trigger. Definition authoring stays in chat.

**Why:** The user asked to "see the workflows." A step-builder UX (agent picker, depends_on graph, on_fail per step, model override) is substantial and already covered by `build_workflow_from_goal` + chat. Shipping browse + run first delivers the visible gap without bloating the change.

## Risks / Trade-offs

- **Stale reads after a run** — `run_workflow` writes via `leader-mcp` (a separate process), and the dashboard's sql.js DB is cached in-process (`dbCache` in `db.ts`). → Mitigation: the run-trigger API route calls `invalidateDb('daas')` after the run returns, so `router.refresh()` re-reads fresh data. (This mirrors the existing `invalidateDb` pattern used after the Python writers.)
- **`leader-mcp` unavailable when triggering a run** — browsing still works (sql.js reads), but the run button fails. → Mitigation: the API route returns a clear `{error}`; the client surfaces it inline. The `crewai-data-workflow` direct fallback means a run can still complete without `crewai`/LLM config, but it does need `leader-mcp` to start.
- **Large `output_json` in DOM** — 1 MB JSON could still be expanded by a user. → Mitigation: truncation default + explicit toggle; the full payload is only attached to the DOM when the user opts in.
- **Name collisions / non-kebab names** — rare given the builder convention; URL-encoding handles it. → Mitigation: routes use `decodeURIComponent` on the param.
- **Run route concurrency** — two simultaneous "Run all" clicks on the same workflow create two runs. → Acceptable: `run_workflow` always starts a fresh run; `run_workflow_step` reuses an `in_progress` run per the spec. No dashboard-level locking needed for v1.

## Migration Plan

- Additive only — new dashboard files + one nav line. No DB migration (tables exist), no `leader-mcp` change, no `.mcp.json` change.
- **Deploy:** `dashboard/` rebuilds on next `next dev`/`next build`; nothing else restarts.
- **Rollback:** delete `dashboard/src/app/workflows/`, `dashboard/src/app/api/workflows/`, revert the nav line. No data to migrate back.
- **Verify after deploy:** visit `/workflows` (list renders, empty-state shown if no workflows), create a workflow via chat (`create_workflow` + `add_workflow_step`), reload `/workflows`, open detail, click "Run all steps", see the new run row, open the run, see step outputs. Run `openspec validate add-workflows-dashboard --strict` before `/opsx:apply`.

## Open Questions

- Should the runs table on the detail page auto-refresh while an `in_progress` run is open (from `run_workflow_step`)? **Tentative: no for v1** — the user can click refresh. Polling adds complexity and the spec's runs are short. Revisit if single-step interactive runs become common.
- Should the run-trigger API live under `/api/workflows/[name]/runs` (collection-style, POST creates a run) — yes, chosen above. If we later want per-step triggers as a separate route, `/api/workflows/[name]/steps/[sortOrder]/runs` is the natural extension.
