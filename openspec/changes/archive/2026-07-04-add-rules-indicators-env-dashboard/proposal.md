## Why

`process-mcp` persists two first-class, replayable artifacts in `mcp/daas.db`: **LLM extraction rules** (`process_rules` → `process_results`) and **math indicators** (`indicator_rules` → `observations`). Today they can only be created, inspected, and run through MCP tool calls (chat) or raw SQL — every other MCP domain (Cron, Datasources, Databases, Collections, Workflows) already has a dashboard surface, but process rules and indicators are the gap. A user cannot browse their rules, see what a rule extracted, view an indicator's latest series, or toggle/run a rule without leaving the chat.

Separately, the existing `/settings` page manages env vars in a `settings` table but only syncs the two `bootstrap` keys (`DAAS_DATABASE_URL`, `DASHBOARD_PORT`) to the root `.env`. The runtime keys (`LLM_*`, proxy, `CKAN_URL`) and per-MCP overrides live only in the database — MCPs read `.env` at startup, so they never see dashboard changes. The page cannot actually "define the `.env` file." This change makes it a real `.env` editor.

## What Changes

### Process rules + indicators dashboard (new pages)

- Add a `/process/rules` list page (Next.js server component) reading `process_rules` from `mcp/daas.db` via the existing sql.js path (`getDb('daas')` + `queryAll`), showing each rule's `name`, `source_table`, `text_column`, `model`, `enabled` (toggle), `last_rowid` cursor, and result count (from `process_results`), mirroring the `/workflows` list-page pattern.
- Add a `/process/rules/[name]` detail page rendering the rule's full config (schema, prompt, model, max_chars, datasource), a recent-`process_results` table (`source_rowid`, `model`, `run_at`, `extracted_json` pretty-printed + truncated with a "Show full" toggle), and actions: **Run rule** (`run_rule`), **Enable/Disable** (`update_rule`), **Edit** (`update_rule`), **Delete** (`delete_rule`).
- Add a `/process/indicators` list page reading `indicator_rules`, showing `name`, `datasource`, `op`, `value_column`, `indicator_name`, `enabled` (toggle), and latest-observation value/date.
- Add a `/process/indicators/[name]` detail page rendering the indicator config (`op`, `params`, source table/columns, `indicator_name`) plus a recent-`observations` table for that indicator (`(source, function_name, indicator)` match) and an **ECharts line chart** of the series (reusing `dashboard/src/components/echarts-wrapper.tsx`), and actions: **Run indicator** (`run_indicator`), **Enable/Disable**, **Edit**, **Delete**.
- Add create forms: a "New rule" form on `/process/rules` and a "New indicator" form on `/process/indicators` (model picker from `list_models`, source-table picker from `list_source_tables`, op picker from `list_indicator_ops`, JSON schema/params as a raw-JSON textarea for v1), proxying to `create_rule` / `create_indicator`.
- Add a "Process" entry to the dashboard nav (`dashboard/src/components/nav.tsx`).
- Read paths use sql.js direct reads (consistent with `/workflows`, `/cron`); mutations (create/update/delete/run/toggle) go through `process-mcp`'s MCP tools via the existing `getMCPTools()` client — the dashboard does NOT reimplement extraction or indicator math.

### `.env` editor (updated settings page)

- The `/settings` page SHALL write every managed key through to the actual `.env` file(s): global bootstrap + runtime keys to the root `.env`, and per-MCP proxy overrides to `mcp/<mcp>/.env` (created on first write, appended as `KEY=value` override lines). The `settings` table remains the source of truth for the UI; `.env` files are regenerated from it on save.
- Add a **raw `.env` editor** section to `/settings`: a textarea showing the live root `.env` contents, with Save (write the whole file) and a "reset from disk" action. Includes a comment legend so users know which lines are dashboard-managed.
- Expand `syncToEnv` in `dashboard/src/app/api/settings/route.ts` to cover all categories (not just `bootstrap`), and add per-MCP `.env` sync. Mark every write with a `restartRequired` hint (MCPs read `.env` only at startup).
- Add a `GET /api/settings/env` (return root `.env` text) and `PUT /api/settings/env` (replace root `.env` text) route for the raw editor.

## Capabilities

### New Capabilities

- `process-dashboard-ui`: Next.js dashboard surface for `process-mcp` LLM extraction rules and math indicators — list, detail, create/edit, delete, enable/disable toggle, run, view extraction results and observation series (with an ECharts chart), reading via sql.js and mutating via `process-mcp` MCP tools.
- `dashboard-env-editor`: The `/settings` page writes every managed env key through to the real `.env` file(s) (root `.env` for globals, `mcp/<mcp>/.env` for per-MCP overrides) and exposes a raw `.env` text editor, so the dashboard is the source of truth for `.env` and MCPs pick up changes on restart.

### Modified Capabilities

<!-- None. The `process-mcp-server` and `process-mcp-indicators` specs cover MCP tool behavior; this change adds a dashboard UI that consumes existing tables and tools without altering their contracts. No existing spec covers the settings page, so `dashboard-env-editor` is a new capability rather than a modification. -->

## Impact

- **Code**: new files under `dashboard/src/app/process/` (`rules/page.tsx`, `rules/[name]/page.tsx`, `indicators/page.tsx`, `indicators/[name]/page.tsx`) + client components for forms, run/toggle/delete buttons, and JSON output blocks; new API routes `dashboard/src/app/api/process/rules/[name]/route.ts` (run/update/delete) + `dashboard/src/app/api/process/rules/route.ts` (create) + mirrored `indicators` routes; updates to `dashboard/src/app/settings/page.tsx` (raw editor section + per-MCP `.env` write-through) and `dashboard/src/app/api/settings/route.ts` (expand `syncToEnv` to all categories + per-MCP sync) + new `dashboard/src/app/api/settings/env/route.ts`; one-line addition to `dashboard/src/components/nav.tsx`. No changes to `mcp/process-mcp/` or `mcp/models/` — all required tables and tools already exist.
- **APIs**: new internal Next.js routes under `/api/process/*` (proxy to `process-mcp` tools) and `/api/settings/env` (raw `.env` read/replace); expanded `PUT /api/settings` to sync all categories + per-MCP `.env`. No public API change.
- **Dependencies**: none new — uses existing `sql.js` (reads), existing `@ai-sdk/mcp` client (`getMCPTools()`), existing `tailwind` styling, existing `echarts-wrapper.tsx` for the indicator chart.
- **Systems**: reads/writes `mcp/daas.db` (`process_rules`, `process_results`, `indicator_rules`, `observations`); writes root `.env` and `mcp/<mcp>/.env` files; spawns `process-mcp` as a stdio subprocess only for mutations (reuses the cached `getMCPClient()` singleton from `mcp-client.ts`).
- **Out of scope**: scheduling rules/indicators via cron from this page (already supported via `process-mcp` `--run-rule` / `--run-indicator` CLI branches + `cron-mcp`; the `/cron` page covers it); a visual JSON-Schema builder (v1 uses a raw-JSON textarea); editing `PROCESS_MODELS` / `LEADER_MODELS` JSON blobs (use chat for now); auth/permissions (the dashboard has none today).
