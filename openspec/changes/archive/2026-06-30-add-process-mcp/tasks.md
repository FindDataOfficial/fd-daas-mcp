## 1. Shared schema — two new tables

- [x] 1.1 Add `ProcessRule` to `mcp/models/models.py`: `__tablename__="process_rules"`; columns `id` (int pk), `name` (str, unique, indexed), `source_table` (str), `text_column` (str), `schema_json` (JSON), `prompt` (Text nullable), `model` (str nullable), `max_chars` (int default 12000), `enabled` (Boolean default True), `last_rowid` (int default 0), `datasource` (str nullable, traceability), `created_at`/`updated_at`. Add `to_dict()` (omit api keys; include schema_json).
- [x] 1.2 Add `ProcessResult`: `__tablename__="process_results"`; `id` (int pk), `rule_id` (FK→`process_rules.id` ON DELETE CASCADE, indexed), `source_table` (str, indexed), `source_rowid` (int, indexed), `extracted_json` (JSON), `model` (str), `run_at` (DateTime default utcnow); `UniqueConstraint("rule_id","source_table","source_rowid", name="uq_process_result")`.
- [x] 1.3 Bump the table-count note in `mcp/models/models.py` docstring (13 → 15) and add a `process-mcp` domain line.
- [x] 1.4 From `mcp/process-mcp/`, confirm `from models import ProcessRule, ProcessResult` resolves and `Base.metadata.create_all` creates both tables in a temp DB (no migration of existing tables).

## 2. Scaffold the MCP directory

- [x] 2.1 Create `mcp/process-mcp/` with `server.py`, `process_tools.py`, `process_database.py`, `pyproject.toml`, `.env`, `.env.example`, `selfcheck.py`
- [x] 2.2 Write `pyproject.toml`: name `process-mcp`, `requires-python>=3.10`, deps `fastmcp>=2.0`, `httpx>=0.27`, `jsonschema>=4`, `pypdf>=4`, `sqlalchemy>=2.0`, `python-dotenv>=1.0`, `mcp-models` (path dep on `../../mcp/models`)
- [x] 2.3 Write `.env.example` and `.env` declaring `LLM_API_KEY=`, `LLM_BASE_URL=`, `LLM_MODEL=`, `PROCESS_MODELS=` (comment: optional JSON; unset → single default model)
- [x] 2.4 `cd mcp/process-mcp && uv sync` succeeds

## 3. server.py — bootstrap, env, model registry

- [x] 3.1 Add unified-env dotenv load (root `.env` first, then per-MCP `.env` with `override=True`), matching `edinet-mcp/server.py`
- [x] 3.2 Put `mcp/models` on `sys.path`; `app = FastMCP(name="process-mcp")`
- [x] 3.3 Implement `load_models()` (in `process_tools.py`): parse `PROCESS_MODELS` JSON; when unset expose one `default` from `LLM_MODEL`/`OPENAI_MODEL` (default `gpt-4o`) with shared `LLM_BASE_URL`/`LLM_API_KEY`/`OPENAI_API_KEY`; resolve per-model `base_url`/`api_key` overrides. Cache at module load.
- [x] 3.4 `resolve_model(name?)`: return named model or first/default; raise `ProcessError` if name unknown or no api_key configured
- [x] 3.5 Bottom of file: `if "--run-rule" in sys.argv:` → parse `<name>`, call `_cli_run_rule(name)`, print JSON summary, `sys.exit(0)`/`sys.exit(1)`; else `app.run(transport="stdio", show_banner=False)`

## 4. process_tools.py — LLM call helper (D1, D5)

- [x] 4.1 `_chat(model_cfg, system, user_content, json_mode=True) -> str`: POST `{base_url}/chat/completions`, `model`, messages, `temperature:0`; when `json_mode` set `response_format:{type:"json_object"}`; `Authorization: Bearer <api_key>`; `httpx` timeout 120s
- [x] 4.2 On an HTTP error indicating `response_format` rejection, retry once without it; strip a ```` ```json ... ``` ```` fence if present
- [x] 4.3 `_extract_once(model_cfg, system, user_content, schema) -> (records, err)`: call `_chat`, parse JSON, accept `{records:[...]}` or bare list, validate via `jsonschema` against array-wrapped schema; return `(records, None)` or `(None, err)`
- [x] 4.4 Wrap `_extract_once` with one retry prepending a "your previous output was invalid; return strict JSON conforming to the schema" preamble (mirror `cnreport.ai_extract._attempt`)

## 5. process_tools.py — ad-hoc extraction tools

- [x] 5.1 `_split_chunks(text, max_chars) -> list[str]`: split on paragraph boundaries when possible, else hard `max_chars` cuts; never exceed `max_chars` per chunk
- [x] 5.2 `extract_text(text, schema: dict, prompt=None, model=None, max_chars=12000) -> dict`: single call if fits, else per-chunk extract + merge dedup pass; return `{records, count, chunk_count, merge_notes?}`; on failure `{error, detail, chunk_count}`
- [x] 5.3 `_encode_image(image) -> (data_url, media_type)`: `http(s)://` pass-through; local path → read bytes, infer type from suffix, build `data:<type>;base64,<b64>`; raw base64 → wrap `data:image/png;base64,<input>`
- [x] 5.4 `extract_image(image, schema: dict, prompt=None, model=None) -> dict`: resolve model, refuse if `vision` false/unset; enforce `max_image_bytes` (default 5 MB) on encoded form; build `[{type:text}, {type:image_url, image_url:{url}}]`; run `_extract_once`; return `{records, count}` or `{error, detail}`
- [x] 5.5 `_read_file_text(path) -> str`: `.txt`/`.md` UTF-8; `.pdf` → `pypdf.PdfReader` page text joined; else raise `ProcessError("unsupported file type")`
- [x] 5.6 `extract_file(path, schema: dict, prompt=None, model=None, max_chars=12000) -> dict`: read via `_read_file_text`, forward through `extract_text` path
- [x] 5.7 `list_models() -> dict`: return `{name, model, vision, base_url}` per configured model (no api keys)

