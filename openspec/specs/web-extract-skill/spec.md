# web-extract-skill Specification

## Purpose
TBD - created by archiving change add-scrapling-extract-skill-with-cron. Update Purpose after archive.
## Requirements
### Requirement: Inspect target page
The `extract-web-data` skill SHALL inspect a target URL before generating a scraper, using scrapling-uv-mcp's `fetch` or `stealthy_fetch` tool (choosing `stealthy_fetch` when the site is known or detected to be anti-bot protected). The skill SHALL use the fetched content to identify the data structure and target columns to extract.

#### Scenario: plain site
- **WHEN** the user provides a URL to a plain (non-protected) site
- **THEN** the skill calls `fetch` and derives the target columns from the returned content

#### Scenario: anti-bot site
- **WHEN** the target site is protected (e.g., Cloudflare) or `fetch` returns a challenge/blocked response
- **THEN** the skill falls back to `stealthy_fetch` to obtain the real page content

### Requirement: Generate and persist a reusable scraper script
The skill SHALL generate a self-contained Python scraper script (importing `scrapling`) that extracts the identified columns and prints the result as JSON to stdout, and SHALL save it to `SCRAPLING_SCRIPTS_DIR` with a filename equal to the slug of the config name. The skill SHALL refuse to overwrite an existing `<slug>.py` unless the user explicitly confirms.

#### Scenario: new scraper saved
- **WHEN** the user provides a URL and target columns and no `<slug>.py` exists
- **THEN** the skill writes a runnable scraper to `<SCRAPLING_SCRIPTS_DIR>/<slug>.py` whose docstring states what it scrapes

#### Scenario: collision guarded
- **WHEN** `<slug>.py` already exists and the user has not confirmed overwrite
- **THEN** the skill reports the collision and does not overwrite

### Requirement: Persist scraping config
The skill SHALL persist the scraping configuration (name, url, columns) to the existing `scraw_configs` table via `mcp/scrapling-uv-mcp/scripts/db_helper.py` (`save_config`). The script filename SHALL be derivable from the config name by slugification, establishing the config↔script link by convention.

#### Scenario: config recorded
- **WHEN** a scraper is generated and saved
- **THEN** a row with `{name, url, columns_json}` exists in `scraw_configs` retrievable via `get_config(name)`

### Requirement: Verify the scraper by running it
The skill SHALL verify the generated scraper by calling scrapling-uv-mcp's `run_script` tool with the new script's name, and SHALL report the extracted output (stdout) to the user before offering to schedule it.

#### Scenario: verification passes
- **WHEN** `run_script` returns `returncode=0` with JSON stdout
- **THEN** the skill reports a sample of the extracted data and proceeds to offer scheduling

#### Scenario: verification fails
- **WHEN** `run_script` returns a non-zero exit code or empty output
- **THEN** the skill reports the failure and stderr, and does not offer scheduling until the scraper is fixed

### Requirement: Register the website as a managed daas datasource
After the scraper is verified, the skill SHALL register the website as a managed daas datasource by calling daas-mcp `create_datasource`. The datasource `name` SHALL be the shared slug (equal to the script stem and `scraw_configs.name`), `url` SHALL be the target URL, and `config_json` SHALL reference the `scraw_configs` name and the script's absolute path so execution stays single-source-of-truth. The skill SHALL first call `search_datasources(source_name=<slug>)`; if a datasource with that name already exists, it SHALL call `update_datasource` instead of creating a duplicate (idempotent).

#### Scenario: new datasource registered
- **WHEN** the scraper is verified and no daas datasource with the slug name exists
- **THEN** the skill calls `create_datasource` with `name=<slug>`, `url=<target>`, `config_json` pointing to the `scraw_configs` name and script path, and a `category_id` resolved per the auto-level requirement, and the datasource appears in `search_datasources`

#### Scenario: existing datasource updated
- **WHEN** `search_datasources(source_name=<slug>)` already returns a datasource
- **THEN** the skill calls `update_datasource` to refresh its fields (url, config_json, category_id) and does NOT create a duplicate

### Requirement: Automatically decide the category level
The skill SHALL automatically decide the datasource's placement in the daas-mcp category tree (the "level" = category depth; daas-mcp has no separate level field) with no user prompt for categorization. It SHALL: call `get_category_tree`; find-or-create a root category named `Web Scraped`; find-or-create a child category named after the site's registered domain (e.g. `example.com`) under `Web Scraped`; and pass that domain leaf's `category_id` to `create_datasource`/`update_datasource`. Category creation SHALL be idempotent (reuse an existing same-named category rather than duplicating).

#### Scenario: placement under a new domain leaf
- **WHEN** the target URL's registered domain is `example.com` and neither `Web Scraped` nor an `example.com` child exists
- **THEN** the skill creates the `Web Scraped` root and the `example.com` child, and registers the datasource with that child's `category_id`, landing at depth 2

#### Scenario: reuse of existing categories
- **WHEN** a `Web Scraped` root and/or an `example.com` child already exist
- **THEN** the skill reuses the existing category node(s) and does not create duplicates

#### Scenario: same site scraped again
- **WHEN** the skill is run for a URL whose domain leaf already exists and a datasource with the slug already exists
- **THEN** the datasource is updated in place under the existing domain leaf with no new categories or datasource created

### Requirement: Attach an extraction form and section
The skill SHALL call daas-mcp `add_form(source_name=<slug>, form_type="page", label=<page title or url>)` and then `add_section(form_id, section_name="columns", instruction=<the target column list>)` so the scraped fields are queryable via `search_datasources(section="columns")` and visible in `list_forms`.

#### Scenario: columns queryable
- **WHEN** the datasource is registered and a form/section is attached
- **THEN** `search_datasources(source_name=<slug>, section="columns")` returns the datasource with the column list carried in the section `instruction`

### Requirement: Schedule recurring extraction via cron-mcp
When the user opts in, the skill SHALL schedule recurring extraction using cron-mcp's task+schedule model: (1) ensure a cron **task** named `scrape_<slug>` exists whose `command` runs the saved script in scrapling-uv-mcp's environment (`uv run --directory <abs>/mcp/scrapling-uv-mcp python <abs>/<slug>.py`) — creating it via `create_task` if absent or refreshing it via `update_task` if present (checked via `list_db_tasks`, since `create_task` rejects duplicate names); (2) `create_schedule(name="scrape_<slug>_<freq>", cron=<expr>, task="scrape_<slug>", enabled=True)` — reusing an existing schedule for that task (found via `list_schedules`) rather than duplicating, since there is no `update_schedule`; (3) `run_now(schedule_id)` to fire one immediate execution; (4) `list_executions(schedule_id, limit=1)` to read the captured `output`. The skill SHALL report the returned `schedule_id` to the user.

#### Scenario: schedule created and confirmed
- **WHEN** the user opts in with a cron expression (e.g., daily) and no `scrape_<slug>` task or schedule exists yet
- **THEN** the skill calls `create_task` with the `uv run --directory … python …` command, `create_schedule` referencing the task by name, `run_now` once, reads the immediate-run result via `list_executions`, and reports the schedule id

#### Scenario: existing task reused
- **WHEN** a `scrape_<slug>` task already exists (site re-scraped)
- **THEN** the skill calls `update_task` to refresh the command rather than `create_task`, reuses any existing schedule for that task instead of creating a duplicate, and reports the schedule id

#### Scenario: no schedule requested
- **WHEN** the user declines scheduling
- **THEN** the skill stops after verification, leaving only the saved script and `scraw_configs` row, with no task or schedule created

