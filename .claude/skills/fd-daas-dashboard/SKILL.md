---
name: fd-daas-dashboard
description: Find, open, and inspect existing daas standalone HTML dashboards — list every dashboard, search by keyword (name / intro / source table), show a dashboard's introduction + data lineage + entity/time coverage, open it in the browser, or query the rows backing it. Use this skill whenever the user wants to USE or FIND an already-built dashboard — phrases like "我们有哪些看板", "打开之前那个看板", "show me the BYD dashboard", "leaders 看板里是什么数据", "有没有关于比特币的看板", "what data backs this dashboard", or any "dashboard / 看板" + "open / find / list / show / 打开 / 找 / 列一下 / 看看". Do NOT use this skill to BUILD a new dashboard (use fd-daas-dashboard-creator) or to edit/delete one — this skill is read-only over the `dashboards` registry; it lists, describes, opens, and queries backing data, nothing more.
---

# fd-daas-dashboard

Use an existing daas standalone HTML dashboard. Dashboards are built by `fd-daas-dashboard-creator` and registered in the `dashboards` table in `mcp/daas.db` (one row per dashboard: name, introduction, source tables, entity/time coverage, refresh cadence, chart config, file url). This skill reads that registry via `dashboard-mcp` tools so you can answer "what dashboards exist", "find me the one about X", "open it", or "what data is in it" — without the user having to remember a filename or a `file://` URL.

This skill is **read-only** over the registry. It never builds, edits, or deletes a dashboard — hand those intents to `fd-daas-dashboard-creator` (build/edit) or the `dashboard-mcp` delete tool (delete).

## Mental model

Four things a user typically wants, each mapped to one or two tool calls:

1. **"What dashboards do we have?" / "Find one about X"** → `list_dashboards` (all) or `search_dashboards` (keyword over name + intro + source tables). Surface name + intro so they can pick.
2. **"What's in this one?"** → `get_dashboard` by slug → introduction, source tables, entity coverage, time range, refresh cadence, chart config, file url.
3. **"Open it"** → `open <file_url>` on macOS, after asking permission.
4. **"What does the data look like?"** → `query_table` against the dashboard's recorded `source_tables`, so the user can inspect/verify the rows behind the charts.

If the user asks to build, edit, or delete a dashboard, redirect (Step 5) — don't mutate the registry from here.

## Step 1 — List or search dashboards

Goal: show the user what exists, narrowed by their interest.

- **"我们有哪些看板" / "list dashboards"** → call `mcp__dashboard-mcp__list_dashboards`. It returns every dashboard's `name`, `slug`, `intro`, and `file_url`. Present them as a numbered list: `1. <name> — <intro>  (slug: <slug>)`. If empty, say "No dashboards registered yet. Build one with fd-daas-dashboard-creator." and stop.
- **"有没有关于 X 的看板" / "find a dashboard about X"** → call `mcp__dashboard-mcp__search_dashboards` with a keyword from the user's request. It matches case-insensitively against each dashboard's name + intro + refresh_cadence + source_tables, so a search for "比亚迪" or "scraw_byd_daily" or "RSI" all work. Present the matches the same way. If no match, say "No dashboard matches <keyword>." and offer `list_dashboards` so they can browse.

Don't open or query anything yet — let the user pick which one.

## Step 2 — Show a dashboard's full metadata

When the user names one (or picks from the list), call `mcp__dashboard-mcp__get_dashboard` with the `slug` and surface, in plain language:

