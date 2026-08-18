---
name: fd-daas-dashboard
description: Find, open, and inspect existing daas standalone HTML dashboards - list every dashboard, search by keyword (name / intro / source table), show a dashboard's introduction + data lineage + entity/time coverage, open it in the browser, or query the rows backing it. Use this skill whenever the user wants to USE or FIND an already-built dashboard - phrases like "我们有哪些看板", "打开之前那个看板", "show me the BYD dashboard", "leaders 看板里是什么数据", "有没有关于比特币的看板", "what data backs this dashboard", or any "dashboard / 看板" + "open / find / list / show / 打开 / 找 / 列一下 / 看看". Do NOT use this skill to BUILD a new dashboard (use fd-daas-dashboard-creator) or to edit/delete one - this skill is read-only over the `dashboards` registry; it lists, describes, opens, and queries backing data, nothing more. Uses sqlite3 on daas.db - NO MCP tools.
---

# fd-daas-dashboard

Use an existing daas standalone HTML dashboard. Dashboards are built by `fd-daas-dashboard-creator` and registered in the `dashboards` table in `daas.db` (one row per dashboard: name, introduction, source tables, entity/time coverage, refresh cadence, chart config, file url). This skill reads that registry via **`sqlite3`** so you can answer "what dashboards exist", "find me the one about X", "open it", or "what data is in it" - without the user having to remember a filename or a `file://` URL.

This skill is **read-only**. It never builds, edits, or deletes a dashboard - hand those intents to `fd-daas-dashboard-creator`.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` points at the DB (currently `sqlite:///daas.db`). From the repo root, `sqlite3 daas.db "..."` works.

## Mental model

1. **"What dashboards do we have?" / "Find one about X"** -> `sqlite3` SELECT on `dashboards` (all, or `LIKE` keyword over name + intro + source_tables).
2. **"What's in this one?"** -> `sqlite3` SELECT by slug -> introduction, source tables, entity coverage, time range, refresh cadence, chart config, file url.
3. **"Open it"** -> `open <file_url>` on macOS, after asking permission.
4. **"What does the data look like?"** -> `sqlite3` SELECT against the dashboard's recorded `source_tables`.

## Step 1 - List or search dashboards

```bash
# list all
sqlite3 daas.db "SELECT slug, name, intro, file_url FROM dashboards ORDER BY created_at"
# search by keyword (matches name + intro + refresh_cadence + source_tables)
sqlite3 daas.db "SELECT slug, name, intro FROM dashboards WHERE LOWER(name||' '||COALESCE(intro,'')||' '||COALESCE(refresh_cadence,'')||' '||COALESCE(source_tables,'')) LIKE '%byd%' ORDER BY created_at"
```

Present matches as a numbered list: `1. <name> - <intro>  (slug: <slug>)`. If empty, say "No dashboards registered yet. Build one with fd-daas-dashboard-creator." and stop. If no match, say "No dashboard matches <keyword>." and offer the list.

## Step 2 - Show a dashboard's full metadata

```bash
sqlite3 daas.db "SELECT slug, name, intro, source_tables, entity_coverage, time_range, refresh_cadence, chart_config, file_url FROM dashboards WHERE slug='<slug>'"
```

Surface in plain language: name + introduction, entity coverage, time range, source tables, refresh cadence, chart config, file_url. If the row is missing, the slug is wrong - re-search.

## Step 3 - Open a dashboard in the browser

1. Get the `file_url` from Step 2.
2. **Ask permission** before launching - "Open <name> in the browser?" Don't auto-launch.
3. Accept -> on macOS run `open <file_url>` and confirm. Decline -> print the URL.

If the `file://` path doesn't exist on disk (HTML deleted but row remains), tell the user the file is missing and suggest rebuilding (`fd-daas-dashboard-creator`) or removing the stale row (`.claude/skills/fd-daas-dashboard-creator/scripts/register_dashboard.py delete --slug <slug>`).

## Step 4 - Query the data backing a dashboard

```bash
sqlite3 daas.db "SELECT * FROM <source_table> LIMIT 20"
```

Take the first (or user-named) `source_table` from Step 2. Show columns + a few rows, naming the source table. Offer to query a different source table or raise the limit.

## Step 5 - Redirect build / edit / delete intent

- **Build** -> `fd-daas-dashboard-creator`.
- **Edit** -> re-run `fd-daas-dashboard-creator` (upserts by slug), or `.claude/skills/fd-daas-dashboard-creator/scripts/register_dashboard.py update --slug <slug> ...` for metadata-only edits.
- **Delete** -> `uv run python .claude/skills/fd-daas-dashboard-creator/scripts/register_dashboard.py delete --slug <slug>` (removes the row + regenerates `index.html`/`daas.md`) and `rm dashboards/<slug>.html`.

## Gotchas

- **Read-only.** Lists, describes, opens, queries - never writes to `dashboards`. Build/edit/delete go to `fd-daas-dashboard-creator` / `register_dashboard.py`.
- **Slug, not name, for lookups.** The `dashboards` table is keyed by the kebab `slug`. If the user gives a name, resolve to a slug via the search query first.
- **Missing HTML file.** A row can outlive its HTML file. Step 3 handles this - don't assume the file exists just because the row does.
- **Dashboard HTML home.** Post-cutover, dashboards live at repo-root `dashboards/<slug>.html`; older rows may still carry a stale `mcp/dashboard-mcp/dashboards/...` `file_path` - treat the `file_url` as authoritative but flag stale paths to the user.
