## Context

This repo already hosts ~12 FastMCP servers under `mcp/` that share one `.env`, one SQLAlchemy `Base` (`mcp/models/`), and one SQLite DB (`mcp/daas.db`). Two fetching MCPs (`scrapling-uv-mcp`, `scrapling-docker-mcp`) already exist for hostile web/PDF retrieval. What is missing is a vertical for **Chinese listed-company annual reports**: pull a report by outline node, run LLM extraction on the section, persist to Elasticsearch, and search it back. The new server slots into the existing conventions rather than introducing a new pattern.

Annual reports on cninfo/sse/hkex are large (often 200+ page PDFs or paginated HTML). The 目录 (outline) is the only sane entry point — agents want "第三节 管理层讨论与分析" or "合并资产负债表", not a raw dump.

## Goals / Non-Goals

**Goals:**
- One MCP, `mcp/cnreport-mcp/`, exposing outline listing, section extraction, AI structured extraction, ES indexing, and ES search as FastMCP tools.
- Reuse `scrapling-*-mcp` for fetching — do not write a new fetcher.
- LLM provider configured by env (`ANTHROPIC_API_KEY` + `CNREPORT_LLM_MODEL`); no provider hard-coded in tool logic.
- New tables share the existing `Base` in `mcp/models/`; no new DB file.
- Follows root `.env` first, per-MCP `.env` override pattern; registered in `.mcp.json`.

**Non-Goals:**
- Not a general-purpose PDF parser — only annual-report-shaped documents.
- Not building a UI; the dashboard integration is out of scope (dashboard can read `daas.db` tables directly later).
- No OCR of scanned-only PDFs in v1 (text-layer reports only; scanned reports return a clear error).
- No vector/semantic search in v1 — Elasticsearch full-text + structured filters only. (kNN is a later addition.)
- Not re-indexing or migrating existing MCP data into ES.

## Decisions

**1. FastMCP stdio server, same layout as `akshare-mcp` / `yfinance-mcp`.**
Tools registered on a `FastMCP` instance; `server.py` loads root `.env` then local `.env` with `override=True`; `sys.path` inserts `mcp/models`. Alternatives: HTTP transport (rejected — inconsistent with siblings), combining into `daas-mcp` (rejected — different domain, would bloat it).

**2. Fetching uses httpx + pypdf directly, not the scrapling MCPs.**
`fetch_source` accepts a `fetcher` arg for forward-compatibility but v1 fetches URLs with `httpx` (text/HTML → tag-stripped text) and extracts text-layer PDFs with `pypdf`; local paths are read directly. Rationale: invoking `scrapling-*-mcp` would mean spawning a subprocess MCP client per fetch — heavy and fragile for a tool call; httpx is already a dependency and handles static cninfo/sse downloads. `ponytail:` scrapling delegation deferred; switch to it if a report needs JS/anti-bot rendering. Alternative: shell out to scrapling (rejected — subprocess-per-fetch overhead), import scrapling library directly (rejected — would add a heavy dep for the common static case).

**3. Outline modeled as a flat list of `(level, title, anchor)` tuples.**
`list_outline` returns sections parsed from the report's 目录 page or PDF bookmarks. `extract_section` takes a selector — either an exact title, a regex, or an ordinal index — and returns the body text between that node and the next sibling. Rationale: annual reports have irregular nesting; a flat list with levels is robust and easy for an LLM agent to target. Alternative: a tree (rejected — over-modeled for v1; `ponytail:` flat list, tree if agents need child navigation).

**4. AI extraction calls the repo's existing OpenAI-compatible LLM endpoint via httpx + jsonschema validation.**
`ai_extract` takes `text` + `schema` (JSON Schema) + optional `prompt`, calls `{LLM_BASE_URL}/chat/completions` with `LLM_API_KEY`/`LLM_MODEL` (the shared root `.env` keys already used by `trading-mcp`), requests `response_format={"type":"json_object"}` with a schema-enforcing system prompt, then validates the returned JSON against the supplied schema with `jsonschema`. Rationale: reuses already-configured credentials and the established repo convention; no new SDK, no new env keys for the user to provision. Alternatives: Anthropic SDK (rejected — repo has no Anthropic creds configured; would force the user to set up a new provider), crewai (rejected — heavy dependency for a single extraction call), free-text + regex parse (rejected — fragile).

**5. Elasticsearch mapping fixed per record type, index name per report-year.**
Index pattern `cnreport-{year}`. Document `_id` = `{report_id}:{section_id}:{record_seq}`. Mapping: `report_id` keyword, `company` keyword, `year` integer, `section` keyword, `text` text with ik_smart analyzer (fallback to standard if ik not installed), `fields` object (dynamic, for AI-extracted structured fields). Rationale: per-year indices are cheap to drop/reindex; ik_smart is the standard for Chinese full-text but we degrade gracefully. Alternative: one fat index with alias (deferred — `ponytail:` per-year is simpler, add alias when reindex-without-downtime matters).

**6. Schema additions to `mcp/models/`: three tables, no edits to existing tables.**
`ReportDocument` (report_id, source, company, stock_code, year, fetched_at, raw_path), `ReportSection` (section_id, report_id FK, ordinal, level, title, char_count), `EsIndexMeta` (index_name, doc_count, created_at, mapping_hash). Rationale: tracks provenance so a re-extract or re-index is idempotent; mirrors the existing `functions`/`observations` provenance style.

**7. Self-check + one unit test, no live calls.**
`selfcheck.py` runs against a temp DB (like `combine-mcp`); the unit test covers selector parsing and the record→ES-doc mapping (pure functions). Live ES/LLM/scrapling calls are gated behind env and skipped in CI. Rationale: matches repo convention; `ponytail:` no framework sprawl.

## Risks / Trade-offs

- **ik analyzer not installed on target ES** → mapping creation falls back to `standard` analyzer; logged via `EsIndexMeta.mapping_hash`. Chinese search recall drops but does not fail.
- **Annual report formats vary wildly across exchanges** → outline parser may miss sections on some reports. Mitigation: `extract_section` accepts raw text fallback; agent can pass a regex selector; record failures in `ReportSection` with `parse_status`.
- **LLM extraction cost/latency** → large sections blow context. Mitigation: `ai_extract` truncates to a configurable `max_chars` (default 12000) and reports truncation in the result; agent can chunk by sub-section.
- **LLM endpoint misconfigured / no key** → `ai_extract` returns a clear error before any network call; the shared `LLM_API_KEY`/`LLM_MODEL` keys (already in root `.env`) are reused so no extra provisioning is needed.
- **Elasticsearch not running** → all ES tools return a clear connection error rather than crashing the MCP. Persistence/extraction still work without ES.
- **httpx can't render JS-only report pages** → v1 targets static HTML/PDF downloads (the common case for annual reports on cninfo/sse). `ponytail:` scrapling delegation deferred for JS/anti-bot pages.

## Migration Plan

- Additive only — no existing data moved. New tables created by `migrate.py` against `mcp/daas.db` on first run.
- Rollback: delete `mcp/cnreport-mcp/`, remove the `.mcp.json` entry, drop the three new tables. No other MCP references them.
- ES indices (`cnreport-{year}`) are disposable; drop via the search tool's `delete_index` if needed.

## Open Questions

- Should `ai_extract` support batch (multiple sections in one call) in v1, or keep single-section? Propose single-section for v1; batch later.
- ES auth: API key vs basic auth — propose API key (`ES_API_KEY`), with `ES_USERNAME`/`ES_PASSWORD` fallback.
- When (if ever) to wire `scrapling-*-mcp` for JS-rendered report pages — deferred out of v1.
