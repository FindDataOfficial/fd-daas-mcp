## Context

scrapling-uv-mcp (`mcp/scrapling-uv-mcp/server.py`) is a low-level `mcp.server.lowlevel.Server` (not FastMCP) that proxies Scrapling fetchers — `get`, `fetch`, `stealthy_fetch`, bulk/session/screenshot variants — plus a few AKShare/CKAN tools. It can fetch a page but has no concept of *reusable scrapers*: scripts are generated ad hoc by the `fd-daas-scraw-scrapling` skill and saved to disk, with no way to list them, run them, or drive them on a schedule through the MCP.

Alongside it sit two reusable pieces this change builds on:
- `mcp/scrapling-uv-mcp/scripts/{init_db.py,db_helper.py}` — a `ScrawConfig` model (mirrored in `mcp/models/models.py`) with `save_config/list_configs/get_config/delete_config`, persisting `{name, url, columns_json}` to `mcp/daas.db`. CRUD exists but is script-only, not exposed as MCP tools.
- `mcp/cron-mcp/` (FastMCP) — `create_schedule`/`list_schedules`/`delete_schedule`/`run_task`/`get_executions`/`get_task_log`. A schedule with `task_type="command"` is shelled out by `agent_runner.py` via `subprocess`, so cron can run any command — including a scrapling scraper.

Constraints: single `.env`, single `mcp/daas.db`, single schema package `mcp/models/`. `.mcp.json` already registers scrapling-uv-mcp and cron-mcp.

## Goals / Non-Goals

**Goals:**
- scrapling-uv-mcp can discover and execute reusable scraper scripts through two new MCP tools.
- A project-scope skill (`extract-web-data`) composes scrapling-uv-mcp + cron-mcp + daas-mcp to take a URL from "I want this data" to "it runs on a schedule", reusing existing storage and scheduling rather than building new ones.
- The skill registers the website as a managed daas datasource and auto-places it in the category tree (decides the "level" = category depth) with no user prompt, plus attaches an extraction form/section so the columns are queryable.
- No new dependencies, no new tables, no schema migration.

**Non-Goals:**
- Migrating scrapling-uv-mcp from the low-level SDK to FastMCP (would touch every existing tool).
- Exposing `scraw_configs` CRUD as MCP tools (the skill calls `db_helper.py` directly).
- Persisting extracted rows into daas `observations` or any queryable store — scripts write to stdout/file; downstream storage is a future capability.
- A management UI for scheduled extractions — cron-mcp's `list_schedules`/`delete_schedule` suffice for now.
- Deleting or rewriting the existing `fd-daas-scraw-scrapling` skill.

## Decisions

### D1. Subclass `ScraplingMCPServer` and override `serve()` to add the two tools
`server.py` is a thin wrapper over scrapling's `ScraplingMCPServer`, whose `serve()` builds a `FastMCP`, registers each fetch tool via `server.add_tool(self.<method>, title=…, …)`, then calls `server.run()`. There is no public hook to add tools before run, so we subclass `ScraplingMCPServer`, add `find_scripts`/`run_script` as methods, and override `serve()` to register the existing fetch tools *plus* the two new ones, then run. Additive — no change to scrapling or to existing fetch tool behavior.
- *Why:* keeps the thin-wrapper spirit, adds two tools in one file, shortest path that works.
- *Alternative:* migrate the whole server to a hand-written FastMCP (as cron-mcp/daas-mcp use). Rejected — large blast radius, no functional gain.
- *Note:* the override duplicates scrapling's `add_tool` list (~10 lines). `ponytail:` comment names this and the upgrade path (contribute an `add_tool` hook upstream, or refactor when scrapling exposes its FastMCP builder). Risk is low — scrapling's tool surface is stable; a tool-list assertion in the selfcheck catches drift.

