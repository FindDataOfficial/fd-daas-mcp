---
name: extract-web-data
description: |
  Extract structured data from a website end-to-end and make it a permanent,
  scheduled, cataloged data source. Use this skill whenever the user wants to pull
  data from a web page on a recurring or reusable basis — not just a one-off
  fetch. It inspects the page with scrapling, generates a reusable scraper script,
  verifies it runs, registers the site as a managed DaaS datasource (auto-placing
  it in the category tree), and optionally schedules it to run on a cron via
  cron-mcp. Trigger on phrases like "extract data from this site", "scrape this
  page and keep it updated", "set up a scraper for X", "pull this table every day",
  "add this website as a datasource", "爬取并定时更新", "抓取网站数据", or whenever
  the user gives a URL and wants reusable + scheduled extraction (not a single
  manual fetch). For a one-shot, no-schedule scrape, `fd-daas-scraw-scrapling` may
  suffice; use THIS skill when run/verify, DaaS catalog registration, or scheduling
  is wanted.
---

# extract-web-data

Turn a URL into a reusable, verified, cataloged, optionally-scheduled data
source — by composing three existing MCP servers rather than reinventing any of
them.

| Concern | MCP server | Tools used |
|---------|-----------|------------|
| Fetch + run scrapers | `scrapling-uv-mcp` | `fetch`, `stealthy_fetch`, `find_scripts`, `run_script` |
| Persist scraping config | (script) | `mcp/scrapling-uv-mcp/scripts/db_helper.py` |
| Catalog the site as a datasource | `daas-mcp` | `search_datasources`, `create_datasource`, `update_datasource`, `get_category_tree`, `create_category`, `add_form`, `add_section`, `list_forms` |
| Schedule recurring runs | `cron-mcp` | `list_db_tasks`, `create_task`, `update_task`, `create_schedule`, `list_schedules`, `run_now`, `list_executions` |

## The one convention that ties everything together: the shared slug

A single `slug` links every artifact so nothing drifts:

```
slug = slugify(config_name)            # lowercase, [a-z0-9-], hyphens for spaces
```

| Artifact | Where the slug appears |
|----------|------------------------|
| Scraper script | `<SCRAPLING_SCRIPTS_DIR>/<slug>.py` (filename stem) |
| `scraw_configs` row | `name = <slug>` |
| DaaS datasource | `name = <slug>` |
| cron task | `name = scrape_<slug>` |
| cron schedule | `name = scrape_<slug>_<freq>` |

Because every MCP keys off `name`, the same slug makes create-or-update idempotent
across re-runs. Pick the config name early (ask the user, or derive from the page
title / URL) and slugify it.

`SCRAPLING_SCRIPTS_DIR` resolves to `mcp/scrapling-uv-mcp/scripts/scrapers/` by
default (settable via root `.env`). The `find_scripts`/`run_script` tools scan
and execute there, so **save generated scrapers into that directory** — not the
old `scripts/` location used by `fd-daas-scraw-scrapling`.

## Prerequisites

- `scrapling-uv-mcp`, `daas-mcp`, `cron-mcp` enabled in `.mcp.json` /
  `.claude/settings.local.json` (they already are in this repo).
- `SCRAPLING_SCRIPTS_DIR` (optional; defaults to the in-repo scrapers dir).
  `SCRAPLING_SCRIPT_TIMEOUT` (optional; default 120s) bounds `run_script`.
- `daas.db` at `mcp/daas.db` (shared by all three; scraw configs live in the
  `scraw_configs` table there).

## Workflow

### Step 1 — Inspect the target page

Call `scrapling-uv-mcp` `fetch` to read the page and identify the data structure
(tables, lists, cards) and the natural columns. If `fetch` returns a challenge
page / blocked / empty body (Cloudflare, anti-bot), fall back to `stealthy_fetch`
for the same URL.

If the user did not name columns, propose the columns you can see (with a short
description each) and let them confirm or adjust before generating anything.

### Step 2 — Generate and save the scraper

Write a self-contained Python scraper that imports `scrapling`, fetches the URL,
extracts the agreed columns, and prints JSON to stdout. Use the template in
`references/scraper-template.md` — it already handles the `--out <path>` option
and JSON-to-stdout contract.

Save it as `<SCRAPLING_SCRIPTS_DIR>/<slug>.py`. **Refuse to overwrite** an
existing `<slug>.py` unless the user confirms (the skill is updating, not
trampling). Add a module docstring whose first line states what it scrapes —
`find_scripts` surfaces that line as the summary.

### Step 3 — Persist the scraping config

Record `{name, url, columns}` in the `scraw_configs` table so the config is
queryable and survives restarts:

```bash
uv run --directory mcp/scrapling-uv-mcp python scripts/db_helper.py \
  save "<slug>" "<url>" '<columns_json>'
```

`columns_json` is a JSON array: `[{"name":"title","type":"string","description":"…"}, …]`.
`db_helper save` upserts on `name` (updates if the slug already exists).

### Step 4 — Verify the scraper runs

