## Context

`cnreport-mcp` extracts sections from Chinese A-share annual-report PDFs via an outline pipeline: `fetch_source(source)` → `parse_outline(text)` → `resolve_selector(outline, selector)` → `extract_section_text(text, outline, entry)`. Three convenience tools (`get_section`, `get_special_report`, and the existing `extract_section`) all flow through `fetch_source`, which today is a bare `httpx.get` + `pypdf` parse — **no cache**. So extracting a second section from the same report re-downloads the (often multi-MB) PDF and re-parses it every call, and any downstream `ai_extract` re-reads the re-fetched text.

The outline pipeline already returns section **text** (never PDF bytes) and already supports exact-title / regex / 1-based-ordinal selectors — so a general "extract a special section by TOC" capability exists. What's missing is (a) a disk cache in front of `fetch_source`, and (b) a convenience tool that resolves the three major financial-statement sections (三大报表) in one call. `get_financials` returns akshare's structured numeric tables, not the report-PDF sections, so it does not satisfy (b).

Constraints: no new Python deps (`httpx`, `pypdf` already in use); no DB schema changes (provenance already in `ReportDocument`/`ReportSection`); the cache must be transparent — existing tool signatures and outputs unchanged except fetch is faster on repeats.

## Goals / Non-Goals

**Goals:**
- A disk cache that stores downloaded annual reports (PDF + extracted text + outline) and is checked before any download.
- A stable, human-browseable cache filename so the user can `ls` the folder and see what's cached.
- A `get_financial_statements(ticker, year, form)` tool returning the 三大报表 section text via the existing outline pipeline, preferring consolidated (`合并`) titles.
- Cache management tools (`list_cache`, `clear_cache`).
- Cache applies to all report-fetching paths (`list_outline`, `extract_section`, `get_section`, `get_special_report`, `get_financial_statements`) without changing their signatures.

**Non-Goals:**
- **LLM-result caching** for `ai_extract` (per-request; different schema/prompt each time — out of scope for v1).
- **Changing the fetcher** (scrapling vs httpx) — the existing spec/code drift around the fetcher is pre-existing and not addressed here.
- **TTL / invalidation** — CNINFO annual reports are immutable once published; no expiry. `clear_cache` covers manual eviction.
- **Fixing `pypdf` text-extraction quality** — pre-existing limitation, unchanged.
- **Deduplicating the `ReportDocument`/`ReportSection` DB rows** — provenance stays as-is; the cache is a separate, file-based concern.

## Decisions

### D1. Cache location & key scheme
`CNREPORT_CACHE_DIR` env, default `mcp/cnreport-mcp/.cache/reports/` (created on first miss; `.gitignore`d). Filename: `{stock_code}_{year}_{form}_{announcement_id}.{ext}` for convenience tools (which carry provenance), and `url_{sha1(url)[:16]}.{ext}` for raw `extract_section(source=URL)` calls. Local-path sources are never cached (already on disk).

- *Alternatives considered:* (a) single content-hash key for everything — rejected because the user explicitly wants a *folder of reports* they can browse by stock/year; the structured filename delivers that. (b) SQLite cache index — rejected as over-engineering; the filesystem already enumerates and `stat`s the files, and `list_cache` just walks the dir.

### D2. What to cache: PDF + `.txt` + `.outline.json`
Store the raw `.pdf` (so the cache is reusable for any future byte-level need), a `.txt` of the extracted text (the expensive `pypdf` parse, cached), and a `.outline.json` snapshot (cheap to re-derive but tiny and convenient for `list_outline`-style calls).

- *Alternatives considered:* cache only the PDF — rejected because `pypdf` re-parse on every hit would still be the slow path; caching the text is the actual win. Cache only the text — rejected because re-downloading is also expensive and the user wants the reports saved.

### D3. Where to hook the cache
A new `report_cache.get_or_fetch(source, *, stock_code=None, year=None, form=None, announcement_id=None, fetcher="uv") -> (text, cache_info)` wraps the existing `fetch_source`. The convenience tools (`get_section`, `get_special_report`, `get_financial_statements`) call `get_or_fetch` with full provenance; `list_outline` and `extract_section` call it with `source` only (URL-hash key, no-op for local paths). `fetch_source` itself stays a pure download+parse primitive (unchanged), so the cache is an additive layer and existing tests keep working.