### D2. Single script directory, resolved by env var
Scrapers live in one dir: `SCRAPLING_SCRIPTS_DIR` env var, default `mcp/scrapling-uv-mcp/scripts/scrapers/` (created lazily on first `find_scripts`/`run_script`/skill-save). `find_scripts` scans `*.py` there.
- *Why:* one well-known location the MCP and the skill agree on; env override lets users point elsewhere without code changes.
- *Alternative considered:* store script paths in `scraw_configs` and query the DB. Rejected (YAGNI) — filename convention (script stem = config slug) is the soft link and the DB schema stays untouched. See Open Questions for the deferred upgrade.

### D3. `find_scripts` returns name + path + one-line summary
For each `*.py`, return `{name: <stem>, path: <abs>, summary: <first line of module docstring, or first `#` comment, or "">}`. No execution.
- *Why:* lets the agent pick a script without running anything; the summary is enough to disambiguate.
- *Alternative:* return full source. Rejected — noisy; `run_script` + the file itself exist for that.

### D4. `run_script` executes via `sys.executable` in the server's own venv, with a timeout
`subprocess.run([sys.executable, script_path, *args], cwd=<mcp_dir>, capture_output=True, timeout=<env or 120s>)`. Return `{returncode, stdout, stderr}` as text.
- *Why:* `sys.executable` reuses the already-running interpreter, so scrapling (installed in this venv) is importable with no extra resolve cost. `cwd=mcp_dir` matches how the server is launched (`uv run --directory …`).
- *Alternative:* `uv run --directory … python …`. Rejected — strictly more process overhead for the same env; reserved for the *cron* path (D6), which runs outside this venv.

### D5. No schema change — reuse `scraw_configs` and cron-mcp `command` as-is
The skill persists `{name, url, columns_json}` via `db_helper.save_config` (existing). It links config↔script↔schedule by **naming convention**: script filename = `slug(config_name).py`; cron schedule `name` embeds the config name. No new columns, no migration, no FK.
- *Why:* the user's goal is *set up and run*, not *manage joins*. cron-mcp already lists/deletes schedules; the join is recoverable from names. Adding `script_path`/`schedule_id` columns is speculative until a management need appears.
- *Alternative considered:* add nullable `script_path` + `schedule_id` to `ScrawConfig` with a guarded `ALTER` (the `category_id` pattern). Rejected for now — see Open Questions.
- *Trade-off:* no single-query "which configs are scheduled" view; mitigated by naming + `list_schedules`.

### D6. Cron runs the scraper via a cron-mcp DB task + schedule (tasks and schedules are separate)
cron-mcp separates **tasks** (a named shell command stored in the `tasks` table, run by `agent_runner` via `subprocess.run(command, shell=True, timeout=task.timeout)`) from **schedules** (a cron expression referencing a task *by name*). There is no `task_type` enum and no inline command on the schedule. So the skill drives scheduling in four calls:
1. Ensure a task exists for the scraper: `list_db_tasks` → if `scrape_<slug>` exists, `update_task(name="scrape_<slug>", command=…)`; else `create_task(name="scrape_<slug>", command="uv run --directory <abs>/mcp/scrapling-uv-mcp python <abs>/<slug>.py", timeout=…)` (`create_task` rejects duplicate names, hence the check).
2. `create_schedule(name="scrape_<slug>_<freq>", cron=<expr>, task="scrape_<slug>", enabled=True)` → returns `schedule_id`. For re-runs on the same site, `list_schedules` to find an existing schedule whose `task == "scrape_<slug>"` and reuse it rather than creating a duplicate (there is no `update_schedule`).
3. `run_now(schedule_id)` — fires once immediately; the run is synchronous, result is written to an `Execution` row.
4. `list_executions(schedule_id, limit=1)` — read `output` (the captured stdout) to confirm it ran.
- *Why:* matches cron-mcp's real API (`create_task`/`create_schedule`/`run_now`/`list_executions`, not `task_type`/`run_task`). `shell=True` runs the `uv run …` string verbatim.
- *venv resolution:* cron-mcp's process can't import scrapling, so the command uses `uv run --directory <abs>/mcp/scrapling-uv-mcp` to activate scrapling-uv-mcp's venv wherever cron runs; absolute paths avoid CWD ambiguity at fire time.
- *Alternative:* a thin wrapper script. Rejected (YAGNI) — the one-line `uv run` invocation is self-contained.

