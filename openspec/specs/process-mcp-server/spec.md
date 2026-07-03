### Requirement: Env-driven multi-model registry
The server SHALL read model configuration from env at startup. A `PROCESS_MODELS` JSON object maps a model name to `{model, vision?, base_url?, api_key?}`. When `PROCESS_MODELS` is unset, the server SHALL expose a single default model derived from `LLM_MODEL`/`OPENAI_MODEL` (default `gpt-4o`), using `LLM_API_KEY`/`OPENAI_API_KEY` for auth and `LLM_BASE_URL` for the endpoint. A per-model `api_key`/`base_url`, when present, SHALL override the shared values for that model only.

#### Scenario: PROCESS_MODELS defines text and vision models
- **WHEN** `.env` sets `PROCESS_MODELS={"fast":{"model":"gpt-4o-mini"},"eyes":{"model":"gpt-4o","vision":true}}`
- **THEN** `list_models` returns both `fast` (vision:false) and `eyes` (vision:true)

#### Scenario: PROCESS_MODELS unset falls back to single-model env
- **WHEN** `PROCESS_MODELS` is unset and `LLM_MODEL=qwen-max`, `LLM_API_KEY=sk-...`
- **THEN** `list_models` returns one model named `default` with `model=qwen-max` and `vision:false`

#### Scenario: Unconfigured endpoint surfaces a clear error
- **WHEN** no `LLM_API_KEY`/`OPENAI_API_KEY` and no per-model `api_key` is set
- **THEN** `extract_text`, `extract_image`, and `run_rule` return `{"error": "..."}` without raising and without making a network call

### Requirement: list_models tool
The server SHALL expose a `list_models()` tool returning the configured models as a list of `{name, model, vision, base_url}`. API keys SHALL never be serialized.

#### Scenario: list_models reports vision flag
- **WHEN** the registry contains a vision and a non-vision model
- **THEN** `list_models` returns one entry per model with the correct `vision` boolean

### Requirement: extract_text handles long text without truncation loss
The server SHALL expose an `extract_text(text, schema, prompt?, model?, max_chars?)` tool. When `len(text) <= max_chars` it SHALL make a single extraction call. When `len(text) > max_chars` it SHALL split the text into `max_chars`-sized chunks, extract records from each chunk against the schema, then run a merge pass that consolidates the per-chunk arrays into a single deduplicated array. The result SHALL include `records`, `count`, and `chunk_count`.

#### Scenario: short text is a single call
- **WHEN** `extract_text` is called with 500 chars of text and `max_chars=12000`
- **THEN** the result has `chunk_count=1` and `records` conform to `schema`

#### Scenario: long text is chunked and merged
- **WHEN** `extract_text` is called with 30000 chars and `max_chars=12000`
- **THEN** the result has `chunk_count=3` and `records` reflects content from all three chunks (no silent truncation)

#### Scenario: invalid model output is retried then validated
- **WHEN** the model returns output that fails JSON parsing or schema validation on the first attempt
- **THEN** the server retries once with a correction preamble, and only returns `{"error":...}` if the retry also fails

### Requirement: extract_image via a vision model
The server SHALL expose an `extract_image(image, schema, prompt?, model?)` tool. `image` accepts a local file path, an `http(s)://` URL, or a raw base64 string. The server SHALL send a vision message to a vision-capable model and return `records` conforming to `schema`.

#### Scenario: image URL is extracted
- **WHEN** `extract_image` is called with an `https://...png` URL and a vision model
- **THEN** the result `records` conform to `schema`

#### Scenario: local image path is base64-encoded and sent
- **WHEN** `extract_image` is called with a local `.png` path
- **THEN** the server encodes the file to a `data:image/png;base64,...` URL and includes it in the vision message

#### Scenario: non-vision model is refused
- **WHEN** `extract_image` is called with a model whose `vision` is false/unset
- **THEN** the server returns `{"error": "model <name> does not support vision"}` without a network call

#### Scenario: oversize image is refused
- **WHEN** the encoded image exceeds `max_image_bytes` (default 5 MB)
- **THEN** the server returns `{"error": "image exceeds max_image_bytes"}`

### Requirement: extract_file reads a local file and forwards to text extraction
The server SHALL expose an `extract_file(path, schema, prompt?, model?, max_chars?)` tool. For `.txt`/`.md` it SHALL read UTF-8 text; for `.pdf` it SHALL extract text per page via `pypdf` and join it. It SHALL then forward the string through the same extraction path as `extract_text` (including chunking when oversized).

