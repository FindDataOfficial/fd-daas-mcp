## Why

The fleet's only LLM-extraction tool (`cnreport-mcp.ai_extract`) is hard-wired to one domain, truncates long text, is text-only, and binds a single model. Worse, there is no way to *persist* an extraction rule and replay it on a schedule — so the obvious workflow ("scrape a site → on a cron, extract structured fields from each new row → store results") cannot be expressed today. `process-mcp` is the missing primitive: a model-pluggable extractor (long text + images) **with persisted rules** that reads scraped source-data tables and is drivable by `cron-mcp`, closing the scrape→extract→store loop alongside `daas-mcp`.

## What Changes

- Add `mcp/process-mcp/` — a FastMCP (stdio) MCP that is now **DB-backed** (writes to `mcp/daas.db` via the shared `mcp/models` package), not stateless.
- **Model registry in env**: `PROCESS_MODELS` JSON maps named models to `{model, vision?, base_url?, api_key?}`; falls back to the existing `LLM_MODEL`/`LLM_BASE_URL`/`LLM_API_KEY` single-model env. Tools take an optional `model` name.
- **Ad-hoc extraction tools** (no rule needed): `list_models`, `extract_text` (long text, chunked map-reduce — not truncated), `extract_image` (vision: path/URL/base64), `extract_file` (local .txt/.md/.pdf → `extract_text`).
- **Persisted rules** (new shared-schema tables in `mcp/models/models.py`): `process_rules` (name, source_table, text_column, schema_json, prompt, model, max_chars, last_rowid cursor, enabled) and `process_results` (rule_id, source_table, source_rowid, extracted_json, model, run_at — idempotent upsert on rule+source+rowid).
- **Source-data table naming rule**: scraped data rows live in dynamically-created tables named `scraw_<slug>` (the `<slug>` matches `scraw_configs.name` and `sources.config.scraw_config`). process-mcp discovers them with `list_source_tables()` (introspects `sqlite_master` for `scraw_*`) and validates the name before any SQL.
- **Rule tools**: `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`.
- **`run_rule(name)`**: incremental — reads source rows with `rowid > last_rowid`, runs `extract_text` per row's `text_column` against the rule's schema, upserts into `process_results`, advances the cursor. Safe to re-run (idempotent).
- **Cron integration**: `server.py` gains a `--run-rule <name>` CLI branch (runs `run_rule` in-process and exits). A `cron-mcp` `Task.command` shells out to `uv run --directory mcp/process-mcp python server.py --run-rule <name>`, and a `Schedule` ties a `cron_expr` to it. Uses cron-mcp's existing subprocess-task model — no change to `cron-mcp`.
- **daas integration**: a rule optionally carries a `datasource` name (daas `sources.name`) for traceability; `sources.config.scraw_config` carries the slug, so the rule's `source_table` and the daas datasource point at the same scraped data. process-mcp does not modify daas tables; output `process_results` is queryable via `dashboard-mcp.query_table`.
- Add `mcp/process-mcp/pyproject.toml` (deps `fastmcp`, `httpx`, `jsonschema`, `pypdf`, `sqlalchemy`, `python-dotenv`, `mcp-models`) and `.env`/`.env.example`.
- Register `process-mcp` in root `.mcp.json` (parallel to `edinet-mcp`).
- Follow the unified-env convention (root `.env` first, then per-MCP `.env` with `override=True`).
- Update root `CLAUDE.md` "MCP Servers" section.

## Capabilities

### New Capabilities
- `process-mcp-server`: DB-backed FastMCP stdio server exposing env-configured multi-model LLM extraction (long-text chunked + image vision) AND persisted processing rules that incrementally extract structured records from `scraw_<slug>` source-data tables into a shared `process_results` table, drivable by `cron-mcp` via a `--run-rule` CLI branch.

### Modified Capabilities
<!-- None. cron-mcp and daas-mcp are consumed, not changed. The shared schema gains two tables (process_rules, process_results) but there is no existing "shared-schema" capability spec to modify; the tables are introduced under process-mcp-server. -->

## Impact

- **New code**: `mcp/process-mcp/` (server.py, process_tools.py, process_database.py, pyproject.toml, .env, .env.example, selfcheck.py).
- **Schema**: `mcp/models/models.py` gains `ProcessRule` (`process_rules`) and `ProcessResult` (`process_results`) — two new tables in the shared `Base`, created via `Base.metadata.create_all` alongside the rest. No migration of existing tables.
- **Config**: root `.mcp.json` gains one entry; root `CLAUDE.md` gains one subsection.
- **Dependencies**: adds `httpx`, `jsonschema`, `pypdf`, `sqlalchemy`, `python-dotenv`, `mcp-models` to a self-contained venv under `mcp/process-mcp/`.
- **External**: hits `LLM_BASE_URL` (any OpenAI-compatible endpoint) at runtime. Requires `LLM_API_KEY` (or per-model `api_key`); extraction tools return a clear error when the chosen model is unconfigured or a vision tool targets a non-vision model.
- **Integration**: reads source rows from `scraw_<slug>` tables in `mcp/daas.db` (created by the scrape skills/scrapling, not by process-mcp); writes to `process_results` in the same DB. cron-mcp invokes the `--run-rule` CLI as a subprocess task — no change to cron-mcp or daas-mcp code.
- **No breaking changes** to existing MCPs, the dashboard, or existing schema tables.
