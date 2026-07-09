## 1. Report cache module

- [x] 1.1 Create `mcp/cnreport-mcp/report_cache.py` with `cache_dir()` — reads `CNREPORT_CACHE_DIR` (default `mcp/cnreport-mcp/.cache/reports/`), creates the directory on first miss
- [x] 1.2 Implement `cache_key(source, stock_code, year, form, announcement_id)` → returns a filename stem or `None`: `{stock_code}_{year}_{form}_{announcement_id}` when provenance is present, `url_{sha1(url)[:16]}` for URL sources without provenance, `None` for local-path sources (never cached)
- [x] 1.3 Implement `get_or_fetch(source, fetcher="uv", *, stock_code=None, year=None, form=None, announcement_id=None) -> (text, cache_info)` — on hit returns the cached `.txt` with `cached=True`; on miss calls `cnreport_tools.fetch_source_with_bytes`, writes `.pdf` + `.txt` + `.outline.json` atomically (write-temp + rename), returns `cached=False`; local-path sources pass straight to `fetch_source` with no cache write
- [x] 1.4 Implement `list_cache()` (walk dir, parse stems back into `stock_code/year/form/announcement_id`, return `cached_at` from mtime + `size` from file sizes) and `clear_cache(stock_code=None, year=None)` (delete matching files, return count removed)

## 2. Wire the cache into fetch paths

- [x] 2.1 Refactor `get_section` in `cnreport_tools.py` to call `report_cache.get_or_fetch(pdf, stock_code=…, year=…, form=…, announcement_id=…)` instead of bare `fetch_source`
- [x] 2.2 Refactor `get_special_report` (section branch) to call `report_cache.get_or_fetch` with provenance from the top filing
- [x] 2.3 Update `list_outline` and `extract_section` in `server.py` to call `report_cache.get_or_fetch(source, …)` (URL-hash key, local-path pass-through) so the cache applies everywhere

## 3. Three-statements tool

- [x] 3.1 Add `STATEMENT_MATCHERS` to `cnreport_tools.py` — `{"income_statement": ["合并利润表","利润表"], "balance_sheet": ["合并资产负债表","资产负债表"], "cashflow": ["合并现金流量表","现金流量表"]}` — and `resolve_statement(outline, key)` returning the first outline entry whose title matches (consolidated tried before un-prefixed)
- [x] 3.2 Implement `get_financial_statements(ticker_or_name, year, form="年度报告")` — resolve company → filing → `get_or_fetch` → `parse_outline` → for each statement `resolve_statement` + `extract_section_text`; collect `missing` + `available` for any not found; return `{stock_code, company_name, year, form, pdf_url, cached, statements:{…}, missing:[…], available:[…]}` per the design
- [x] 3.3 Wrap `get_financial_statements` with `@_tool_safe`; confirm company-not-found and filing-not-found return `{error: …}` without a network call

## 4. Cache management tools

- [x] 4.1 Add `list_cache` and `clear_cache` `@app.tool` wrappers in `server.py` delegating to `report_cache`; document args/return in docstrings

## 5. Server registration, env, gitignore

- [x] 5.1 Register `get_financial_statements`, `list_cache`, `clear_cache` in `server.py` (verify they appear in `app`'s tool list)
- [x] 5.2 Add a commented `CNREPORT_CACHE_DIR=` line to `mcp/cnreport-mcp/.env.example`
- [x] 5.3 Add `mcp/cnreport-mcp/.cache/` to `.gitignore`

## 6. Self-checks

- [x] 6.1 Create `mcp/cnreport-mcp/selfcheck_cache.py` — temp `CNREPORT_CACHE_DIR`, a stub URL fixture (monkeypatch `fetch_source_with_bytes` to avoid network), assert: miss → download + store (`cached=False`), second call → hit + no re-download (`cached=True`), `list_cache` shape, `clear_cache` count
- [x] 6.2 Add a three-statements matcher assertion in the selfcheck using fixture outlines: (a) all three `合并`-prefixed found, (b) un-prefixed fallback found, (c) one missing → `missing`/`available` populated
- [x] 6.3 Extend `mcp/cnreport-mcp/selfcheck.py` with a cache-hit assertion (updated the `get_section`/`get_special_report` stubs to patch `fetch_source_with_bytes` + a miss→hit call-count assertion)
- [x] 6.4 Run `uv run --directory mcp/cnreport-mcp python selfcheck_cache.py` and the existing `selfcheck.py` green

## 7. Docs & validation

- [x] 7.1 Update `mcp/cnreport-mcp/README.md` — cache behavior + `CNREPORT_CACHE_DIR`, the new `get_financial_statements` / `list_cache` / `clear_cache` tools, and the `missing`/`available` escape hatch
- [x] 7.2 Update `CLAUDE.md` `mcp/cnreport-mcp/` section — note the cache, the three new tools, and the `selfcheck_cache.py` command
- [x] 7.3 Run `openspec validate add-cnreport-section-cache --strict` green