#### Scenario: text file is read and extracted
- **WHEN** `extract_file` is called with a `notes.txt` path
- **THEN** the result equals calling `extract_text` with the file's contents

#### Scenario: PDF is read to text and extracted
- **WHEN** `extract_file` is called with a `report.pdf` path
- **THEN** the server extracts page text via `pypdf` and returns `records` conforming to `schema`

#### Scenario: unsupported file type is refused
- **WHEN** `extract_file` is called with a `.xlsx` path
- **THEN** the server returns `{"error": "unsupported file type"}`

### Requirement: OpenAI-compatible endpoint with JSON fallback
The server SHALL call the configured `base_url` + `/chat/completions` with `temperature:0` and `response_format:{type:"json_object"}`. If the endpoint rejects `response_format`, the server SHALL retry without it and parse a ```` ```json ```` fenced block from the raw content.

#### Scenario: endpoint rejects response_format
- **WHEN** the endpoint returns an error specifically rejecting `response_format`
- **THEN** the server retries the same call without `response_format` and still returns parsed `records`

### Requirement: Persisted processing rules in the shared schema
The server SHALL persist processing rules in two tables added to the shared `mcp/models` `Base`, created in `mcp/daas.db` via `Base.metadata.create_all`: `process_rules` (id, unique name, source_table, text_column, schema_json, prompt, model, max_chars, enabled, last_rowid, timestamps) and `process_results` (id, rule_id FK→process_rules.id with ON DELETE CASCADE, source_table, source_rowid, extracted_json, model, run_at) with a unique constraint on `(rule_id, source_table, source_rowid)` for idempotent upsert.

#### Scenario: tables are created on first run
- **WHEN** process-mcp starts against a `daas.db` that lacks the two tables
- **THEN** `Base.metadata.create_all` creates `process_rules` and `process_results` without altering any other table

#### Scenario: deleting a rule cascades to its results
- **WHEN** `delete_rule` removes a rule that has result rows
- **THEN** the `process_results` rows for that rule are deleted via the FK ON DELETE CASCADE

### Requirement: Source-data table naming rule and discovery
Scraped source-data tables SHALL be named `scraw_<slug>` where `<slug>` matches `scraw_configs.name` / `sources.config.scraw_config`. The server SHALL expose a `list_source_tables()` tool that introspects `sqlite_master` for tables whose name starts with `scraw_` and returns each with its row count and columns. The server SHALL NOT create these source tables (they are created by the scrape skills/scrapling).

#### Scenario: list_source_tables finds scraped data tables
- **WHEN** `daas.db` contains tables `scraw_news_finance` and `scraw_reddit_wsb`
- **THEN** `list_source_tables` returns both with their row counts and column lists

#### Scenario: non-scraw tables are excluded
- **WHEN** `daas.db` also contains `observations`, `sources`, `process_results`
- **THEN** `list_source_tables` returns only the `scraw_*` tables

### Requirement: Rule CRUD tools
The server SHALL expose `create_rule(name, source_table, text_column, schema, prompt?, model?, max_chars?, datasource?, enabled?)`, `list_rules()`, `get_rule(name)`, `update_rule(name, ...)`, and `delete_rule(name)`. `create_rule` SHALL validate that `source_table` exists in `sqlite_master` and that `text_column` exists in that table's `PRAGMA table_info` before creating the rule.

#### Scenario: create_rule validates the source table and column
- **WHEN** `create_rule` is called with `source_table="scraw_news_finance"` and `text_column="body"`
- **THEN** the rule is created and `list_rules` includes it

#### Scenario: create_rule rejects a missing table
- **WHEN** `create_rule` is called with `source_table="scraw_does_not_exist"`
- **THEN** the server returns `{"error": "source table not found"}` and creates no rule

#### Scenario: create_rule rejects a missing column
- **WHEN** `create_rule` is called with a `text_column` not present in the source table
- **THEN** the server returns `{"error": "text_column not found in source table"}` and creates no rule

#### Scenario: update_rule changes only provided fields
- **WHEN** `update_rule` is called with `name` and `max_chars=8000`
- **THEN** only `max_chars` (and `updated_at`) change; other fields are preserved

### Requirement: run_rule is incremental and idempotent
The server SHALL expose a `run_rule(name, batch?)` tool. It SHALL read source rows with `rowid > rule.last_rowid` ordered by `rowid`, limited to `batch` (default 500), run `extract_text` on each row's `text_column` against the rule's `schema_json` using the rule's `model`, upsert each result into `process_results` on `(rule_id, source_table, source_rowid)`, then advance `rule.last_rowid` to the max `rowid` processed. The result SHALL include `processed`, `failed`, `next_rowid`, and `up_to_date` (true when no rows remained).

#### Scenario: first run processes all rows
- **WHEN** `run_rule` is called on a rule whose `last_rowid=0` against a source table with 10 rows
- **THEN** all 10 rows are processed, `process_results` holds 10 rows, and `last_rowid` advances to the source table's max rowid

#### Scenario: second run processes only new rows
- **WHEN** 5 new rows have been appended since the last run and `run_rule` is called again
- **THEN** only 5 rows are processed and `next_rowid` reflects the new max

#### Scenario: re-run after a mid-batch failure does not duplicate
- **WHEN** `run_rule` is re-run over rows already present in `process_results`
- **THEN** the unique constraint upserts (no duplicate `process_results` rows) and `last_rowid` advances

#### Scenario: no new rows returns up_to_date
- **WHEN** `run_rule` is called and `last_rowid` already equals the source table's max rowid
- **THEN** the result has `processed=0` and `up_to_date=true`

### Requirement: SQL-injection guard on dynamic identifiers
Because `source_table` and `text_column` are interpolated into SQL (they cannot be bind parameters), the server SHALL validate each against `^[A-Za-z_][A-Za-z0-9_]*$` and confirm existence in `sqlite_master` / `PRAGMA table_info` before executing any source-table query. A failing check SHALL return an error and execute no SQL against the source table.

#### Scenario: invalid table name is rejected
- **WHEN** a rule's `source_table` is `scraw_x; DROP TABLE sources;--`
- **THEN** `run_rule` returns `{"error": "invalid source_table identifier"}` and executes no SQL

### Requirement: Cron-driven execution via CLI branch
The server SHALL support a `--run-rule <name>` CLI argument. When present, the server SHALL run `run_rule(<name>)` in-process, print a JSON summary to stdout, and exit with code 0 on success or non-zero on failure — without starting the MCP stdio server. A `cron-mcp` `Task.command` of the form `uv run --directory mcp/process-mcp python server.py --run-rule <name>` SHALL execute the rule on schedule.

#### Scenario: CLI branch runs a rule and exits
- **WHEN** `server.py --run-rule sentiment_news` is invoked from a shell
- **THEN** the rule runs, a JSON summary is printed, and the process exits without starting the stdio server

#### Scenario: cron task command drives the rule
- **WHEN** a cron-mcp `Task` has `command="uv run --directory mcp/process-mcp python server.py --run-rule sentiment_news"` and a `Schedule` references it
- **THEN** on the schedule, cron-mcp's subprocess runner executes the command and records an `Execution`

### Requirement: daas integration is traceability only
A processing rule MAY carry a `datasource` name (daas `sources.name`) for traceability. The LLM extraction path (`create_rule`, `update_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`) SHALL NOT read from or write to any daas registry table (`sources`, `daas_functions`, `observations`, `datasource_*`). The source-of-truth for which table to read is `process_rules.source_table`; the daas `sources.config.scraw_config` slug is what makes the rule and the datasource point at the same scraped data. The indicator path (`create_indicator`, `update_indicator`, `run_indicator`, `calculate`) is exempt from this constraint and SHALL write computed indicators to `observations` as specified by the `process-mcp-indicators` capability.

#### Scenario: daas tables are untouched by run_rule
- **WHEN** `run_rule` processes a rule whose `datasource="news_finance"`
- **THEN** no `sources`, `daas_functions`, or `observations` row is created or modified

#### Scenario: process_results is queryable via dashboard-mcp
- **WHEN** a caller runs `dashboard-mcp.query_table(database="daas", table="process_results")`
- **THEN** the extracted records are returned as rows

#### Scenario: indicator path is exempt and writes observations
- **WHEN** `run_indicator` runs an indicator rule
- **THEN** `observations` rows MAY be created by the indicator path, and this does not violate the LLM extraction path's traceability-only guarantee