Call `scrapling-uv-mcp` `run_script` with `name=<slug>`. Expect `returncode=0`
and JSON on stdout. Show the user a sample of the extracted rows. If it fails,
read `stderr`, fix the script, and re-run before doing anything else — do **not**
register or schedule a scraper that doesn't verify.

### Step 5 — Register the website as a managed DaaS datasource

Make the site appear in the managed catalog and `search_datasources`.

1. Decide the category level automatically (no user prompt) — see
   `references/auto-level.md`: `get_category_tree` → find-or-create a root
   `Web Scraped` → find-or-create a child named after the URL's registered
   domain (e.g. `example.com`) → use that leaf's `category_id`.
2. Check for an existing datasource: `search_datasources(source_name=<slug>)`.
   - If it exists → `update_datasource(name=<slug>, url=…, config_json=…,
     category_id=<leaf>)`.
   - If not → `create_datasource(name=<slug>, label=<page title or host>,
     description=…, url=<url>, config_json='{"scraw_config":"<slug>","script":"<abs script path>"}',
     category_id=<leaf>, enabled=True)`.
3. Attach a form + section so the columns are queryable:
   `add_form(source_name=<slug>, form_type="page", label=<page title or url>)` →
   take the returned `form_id` → `add_section(form_id, section_name="columns",
   instruction=<column list as JSON or prose>)`.

After this, `search_datasources(source_name=<slug>, section="columns")` returns
the datasource with its column list, and `list_forms(<slug>)` shows the `page`
form. Re-running the skill for the same site updates in place — no duplicate
datasource, form, or category.

### Step 6 — (Optional) Schedule recurring extraction via cron-mcp

Only when the user opts in. cron-mcp separates **tasks** (a named shell command)
from **schedules** (a cron expression referencing a task by name), so do this in
order:

1. **Ensure the task exists.** `list_db_tasks` → look for `scrape_<slug>`.
   - Present → `update_task(name="scrape_<slug>", command=<cmd>, timeout=<>)`
     (refresh the command, e.g. if the script path changed).
   - Absent → `create_task(name="scrape_<slug>", command=<cmd>, description=…,
     timeout=<>)`. `create_task` rejects duplicate names, hence the check.
   - `command` = `uv run --directory <abs>/mcp/scrapling-uv-mcp python <abs>/<slug>.py`
     (append ` --out <path>` if a durable file is wanted each run). Use **absolute
     paths** — the cron process may run from anywhere.
2. **Create or reuse the schedule.** `list_schedules` → look for one whose `task`
   is `scrape_<slug>`. If found, reuse it (there is no `update_schedule`). If not,
   `create_schedule(name="scrape_<slug>_<freq>", cron=<expr>, task="scrape_<slug>",
   enabled=True)` → note the returned `schedule_id`.
3. **Confirm it works once.** `run_now(schedule_id)` fires immediately (the result
   is written to an Execution row, not returned inline). Then
   `list_executions(schedule_id, limit=1)` → read `output` (the captured stdout)
   and `status`. Report the `schedule_id` and the immediate-run result to the user.

### Step 7 — Report

Tell the user the shared slug and the artifacts created: script path,
`scraw_configs` row, DaaS datasource name + its category path (`Web Scraped` →
`<domain>`), the `page`/`columns` form, and (if scheduled) the `schedule_id`,
cron expression, and task name. Give them the one-line delete path for each
(`delete_schedule`, `delete_task`, `delete_datasource`, `delete_category`,
`db_helper.py delete`).

## Relationship to `fd-daas-scraw-scrapling`

`fd-daas-scraw-scrapling` is the **one-shot** path: fetch a URL, generate a
scraper, save it, persist the config — nothing more. This skill is the
**lifecycle** path: it adds run/verify, DaaS catalog registration with
auto-decided category level, and cron scheduling. Both reuse the same
`scraw_configs` table; this skill saves scrapers to `SCRAPLING_SCRIPTS_DIR`
(so they're discoverable by `find_scripts`/runnable by `run_script`) rather
than the old `scripts/` dir. Prefer this skill whenever the user wants the
site to be reusable, cataloged, or scheduled — not merely fetched once.

## Principles

- **Verify before registering/scheduling.** Never catalog or cron a scraper that
  hasn't returned `returncode=0`.
- **One slug, everywhere.** The slug ties script ↔ config ↔ datasource ↔ task ↔
  schedule; keep it identical across every call.
- **Idempotent by default.** search-then-create-or-update for datasources; check
  `list_db_tasks`/`list_schedules` before creating tasks/schedules. Re-running
  the skill for the same site must not duplicate anything.
- **Decide the level, don't ask.** Categorize automatically by domain under a
  `Web Scraped` root (see `references/auto-level.md`); surface the choice, don't
  block on it.
- **Absolute paths for cron.** The cron process has no CWD guarantee.

## References

- `references/scraper-template.md` — the scraper script the skill generates
  (scrapling + JSON-to-stdout + `--out`).
- `references/auto-level.md` — the auto-decide-category rule and domain extraction.
