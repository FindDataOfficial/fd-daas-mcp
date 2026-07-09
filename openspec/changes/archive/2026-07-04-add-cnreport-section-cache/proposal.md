## Why

`cnreport-mcp` has two gaps the user hits in practice. (1) **No cache** — `fetch_source` does a fresh `httpx.get` of the annual-report PDF on *every* call to `list_outline` / `extract_section` / `get_section` / `get_special_report`, so re-extracting a second section from the same report re-downloads the (often multi-MB) PDF and re-parses it through `pypdf` each time, then feeds it to the LLM again. (2) **No way to pull the 三大报表 as text from the report PDF** — `get_financials` returns akshare's structured numeric tables, not the actual `合并利润表` / `合并资产负债表` / `合并现金流量表` sections as they appear in the annual report. The outline pipeline (`parse_outline` → `resolve_selector` → `extract_section_text`) already returns section text and never the PDF bytes, so both gaps are closeable by building on it: a disk cache in front of `fetch_source`, and a convenience tool that resolves the three statement titles in one call.

## What Changes

- **Local report cache** (new). `fetch_source` becomes cache-aware: before downloading, it checks a configurable on-disk cache (`CNREPORT_CACHE_DIR`, default `mcp/cnreport-mcp/.cache/reports/`). On a hit it returns the cached extracted text (and reuses the cached PDF); on a miss it downloads, extracts text via `pypdf`, and stores both the `.pdf` and a `.txt` companion (plus a `.outline.json` snapshot) under a stable, human-browseable filename `{stock_code}_{year}_{form}_{announcement_id}`. Cache is keyed for the convenience tools that have provenance (`get_section` / `get_special_report` / the new statements tool) and falls back to a URL hash for raw `extract_section(source=URL)` calls. Local-path sources are never cached. No TTL — CNINFO annual reports are immutable once published.
- **`get_financial_statements` tool** (new). `get_financial_statements(ticker_or_name, year, form="年度报告")` resolves the company → filing → cached PDF, parses the TOC, locates the three major statement sections (preferring the consolidated `合并利润表` / `合并资产负债表` / `合并现金流量表`, falling back to the un-prefixed titles), and returns each one's body text + outline entry + char_count. Returns text only — never PDF bytes. Statements not found in the TOC are listed in a `missing` array with the available titles so the caller can fall back to a regex selector.
- **Cache management tools** (new, optional). `list_cache` lists cached reports (stock/year/form/announcement_id/cached_at/size); `clear_cache(stock_code?, year?)` evicts (all, by company, or by company+year).
- **No DB schema changes** — provenance already lives in `ReportDocument` / `ReportSection`; the cache is purely on-disk files. **No new dependencies** — `httpx` + `pypdf` already in use.

## Capabilities

### New Capabilities
- `cnreport-report-cache`: on-disk cache of downloaded annual reports (PDF + extracted text + outline) keyed by stock/year/form/announcement_id (URL-hash fallback), with cache-first lookup, store-on-miss, and list/clear management tools. Transparent to callers — same inputs/outputs, faster on repeats.
- `cnreport-financial-statements`: `get_financial_statements(ticker, year, form)` extracts the three major financial-statement sections (三大报表) as text from the annual report PDF via the existing outline pipeline, preferring consolidated (`合并`) titles, reporting any not found.

### Modified Capabilities
- `report-outline-extraction`: the fetch step that backs `list_outline`, `extract_section`, and the convenience wrappers now consults the report cache before downloading and stores the result on a miss (previously: unconditional `httpx.get` + `pypdf` parse on every call).

## Impact

- **New files**: `mcp/cnreport-mcp/report_cache.py` (cache module: key derivation, hit/miss, store, list, clear), `mcp/cnreport-mcp/selfcheck_cache.py` (temp cache dir; no network — hit/miss/store round-trip + three-statements matcher against a fixture PDF).
- **Modified files**: `mcp/cnreport-mcp/cnreport_tools.py` (`fetch_source` → cache-aware; new `get_financial_statements` + statement-title matchers), `mcp/cnreport-mcp/server.py` (register `get_financial_statements`, `list_cache`, `clear_cache`), `mcp/cnreport-mcp/.env.example` (`CNREPORT_CACHE_DIR`), `mcp/cnreport-mcp/README.md`, `CLAUDE.md` (document the cache + new tool), `mcp/cnreport-mcp/selfcheck.py` (extend with a cache-hit assertion).
- **APIs**: three new MCP tools (`get_financial_statements`, `list_cache`, `clear_cache`); `fetch_source` signature unchanged (cache is internal).
- **No DB migrations**, no new Python deps, no changes to other MCPs. The cache directory should be `.gitignore`d (`mcp/cnreport-mcp/.cache/`).
