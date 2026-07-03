## Why

Chinese listed-company annual reports are long PDF/HTML documents whose value lives behind a structured 目录 (outline) — 财务报表、附注、管理层讨论. There is no MCP in this repo that turns that outline into queryable data: extracting a specific section, cleaning/structuring it with an LLM, persisting it to a search index, and searching it back. Today an agent would have to glue scrapling + an LLM call + an ES client by hand for every report. This change adds one MCP that does the full loop so any agent can pull a section, AI-extract fields, store to Elasticsearch, and search — through a uniform tool surface.

## What Changes

- New MCP server `mcp/cnreport-mcp/` (FastMCP, stdio) following the existing `mcp/*` conventions (root `.env` first, `mcp/models` schema, `mcp/daas.db`, registered in `.mcp.json`).
- **Outline extraction** tools: given a report source (URL or local path) and a section/outline selector, fetch the document (via the existing `scrapling-*-mcp` fetchers) and return the section content under a chosen outline node.
- **AI data processing** tools: pass extracted section text + an extraction schema/prompt to an LLM (Claude API via the `claude-api` reference) and return structured records (e.g. financial line-items, tables). Provider configured by env, no provider hard-coded.
- **Elasticsearch persistence** tools: index extracted/processed records into an ES index with a defined mapping; bulk-index support.
- **Elasticsearch search** tools: full-text and structured query against indexed report content, return hits with source + highlights.
- Shared SQLAlchemy tables in `mcp/models/` to track extraction jobs, indexed documents, and ES index metadata (mirrors the existing registry/observation pattern).
- Self-check script + a `ponytail:`-minimal unit test for the non-live logic (parsing selectors, mapping records → ES docs).

## Capabilities

### New Capabilities
- `report-outline-extraction`: fetch a Chinese annual report and extract section content by outline/目录 selector, with outline listing.
- `report-ai-processing`: run LLM-driven structured extraction over report section text given a schema/prompt.
- `report-elasticsearch-store`: index processed report records into Elasticsearch with a defined mapping; bulk and single-doc.
- `report-elasticsearch-search`: full-text and filtered search over indexed report content with highlights.

### Modified Capabilities
<!-- None — this is a new MCP. -->

## Impact

- **New code**: `mcp/cnreport-mcp/` (`server.py`, `cnreport_tools.py`, `outline.py`, `ai_extract.py`, `es_store.py`, `es_search.py`, `migrate.py`, `selfcheck.py`).
- **Schema**: new tables added to `mcp/models/` (`ReportDocument`, `ReportSection`, `EsIndexMeta`) — one `Base`, no changes to existing tables.
- **Dependencies**: `elasticsearch>=8.x` (new), `fastmcp`, `sqlalchemy`, `httpx`, `pypdf`, `jsonschema`; fetching via `httpx`/`pypdf` directly (scrapling deferred). LLM via the repo's existing OpenAI-compatible endpoint (`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`) — no new SDK, no new LLM credentials.
- **Env**: `.env` gains `ES_URL`, `ES_API_KEY` (+ `ES_USERNAME`/`ES_PASSWORD` fallback); reuses existing `LLM_*` keys.
- **Config**: registered in `.mcp.json` via `uv run --directory mcp/cnreport-mcp python server.py`.
- **No breaking changes** to existing MCPs; the new server is additive.