## 6. process_database.py — DB access (D7, D9)

- [x] 6.1 `Database` singleton over `DAAS_DATABASE_URL` (default `sqlite:///mcp/daas.db`); `Base.metadata.create_all` on init (creates `process_rules`/`process_results`); `get_session()` context manager
- [x] 6.2 Rule CRUD: `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule` (delete relies on FK CASCADE for results)
- [x] 6.3 `upsert_result(rule_id, source_table, source_rowid, extracted_json, model)`: INSERT … ON CONFLICT(rule_id, source_table, source_rowid) DO UPDATE (SQLite upsert)
- [x] 6.4 `list_source_tables()`: query `sqlite_master` for `type='table' AND name LIKE 'scraw_%'`; per table, `PRAGMA table_info` for columns + `SELECT count(*)` for row count
- [x] 6.5 `_validate_identifier(name)`: `re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)`; used for `source_table`/`text_column`
- [x] 6.6 `_table_exists(name)` / `_column_exists(table, col)`: check `sqlite_master` / `PRAGMA table_info`

## 7. server.py — source-table discovery + rule CRUD tools

- [x] 7.1 `list_source_tables()` tool: wrap `db.list_source_tables()`; return `{tables: [{name, row_count, columns}]}` (only `scraw_*`)
- [x] 7.2 `create_rule(name, source_table, text_column, schema, prompt=None, model=None, max_chars=12000, datasource=None, enabled=True)`: validate identifiers + table/column existence (D10); on failure return `{error}`; else `db.create_rule(...)` and return the rule dict
- [x] 7.3 `list_rules()`, `get_rule(name)`, `update_rule(name, ...)` (only provided fields), `delete_rule(name)` — wrap DB CRUD; `delete_rule` returns `{deleted: name, results_cascaded: true}`

## 8. server.py — run_rule (D9) + cron CLI branch (D11)

- [x] 8.1 `run_rule(name, batch=500) -> dict`: load rule; if `enabled` false return `{error: "rule disabled"}`; resolve `model`; build guarded query `SELECT rowid, <text_column> FROM <source_table> WHERE rowid > :cursor ORDER BY rowid LIMIT :batch` (identifiers validated in D10); iterate rows, call `extract_text` per row's text against `schema_json`, `db.upsert_result(...)`; track `processed`/`failed`; advance `rule.last_rowid` to max rowid processed
- [x] 8.2 Return `{rule: name, processed, failed, next_rowid, up_to_date: (processed < batch)}`
- [x] 8.3 `_cli_run_rule(name)`: call `run_rule` logic, return a JSON-serializable summary (for stdout); `sys.exit(1)` on unhandled error with `{error}` to stderr
- [x] 8.4 Confirm `python server.py --run-rule <name>` prints JSON and exits 0 without starting stdio; confirm `python server.py` (no args) starts the MCP server

## 9. Wire into the repo

- [x] 9.1 Add `process-mcp` entry to root `.mcp.json`: `type: stdio`, command `uv run --directory /Users/chengsishi/code/cli-anything/mcp/process-mcp python server.py`, parallel to `edinet-mcp`
- [x] 9.2 Add `mcp/process-mcp/` subsection to root `CLAUDE.md` under "MCP Servers": entry, deps, env (`LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` + optional `PROCESS_MODELS` JSON), the 11 tools, the `scraw_<slug>` source-data naming rule, the `process_rules`/`process_results` schema tables, the `--run-rule` cron CLI branch, and a worked cron example (`create_task` + `create_schedule`)
- [x] 9.3 Note in `CLAUDE.md` that `process_results` is queryable via `dashboard-mcp.query_table(database="daas", table="process_results")`

## 10. Verify

- [x] 10.1 `cd mcp/process-mcp && uv sync` succeeds; `python3 server.py` starts the MCP server without error
- [x] 10.2 On first run against `daas.db`, `process_rules` and `process_results` are created; no other table is altered
- [x] 10.3 `list_models()` returns configured models with correct `vision` flags
- [x] 10.4 `list_source_tables()` returns only `scraw_*` tables with row counts + columns
- [x] 10.5 `create_rule` rejects a missing table and a missing column with clear errors; accepts a valid `scraw_<slug>` + `text_column`
- [x] 10.6 `extract_text`/`extract_image`/`run_rule` return a clear `error` when `LLM_API_KEY` is unset (no network call)
- [x] 10.7 Smoke `run_rule` against a tiny `scraw_<slug>` fixture (≤3 rows): first run `processed=3`, second run `processed=0`/`up_to_date=true`, re-run after deleting a result row is idempotent (no duplicate)
- [x] 10.8 SQL-injection guard: `run_rule` on a rule whose `source_table` is malicious returns `{error: "invalid source_table identifier"}` and runs no source-table SQL
- [x] 10.9 `python server.py --run-rule <name>` prints a JSON summary and exits 0 without starting stdio
- [x] 10.10 `delete_rule` cascades: its `process_results` rows are removed
- [x] 10.11 Add an opt-in `__main__` self-check (`selfcheck.py`, guarded by env key presence) exercising `list_models`, `list_source_tables`, rule CRUD, and a short `extract_text`, so non-trivial logic has a runnable check
