## Why

scrapling-uv-mcp can *fetch* a page (get/fetch/stealthy_fetch) but cannot *find or run* the reusable scraper scripts the project generates — every extraction is a one-shot manual fetch, with no way to persist a scraper, re-run it, or drive it on a schedule. We need scrapers to be discoverable and executable through the MCP, and a project-scope skill that ties the full lifecycle together: inspect a site → generate a reusable scraper → persist its config → run it → schedule it to run automatically via cron-mcp.

## What Changes

- **scrapling-uv-mcp gains two tools**: `find_scripts` (list scrapling scraper scripts in a configured directory, returning name, path, and a one-line summary from each script's docstring/first comment) and `run_script` (execute a named scraper script in the server's own environment via `subprocess`, forwarding optional args, returning stdout/stderr/exit code). Registered following the existing low-level `@server.tool()` pattern in `mcp/scrapling-uv-mcp/server.py`.
- **A script-directory convention**: scrapers live in a single discoverable dir, resolved from a `SCRAPLING_SCRIPTS_DIR` env var with a default of `mcp/scrapling-uv-mcp/scripts/scrapers/`. The dir is created on first use.
- **A new project-scope skill `extract-web-data`** (created via `fd-skill-creator`, written to `.claude/skills/extract-web-data/`) that orchestrates the full extraction lifecycle using existing MCPs:
  1. Inspect a target URL via scrapling-uv-mcp `fetch`/`stealthy_fetch`.
  2. Generate a self-contained Scrapling scraper script (filename = slug of the config name) and save it to `SCRAPLING_SCRIPTS_DIR`.
  3. Persist the scraping config (name, url, columns) to the existing `scraw_configs` table via the existing `scripts/db_helper.py`.
  4. Verify by calling the new `run_script` tool.
  5. Optionally schedule recurring extraction via cron-mcp: ensure a cron **task** exists (`create_task` / `update_task`) whose command runs the saved script (`uv run --directory mcp/scrapling-uv-mcp python <script>.py`), then `create_schedule` referencing it by name, fire one immediate `run_now`, and read the captured output via `list_executions` to confirm.
- **Register the website as a managed daas datasource**: the skill also calls daas-mcp `create_datasource` (one shared slug = script name = `scraw_configs.name` = datasource `name`), so the site shows up in the managed catalog and `search_datasources`.
- **Automatically decide the category level**: the skill auto-resolves the `category_id` for the new datasource — a "Web Scraped" root → a child named after the site's registered domain (e.g. `example.com`), creating missing categories idempotently and reusing existing ones. The datasource lands at the domain leaf (depth 2, matching the existing seed convention). No user prompt for categorization.
- **Attach an extraction form/section**: the skill calls daas-mcp `add_form` + `add_section` carrying the target columns as the section `instruction`, so the scraped fields are queryable via `search_datasources(section=…)`. The datasource `config_json` points back to the `scraw_configs` name / script path so execution stays single-source-of-truth.
- **Reuses existing infrastructure unchanged**: the `scraw_configs` table/schema (no new columns, no migration), cron-mcp's existing task+schedule model (`create_task`/`create_schedule`/`run_now`/`list_executions` — no cron-mcp code change), and daas-mcp's existing `create_datasource`/`create_category`/`get_category_tree`/`add_form`/`add_section`/`search_datasources` (no daas-mcp code or schema change). The config→script→schedule→datasource link is by shared-slug convention, not a schema addition.

## Capabilities

### New Capabilities

- `scrapling-script-runner`: scrapling-uv-mcp can discover (`find_scripts`) and execute (`run_script`) reusable scraper scripts from a configured directory, returning structured results.
- `web-extract-skill`: a project-scope skill (`extract-web-data`) that drives the full website-data-extraction lifecycle — inspect, generate scraper, persist config, verify, and (optionally) schedule recurring extraction via cron-mcp — by composing scrapling-uv-mcp and cron-mcp tools.

### Modified Capabilities

<!-- None. cron-mcp and the scraw_configs schema are reused as-is; no spec-level requirement changes. -->

## Impact

- **Code**: `mcp/scrapling-uv-mcp/server.py` (two new tools + script-dir resolution); `mcp/scrapling-uv-mcp/scripts/scrapers/` (new default dir, created lazily); new `.claude/skills/extract-web-data/` skill (SKILL.md + optional references). daas-mcp and cron-mcp are consumed, not modified.
- **MCP surface**: two new tools exposed by scrapling-uv-mcp. cron-mcp (`create_task`/`create_schedule`/`run_now`/`list_executions`) and daas-mcp (`create_datasource`/`create_category`/`get_category_tree`/`add_form`/`add_section`/`search_datasources`) and `scraw_configs` are all consumed, not modified.
- **Dependencies**: none added — scrapling, cron-mcp, daas-mcp, and mcp-models are already installed/registered.
- **Config**: new optional `SCRAPLING_SCRIPTS_DIR` env var (root `.env`), defaults to the in-repo scrapers dir.
- **Registration**: `.mcp.json` unchanged — scrapling-uv-mcp, daas-mcp, and cron-mcp are already registered.
