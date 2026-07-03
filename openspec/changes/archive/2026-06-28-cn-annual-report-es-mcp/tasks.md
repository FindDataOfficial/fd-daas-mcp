## 1. Scaffold & schema

- [x] 1.1 Create `mcp/cnreport-mcp/` dir with `server.py`, `cnreport_tools.py`, `.env.example`, `pyproject.toml` mirroring `mcp/akshare-mcp` layout
- [x] 1.2 Add `ReportDocument`, `ReportSection`, `EsIndexMeta` tables to `mcp/models/` (shared `Base`, no edits to existing tables)
- [x] 1.3 Write `migrate.py` to create the three tables in `mcp/daas.db`; verify against a temp DB
- [x] 1.4 Register the server in `.mcp.json` via `uv run --directory mcp/cnreport-mcp python server.py`
- [x] 1.5 Add deps to `mcp/cnreport-mcp/pyproject.toml`: `elasticsearch>=8`, `fastmcp`, `sqlalchemy`, `python-dotenv`, `httpx`, `pypdf`, `jsonschema`, `mcp-models`; `uv sync`

## 2. Outline extraction

- [x] 2.1 Implement `fetch_source(source, fetcher)` — URL via httpx (text/html tag-strip), PDF via pypdf, local path direct read; returns text
- [x] 2.2 Implement `parse_outline(text)` → flat list of `{level, title, ordinal}` from 目录/bookmarks
- [x] 2.3 Implement `list_outline` tool (URL or local path → outline entries)
- [x] 2.4 Implement `extract_section(source, selector)` — selector is exact title | regex | ordinal; returns body text to next sibling; errors with available titles on no match
- [x] 2.5 Persist `ReportDocument` + `ReportSection` rows; idempotent on re-extract (upsert by report_id+section_id)

## 3. AI processing

- [x] 3.1 Implement `ai_extract(text, schema, prompt=None, max_chars=12000)` — OpenAI-compatible Chat Completions via httpx (`response_format=json_object`), validate output with `jsonschema`
- [x] 3.2 Retry once with corrective prompt on schema violation, then error
- [x] 3.3 Truncate to `max_chars`, return `truncated: true` in result
- [x] 3.4 Guard on missing `LLM_API_KEY` — error before any network call
- [x] 3.5 Config: reuse shared `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` from root `.env`

## 4. Elasticsearch store

- [x] 4.1 Implement ES client builder from `ES_URL`/`ES_API_KEY` (fallback `ES_USERNAME`/`ES_PASSWORD`); lazy, connection errors returned not raised
- [x] 4.2 Define `cnreport` mapping (ik_smart analyzer with standard fallback); create index on first use
- [x] 4.3 Implement `index_records(records, year)` — bulk index, `_id`=`{report_id}:{section_id}:{seq}`, idempotent upsert
- [x] 4.4 Return succeeded/failed counts; upsert `EsIndexMeta` (index_name, doc_count, mapping_hash)
- [x] 4.5 Graceful degradation: ES unreachable → descriptive error, server stays up

## 5. Elasticsearch search

- [x] 5.1 Implement `search_reports(query, year=None, company=None, stock_code=None, section=None, from_=0, size=25)` with highlights + total
- [x] 5.2 Cap `size` at 50 (configurable); enforce pagination via `from`/`size`
- [x] 5.3 Implement `delete_index(year, confirm=False)` — drops `cnreport-{year}` + removes `EsIndexMeta` row; errors without `confirm=true`

## 6. Server wiring & env

- [x] 6.1 Register all tools on the FastMCP instance in `server.py`
- [x] 6.2 Load root `.env` first, local `.env` with `override=True`; add `ES_URL`, `ES_API_KEY`, `ES_USERNAME`, `ES_PASSWORD`, `CNREPORT_FETCHER` to `.env.example` (reuses shared `LLM_*` keys)
- [x] 6.3 `sys.path` insert `mcp/models`; `from models import ...`

## 7. Verification

- [x] 7.1 Write `selfcheck.py` against a temp DB (mirror `combine-mcp/selfcheck.py`) — create tables, run migrate, smoke-check pure functions
- [x] 7.2 One `test_cnreport.py` unit test: selector parsing (exact/regex/ordinal) + record→ES-doc mapping; skip live ES/LLM/scrapling when env absent
- [x] 7.3 `uv run python selfcheck.py` passes without touching `mcp/daas.db`
- [x] 7.4 `uv run pytest -v` for the new test passes