### D7. New skill composes MCPs; does not reimplement scraping or scheduling
`extract-web-data` (created via `fd-skill-creator` into `.claude/skills/extract-web-data/`) is a thin orchestrator: scrapling-uv-mcp `fetch`/`stealthy_fetch` to inspect → generate a self-contained Scrapling script → save to `SCRAPLING_SCRIPTS_DIR` → `db_helper.save_config` → `run_script` to verify → cron-mcp `create_schedule` (`task_type="command"`, command from D6) → cron-mcp `run_task` for one immediate confirmation.
- *Why:* the building blocks exist; the skill is glue + a script template. Relationship to `fd-daas-scraw-scrapling`: that skill covers fetch→generate→save→persist (one-shot). This skill adds run + schedule and is the canonical *automated* path. The old skill is left intact (non-goal to remove it); overlap is noted, not duplicated, because both reuse the same `scraw_configs` table and script dir.
- *Alternative:* extend `fd-daas-scraw-scrapling` in place. Rejected — user explicitly asked for a new skill via `skill-creator`, and a dedicated automated-extraction skill keeps each skill's trigger crisp.

### D8. Scraper scripts write JSON to stdout; optional `--out <file>` for scheduled runs
Generated scripts print extracted records as JSON to stdout (captured by `run_script` return and by cron-mcp's execution log). For scheduled runs that need a durable file, the script accepts `--out <path>`.
- *Why:* stdout is the simplest contract that both ad-hoc `run_script` and cron capture uniformly.

### D9. Register the website as a managed daas datasource (one shared slug)
The skill calls daas-mcp `create_datasource(name=<slug>, label=<site/page>, description=…, url=<url>, config_json=`{"scraw_config": "<slug>", "script": "<abs script path>"}`, category_id=<resolved per D10>)`. The same slug ties script ↔ `scraw_configs.name` ↔ datasource `name`. If `search_datasources(source_name=<slug>)` already finds it, the skill calls `update_datasource` instead (idempotent).
- *Why:* daas-mcp is the managed catalog (category tree, forms/sections, collections, search); `scraw_configs` is the execution store. Registering in both gives a queryable catalog without a second execution source of truth — `config_json` points back to the `scraw_configs` name/script.
- *Alternative:* store everything in daas and drop `scraw_configs`. Rejected — the scraper-runner tools (D3/D4) and the existing `fd-daas-scraw-scrapling` skill already key off `scraw_configs`/the script dir; removing it is out of scope.

### D10. "Automatically decide the level" = auto-resolve `category_id` by domain, depth 2
daas-mcp has **no `level` field** — category depth is derived from `parent_id`, and the seed (`seed_external_mcps.py`) places datasources at depth 2 (leaf under a root). So "the level" = which category node (→ depth) the datasource attaches to. The skill decides it automatically, no user prompt:
1. `get_category_tree()` to load existing categories.
2. Find-or-create a root category `Web Scraped` (match by name; `create_category` is idempotent on dupe-name via a name lookup before create).
3. Find-or-create a child named after the site's **registered domain** (e.g. `example.com`) under `Web Scraped`.
4. Pass that domain leaf's `category_id` to `create_datasource`.
- *Why:* domain is a stable, derivable key (from the URL) that needs no inference model; depth-2 matches the seed convention so the tree stays uniform. No prompt honors the user's "automatically decide" intent.
- *Alternative:* infer a *topic* category (e.g. "News", "Finance") via the LLM. Rejected for v1 — domain is deterministic and free; topic inference is speculative until users ask to browse by topic. Noted as an open question.
- *Alternative:* dump at root (no category). Rejected — un-categorized datasources clutter root and defeat the catalog's purpose.

### D11. Attach a form + section carrying the target columns as the extraction instruction
After `create_datasource`, the skill calls `add_form(source_name=<slug>, form_type="page", label=<page title or url>)` then `add_section(form_id, section_name="columns", instruction=<the column list, as JSON or prose>)`. This makes the scraped fields discoverable via `search_datasources(section="columns")` and visible in `list_forms`, mirroring how the seed encodes extraction rules in section `instruction`s.
- *Why:* the form/section model is exactly daas-mcp's mechanism for per-datasource extraction metadata; reusing it needs no schema change and integrates with `search_datasources`.
- *Alternative:* one section per column-group/page. Deferred (YAGNI) — a single "columns" section with the full list covers the queryable-columns goal; finer granularity can come later.

## Risks / Trade-offs

- **[Runaway scraper blocks the MCP stdio loop]** → `run_script` enforces a timeout (default 120s, `SCRAPLING_SCRIPT_TIMEOUT`). Very long scrapers should be *scheduled* (run by cron-mcp out-of-band), not called ad hoc.
- **[Script filename collisions]** → the skill slugifies the config name and refuses to overwrite an existing `<slug>.py` unless the user confirms; `db_helper` keys configs by name, reinforcing uniqueness.
- **[cron-mcp can't import scrapling]** → mitigated by D6 (the schedule command invokes `uv run --directory scrapling-uv-mcp`).
- **[No durable config↔schedule join]** → acceptable per D5; recoverable via naming + `list_schedules`. If a management UI is later needed, add `script_path`/`schedule_id` columns then.
- **[Running arbitrary `.py` is a security-sensitive operation]** → `run_script` only executes files already in the project-local `SCRAPLING_SCRIPTS_DIR` (generated by the skill, trusted). It is not exposed to untrusted input and is a dev/data tool, not a public API. No path traversal: `run_script(name)` resolves `<dir>/<slug>.py` and rejects names containing path separators or `..`.
- **[Two `ScrawConfig` definitions (mcp/models vs scripts/init_db.py)]** → unchanged by this design (no new columns), so no drift is introduced. If D5's deferred columns are ever added, that's the moment to make `scripts/init_db.py` import the canonical model instead of redefining it.
- **[Dual registration: `scraw_configs` + daas `datasources` drift]** → the shared slug + `config_json` pointer (D9) keep them aligned; the skill is idempotent (`search_datasources` → `update_datasource` on existing name). If a config is deleted, the skill should `delete_datasource` the matching entry (a future cleanup task; not blocking for the stated goal).
- **[Category-tree clutter from many domains]** → bounded at depth 2 (one leaf per domain); if a domain accumulates many datasources, a per-page subcategory can be added later. No user-visible problem at v1 scale.

## Migration Plan

- **Deploy**: additive only. New `SCRAPLING_SCRIPTS_DIR` env (optional, defaults to in-repo dir). New tools registered on next scrapling-uv-mcp restart. New skill is a new file. The scrapers dir is created lazily.
- **Rollback**: remove the two tools from `server.py`, remove `.claude/skills/extract-web-data/`, unset the env var. Existing scrapling-uv-mcp fetch tools, `scraw_configs`, cron-mcp, and any already-saved scripts/schedules are unaffected. Already-created cron schedules continue to fire (delete them via cron-mcp `delete_schedule` if desired).

## Open Questions

- **Durable config↔schedule link?** Deferred. If users ask "show me which extractions are scheduled" or "pause config X", add nullable `script_path` + `schedule_id` to `ScrawConfig` (guarded `ALTER`, soft FK) and have the skill write them on creation. Not needed for the stated goal.
- **Where do scheduled extractions land?** Today: stdout (in the cron execution log) + optional `--out` file. Wiring into daas `observations` is a separate future capability.
- **What does "level" mean?** Interpreted here as category-tree depth (the only hierarchy daas-mcp exposes for datasources; no `level` field exists). If the user instead meant form/section granularity (datasource-only vs. +form vs. +sections per column-group) or a topic-based (vs. domain-based) placement, the spec's auto-level rule (D10) is the one knob to revisit — the rest of the registration is unaffected.