- **Name + introduction** — what the dashboard is and why it exists.
- **Entity coverage** — which entities/codes it spans (e.g. "12 symbols: aapl, amd, …"), or "unscoped (aggregate)".
- **Time range** — the date span it covers, or "latest snapshot".
- **Source tables** — the `scraw_*` / `observations` tables backing the charts.
- **Refresh cadence** — static snapshot vs the cron that refreshes it (name the cron).
- **Chart config** — a one-line summary of the charts (e.g. "2 charts: a candlestick+line over scraw_<sym>_daily, and an RSI/vol line over observations").
- **file_url** — the `file://` URL (don't auto-open; Step 3 does that on request).

If `get_dashboard` returns `{"error": "dashboard '<slug>' not found"}`, the slug is wrong — re-run `search_dashboards` to find the right one, or `list_dashboards` to browse.

## Step 3 — Open a dashboard in the browser

When the user says "open it" / "打开" / "show me":

1. Get the `file_url` from Step 2 (or call `get_dashboard` if you only have the slug).
2. **Ask permission** before launching — "Open <name> in the browser?" Don't auto-launch.
3. Accept → on macOS (the project host) run `open <file_url>` and confirm it launched. Decline → print the `file_url` and don't launch.

If the `file://` path doesn't exist on disk (the HTML was deleted but the registry row remains), tell the user the file is missing and suggest either rebuilding it (`fd-daas-dashboard-creator`) or removing the stale row (`mcp__dashboard-mcp__delete_dashboard`).

## Step 4 — Query the data backing a dashboard

When the user asks "what's the data in this dashboard" / "这个看板的数据长什么样" / "show me the rows behind it":

1. From Step 2, take the first (or user-named) `source_table`.
2. Call `mcp__dashboard-mcp__query_table` with `database="daas"`, `table="<source_table>"`, `limit=20`. It returns `{columns, rows, total}`.
3. Show the user the columns + a few rows, naming the source table and the total row count. Offer to query a different source table from the dashboard's list, or to raise the `limit`.

**Stale-DB fallback**: if `query_table` returns `no such table` for a `scraw_*` table the dashboard says it uses, `dashboard-mcp` is reading a stale DB (a running process that predates the repo-root URL fix). Fall back to a `python3 -c "import sqlite3,json; ..."` one-liner against `<repo-root>/mcp/daas.db` to fetch the rows, and tell the user to restart `dashboard-mcp`.

## Step 5 — Redirect build / edit / delete intent

This skill is read-only. If the user wants to:

- **Build a new dashboard** ("做一个看板" / "build a dashboard for these indicators") → tell them to invoke `fd-daas-dashboard-creator`. Don't attempt to build here.
- **Edit an existing dashboard** (change charts, data, filters) → tell them to re-run `fd-daas-dashboard-creator` for that dashboard (it upserts by slug), or to call `mcp__dashboard-mcp__update_dashboard` directly for metadata-only edits.
- **Delete a dashboard** → tell them to call `mcp__dashboard-mcp__delete_dashboard("<slug>")` (removes the registry row + regenerates `index.html`/`daas.md`) and `rm dashboard/my-charts-dashboard/<slug>.html`. Don't delete from here.

## Gotchas

- **Read-only.** This skill lists, describes, opens, and queries — it never writes to the `dashboards` table. Build/edit/delete go to `fd-daas-dashboard-creator` or the `dashboard-mcp` tools.
- **Standalone HTML only.** This skill covers the dashboards in `dashboard/my-charts-dashboard/*.html` (the `dashboards` registry). It does NOT navigate the Next.js `dashboard/` app pages (`/entities`, `/collections`, `/indicators`, …). If the user wants the Next.js app, tell them that's a separate app — this skill is for the standalone HTML dashboards.
- **`dashboard-mcp` stale-DB gotcha.** If `query_table` (Step 4) returns `no such table` for a source table the dashboard records, fall back to a direct `sqlite3` one-liner against `<repo-root>/mcp/daas.db`. The registry tools (`list_dashboards` / `get_dashboard` / `search_dashboards`) resolve the URL correctly, so Steps 1–2 are unaffected — only the data-query in Step 4 can hit this.
- **Slug, not name, for tool calls.** `get_dashboard` / `delete_dashboard` take the kebab `slug`, not the human-readable `name`. If the user gives a name, resolve it to a slug via `search_dashboards` or `list_dashboards` first.
- **Missing HTML file.** A registry row can outlive its HTML file (someone deleted the `.html` but not the row). Step 3 handles this — don't assume the file exists just because the row does.
