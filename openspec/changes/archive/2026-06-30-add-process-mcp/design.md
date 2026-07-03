## Context

Three fleet facts drive this design:

1. **cron-mcp runs `Task.command` as a shell subprocess** (`agent_runner._run_db_task` → `subprocess.run(..., shell=True, timeout=...)`). The `agent`/`prompt` schedule fields are MVP-logged only. So cron drives process-mcp through a CLI entrypoint, not an MCP tool call.
2. **`scraw_configs` holds scraping *config*** (url, name-slug, columns_json); scraped *data rows* are not a fixed schema table. The user persists them in a dynamically-created table, so process-mcp needs a discovery rule to find that source data.
3. **`mcp/models/models.py` is the single schema source of truth** — process-mcp's persisted tables go there, created via `Base.metadata.create_all`, matching how `cnreport-mcp`/`daas-mcp` add tables.

`cnreport-mcp.ai_extract` / `cnreport_tools.call_llm_json` is the proven extraction shape: a 15-line `httpx.post` to an OpenAI-compatible `/chat/completions` with `response_format:{type:"json_object"}`, one retry, `jsonschema` validation. process-mcp generalizes it (multi-model, long-text chunked, vision) and adds the persistence + cron layer.

## Goals / Non-Goals

**Goals:**
- Env-driven multi-model registry (`PROCESS_MODELS` JSON, single-model fallback) covering text and vision models.
- Long-text extraction that does **not** truncate: chunked map-reduce when input exceeds `max_chars`.
- Image extraction via a vision model (path / HTTP URL / base64).
- **Persisted rules** in the shared schema: a rule binds a source table + text column + JSON Schema + model, and can be replayed.
- **Incremental `run_rule`**: read new source rows (rowid cursor), extract, upsert into a shared `process_results` table, advance cursor. Idempotent re-runs.
- **Cron-driven**: a `--run-rule <name>` CLI branch that cron-mcp's subprocess task invokes.
- **Source-data discovery**: a naming rule (`scraw_<slug>`) + a `list_source_tables()` introspection tool.
- Caller-supplied JSON Schema validation with one retry. No new SDK (`httpx` only).

**Non-Goals:**
- Not a registry/harness MCP; no function catalog, no `daas_functions` rows.
- No streaming, no async/batch APIs, no embeddings.
- No OCR fallback — a non-vision model + image is an error, not a route to OCR.
- process-mcp does **not** create the `scraw_<slug>` source tables — the scrape skills/scrapling do. process-mcp only reads them.
- No per-rule output tables — one shared `process_results` table (lazy; upgrade path noted below).
- No re-implementation of cnreport's PDF-outline pipeline.

## Decisions

**D1 — No SDK; OpenAI-compatible `httpx.post`.** Reuse `cnreport_tools.call_llm_json`'s shape. *Alternative:* the `openai` SDK — rejected (pins one provider family; every target endpoint already speaks the OpenAI-compatible API).