- *Alternatives considered:* bake caching directly into `fetch_source` — rejected because `fetch_source` is also called with local paths and raw URLs where provenance isn't available, and mixing the cache key derivation in would muddy a clean primitive.

### D4. Three-statements matcher
Curated regex per statement, applied to the flat `parse_outline` title list, first match wins, preferring `合并`:
- income: `r"^合并利润表$|^利润表$"` (try `合并利润表` first, then `利润表`)
- balance: `r"^合并资产负债表$|^资产负债表$"`
- cashflow: `r"^合并现金流量表$|^现金流量表$"`

Implementation tries the consolidated title first across all outline entries, then the un-prefixed title, so a report that lists only `利润表` still resolves. Statements not found are collected into `missing` (with the full `available` title list) and omitted from the returned `statements` object. Reuses `extract_section_text` to slice the body.

- *Alternatives considered:* (a) fuzzy/approximate title matching — rejected for v1; annual reports follow a regulated naming convention, exact + `合并`-prefix covers the vast majority, and the `missing`/`available` escape hatch lets the caller fall back to `get_section` with a custom regex. (b) Match against the body text instead of the TOC — rejected because the TOC is the user-requested entry point and is faster/more reliable than scanning the body.

### D5. Return shape for `get_financial_statements`
```
{
  "stock_code", "company_name", "year", "form", "pdf_url", "cached": bool,
  "statements": {
    "income_statement": {"title", "outline_entry", "char_count", "text"},
    "balance_sheet":    {...},
    "cashflow":         {...},
  },
  "missing": ["cashflow"],            # omitted-from-statements names
  "available": ["第一节 ...", ...],    # full TOC titles, only when missing non-empty
  "error": "..."                       # only on company/filing lookup failure
}
```
Text only — no PDF bytes, no base64. Mirrors the shape of the existing `get_section` response.

### D6. Cache management tools
`list_cache()` walks `CNREPORT_CACHE_DIR`, parses filenames back into `(stock_code, year, form, announcement_id)`, and returns each entry with `cached_at` (file mtime) and `size` (sum of `.pdf`+`.txt`+`.outline.json`). `clear_cache(stock_code=None, year=None)` deletes matching files (all / by company / by company+year) and returns the count removed.

## Risks / Trade-offs

- **[Stale cache if a report is ever republished]** → CNINFO annual reports are immutable post-publication; accept the risk, provide `clear_cache` for manual correction. Document in README.
- **[Unbounded disk growth]** → No automatic eviction (annual reports are large but finite in count per company). `list_cache` surfaces sizes; `clear_cache` evicts. Note the trade-off in README. A future size-based eviction is a Non-Goal for v1.
- **[Cache-key collision for URL-hash fallback]** → `sha1(url)[:16]` collisions are astronomically unlikely for CNINFO's URL space; the provenance-keyed path is the primary path so the URL-hash is only for raw `extract_section`.
- **[Three-statements matcher misses non-standard titles]** → Some reports use `母公司利润表` only, or nest statements under a `财务报告` parent with non-standard sub-headers. The `missing` + `available` response lets the caller fall back to `get_section` with an exact/regex selector. Documented as a known limitation.
- **[Spec/code drift on the fetcher (scrapling vs httpx)]** → Pre-existing; not introduced here and not fixed here. The cache works regardless of fetcher.
- **[Thread-safety of concurrent writes]** → MCP server is single-process stdio; concurrent writes to the same cache key are not a concern in practice. If a key is being written while another process reads, the `.txt` is written atomically (write-to-temp + rename) to avoid partial reads.

## Migration Plan

Additive — no migration required. The cache directory is auto-created on first miss. Existing tools' signatures and outputs are unchanged, so no caller updates. Rollback = delete `mcp/cnreport-mcp/.cache/` and revert the code; no DB to unwind. Add `mcp/cnreport-mcp/.cache/` to `.gitignore`.

## Open Questions

None material. (Deferred: whether to also cache `ai_extract` results by `(text_hash, schema_hash, prompt_hash)` — punted to a future change; the report cache already removes the re-download + re-parse cost the user flagged.)