**D2 — Model registry as one env var `PROCESS_MODELS` (JSON).** name → `{model, vision?, base_url?, api_key?}`; per-model overrides win, shared `LLM_*` is the fallback. Tools take an optional `model` name (default: first entry, or legacy `LLM_MODEL`). *Alternatives:* a `LLM_TEXT_MODEL`/`LLM_VISION_MODEL` pair (caps at two, no per-model keys) — rejected; a `models.yaml` (another file to load; env is the fleet's config surface) — rejected.

**D3 — Long text: chunked map-reduce.** `len(text) <= max_chars` → one call; else paragraph-boundary chunks, extract each, then a merge pass dedups/consolidates per-chunk arrays. *Alternative:* truncate (cnreport today) — that is the bug being fixed. Result carries `chunk_count` and `merge_notes`.

**D4 — Images: OpenAI vision message content.** User message `content` is `[{type:text}, {type:image_url, image_url:{url}}]`; `url` is an HTTP(S) URL passed through or a `data:image/...;base64,...` built from a local path / raw base64.

**D5 — JSON discipline + one retry.** Parse output as JSON; if the endpoint rejects `response_format`, retry without it and strip a ```` ```json ```` fence. Validate records against the caller's schema via `jsonschema`; on failure, retry once with a correction preamble. Mirrors `cnreport.ai_extract._attempt`.

**D6 — `extract_file` is a thin reader** (`.txt`/`.md` UTF-8; `.pdf` via `pypdf` page text) that forwards to `extract_text`. One extraction code path.

**D7 — Two shared-schema tables.** Added to `mcp/models/models.py`:
- `ProcessRule` (`process_rules`): `id, name(unique), source_table, text_column, schema_json(JSON), prompt(Text), model, max_chars(default 12000), enabled(default 1), last_rowid(default 0), created_at, updated_at`.
- `ProcessResult` (`process_results`): `id, rule_id(FK→process_rules.id CASCADE), source_table(index), source_rowid(index), extracted_json(JSON), model, run_at`, `UniqueConstraint(rule_id, source_table, source_rowid)` for idempotent upsert.
*Alternative:* per-rule output tables — rejected for now (one shared table is lazier and queryable via `dashboard-mcp.query_table`); `# ponytail: shared results table, add per-rule output table when a rule needs its own shape`.

**D8 — Source-data naming rule: `scraw_<slug>`.** Scraped data tables are named `scraw_<slug>` where `<slug>` == `scraw_configs.name` == `sources.config.scraw_config`. `list_source_tables()` introspects `sqlite_master` for `name LIKE 'scraw_%'` and returns each with row count + columns (via `PRAGMA table_info`). A rule stores the literal `source_table` name. This is the "rule to help you find which is the source data."

**D9 — `run_rule` is incremental and idempotent.** `SELECT rowid, <text_column> FROM <source_table> WHERE rowid > :last_rowid ORDER BY rowid LIMIT :batch` → extract each → upsert into `process_results` on `(rule_id, source_table, source_rowid)` → set `rule.last_rowid = max(rowid)`. Re-running after a failure reprocesses only the un-cursored tail; already-written rows are upserted (no duplicates). `LIMIT :batch` (default 500) bounds one cron tick.

**D10 — SQL-injection guard at the trust boundary.** `source_table` and `text_column` are user-provided and interpolated into SQL (dynamic table/column — can't be a bind parameter). Before any query: validate both against `^[A-Za-z_][A-Za-z0-9_]*$`, confirm the table exists in `sqlite_master`, and confirm the column exists in `PRAGMA table_info(<table>)`. Reject otherwise. This is the one place ponytail never simplifies away.

**D11 — Cron CLI branch in `server.py`.** At the bottom: `if "--run-rule" in sys.argv:` → parse the rule name, call the `run_rule` logic in-process, print a JSON summary, `sys.exit(0)`; else `app.run(transport="stdio")`. One file, no separate CLI binary. cron's `Task.command` = `uv run --directory mcp/process-mcp python server.py --run-rule <name>`.

**D12 — daas link is traceability, not coupling.** A rule optionally stores a `datasource` name (daas `sources.name`). process-mcp does not read or write daas registry tables; the link lets a human/agent see "rule X processes datasource Y." The source-of-truth for *which table to read* is `source_table`; the daas `sources.config.scraw_config` slug is what makes the two point at the same scraped data.

**D13 — Tool surface (11):** `list_models`, `list_source_tables`, `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`.

## Risks / Trade-offs

- **[Dynamic table/column in SQL → injection]** → D10 guard: strict identifier regex + existence check in `sqlite_master`/`PRAGMA table_info` before any query. Identifiers can't be bind parameters, so validation is mandatory, not optional.
- **[Long-text merge drops/duplicates records at chunk boundaries]** → merge-pass prompt is told the schema and asked to dedup; result carries `chunk_count` + `merge_notes`. `# ponytail: heuristic merge, caller re-checks when a key is absent`.
- **[Some endpoints reject `response_format`]** → catch and retry without it, then strip ```` ```json ```` fence; if both fail, return raw content under `raw`.
- **[Vision support varies]** → `list_models` surfaces a `vision` flag; `extract_image` refuses with a clear error if the chosen model's `vision` is false/unset.
- **[Cost: chunked extraction = N+1 calls]** → single-call path when input fits; `extract_text` returns `chunk_count`; `run_rule` is incremental (only new rows) and batch-capped.
- **[Large images blow the context window]** → cap encoded size at `max_image_bytes` (default 5 MB); error with guidance if exceeded. `# ponytail: hard cap, add resize when callers hit it`.
- **[Cron tick interrupted mid-rule]** → `last_rowid` advances only after the batch is written; a crash mid-batch reprocesses that batch next run (idempotent upsert → no dupes, just wasted calls). Acceptable.
- **[Per-model `api_key` in `PROCESS_MODELS` JSON is another secret in env]** → documented in `.env.example` as optional; shared `LLM_API_KEY` covers the common case.

## Migration Plan

Additive. 1) Add `ProcessRule`/`ProcessResult` to `mcp/models/models.py`. 2) Ship `mcp/process-mcp/`. 3) `Base.metadata.create_all` creates the two new tables in `mcp/daas.db` on first run (no migration of existing tables). 4) Register in `.mcp.json`, document in `CLAUDE.md`. 5) To wire a cron job: `create_task(name="proc_sentiment", command="uv run --directory mcp/process-mcp python server.py --run-rule sentiment_news")` then `create_schedule(name=..., cron_expr=..., task="proc_sentiment")`. Rollback = delete the directory + `.mcp.json` entry + `CLAUDE.md` subsection + drop the two tables.

## Open Questions

None blocking. Defaults (`max_chars=12000`, `max_image_bytes=5MB`, `batch=500`, prefix `scraw_`) are tunable via tool args / the naming rule without code change.
