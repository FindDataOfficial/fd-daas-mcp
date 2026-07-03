## 1. Category Registry

- [x] 1.1 Create `mcp/cnreport-mcp/cninfo_categories.json` with the grouped shape from design.md — groups: 定期报告, 融资, 业绩, 股权变动, 公司治理, 担保, 其他. Seed 定期报告 with the four existing forms (年度报告→`category_ndbg_szsh`, 半年度报告→`category_bndbg_szsh`, 第一季度报告→`category_yjdbg_szsh`, 第三季度报告→`category_sjdbg_szsh`) plus a curated subset of special types (招股说明书, 增发, 配股, 可转债, 业绩预告, 业绩快报, 股东大会决议, 董事会决议, 收购报告书, 权益变动报告书, 股权激励, 关联交易, 对外担保). Each entry: `{name, code, description}`.
- [x] 1.2 Confirm exact CNINFO `code` values for the curated special types by inspecting CNINFO's SPA request payloads (DevTools network tab on cninfo.com.cn → hisAnnouncement/query). Omit any entry whose code cannot be confirmed rather than guessing; leave a TODO comment in the JSON.

## 2. cninfo_client Changes

- [x] 2.1 Add `load_categories()` to `cninfo_client.py` — reads `cninfo_categories.json` once at import, caches it, returns the `{groups: [...]}` structure. Raises a clear `FileNotFoundError`/`JSONDecodeError` message naming the file if missing/malformed.
- [x] 2.2 Add `resolve_category(category)` — returns the CNINFO code for a Chinese name (registry lookup), passes a raw code through unchanged, returns `None` for unknown input.
- [x] 2.3 Replace `_FORM_CATEGORIES` usage with registry lookups: derive the four-form name→code map from `load_categories()` (so the existing `form` path resolves to identical codes). Keep `_FORM_CATEGORIES` as a module-level dict populated from the registry for backward-compatible internal references, OR replace all call sites — pick one and remove the stale dict.
- [x] 2.4 Add a `category: Optional[str] = None` parameter to `query_announcements(stock_code, org_id, *, form=None, category=None, year=None, limit=20)`. When `category` is given, resolve it via `resolve_category`, set `data["category"] = code`, and skip the post-hoc `form` title filter. When `form` is given (no `category`), keep existing behavior. When neither, list all (unchanged). Raise/return a clear signal if `category` does not resolve.

## 3. cnreport_tools Wrappers

- [x] 3.1 Update `list_filings(ticker_or_name, form=None, category=None, year=None, limit=20)` in `cnreport_tools.py`: enforce mutual exclusion of `form` and `category` (return `{"error": ...}` if both given), resolve `category` via `cninfo_client.resolve_category` (return `{"error": ...}` if unknown, no network call), and pass `category` through to `query_announcements`.
- [x] 3.2 Add `list_report_types(group=None)` wrapper — calls `cninfo_client.load_categories()`, returns all groups or one group's categories, includes `count`. Returns `{"error": ...}` for unknown `group` or load failure. Decorate with `@_tool_safe`.
- [x] 3.3 Add `get_special_report(ticker_or_name, category, year=None, section=None, limit=5)` wrapper — resolve company, resolve `category` (error if unknown, no network), `query_announcements(category=…, year=…, limit=…)`, pick first filing (error if none). If `section` given: `fetch_source(pdf) → parse_outline → resolve_selector → extract_section_text` (reuse, no duplication); return `{stock_code, company_name, category, year, section, pdf_url, outline_entry, text, char_count}` (or `{"error":..., "available":[...], "pdf_url":...}` on no match). If `section` omitted: return `{stock_code, company_name, category, filings:[...], pdf_url}` with no PDF download. Decorate with `@_tool_safe`.

## 4. Server Registration

- [x] 4.1 Register `list_report_types` and `get_special_report` as `@app.tool` in `server.py` with docstrings matching the other company-API tools.
- [x] 4.2 Update the `list_filings` `@app.tool` signature to expose `category` and document the `form`/`category` mutual exclusion in its docstring.
- [x] 4.3 Boot the server (`uv run --directory mcp/cnreport-mcp python server.py`) and confirm via `list_tools` that all 13 tools are registered (6 PDF/AI/ES + 5 company-API + `list_report_types` + `get_special_report`).

## 5. Tests + Fixtures

- [x] 5.1 Add a `test_fixtures/cninfo_hisannouncement_special.json` fixture — a CNINFO `hisAnnouncement` response for a special category (e.g. 招股说明书) so special-report tests run offline.
- [x] 5.2 Add `test_list_report_types_*` tests: all groups returned with `count`; filter by `定期报告` returns the four forms; unknown group returns `error`.
- [x] 5.3 Add `test_list_filings_category_*` tests: filter by Chinese name resolves and calls `hisAnnouncement` with the right `category` code; raw code path identical; unknown category returns `error` with no network call; both `form` and `category` returns `error`.
- [x] 5.4 Add `test_get_special_report_*` tests: by name and by code (mock `fetch_source` for the section path); with `section` returns extracted text; without `section` returns metadata + `pdf_url` and does not call `fetch_source`; unknown category / no filing / unknown company each return `error`.
- [x] 5.5 Add `test_resolve_category` and `test_load_categories` unit tests (registry covers the four forms; name→code; code passthrough; unknown→None; missing file raises clear error).
- [x] 5.6 Run `uv run --with pytest python -m pytest test_cnreport.py -v -p no:logfire` — all existing tests still pass plus the new ones. No real HTTP traffic.

## 6. Self-check

- [x] 6.1 Extend `selfcheck.py` to exercise `list_report_types`, `list_filings(category=…)`, and `get_special_report` against the same mocks used by the test suite (no network). Confirm `python server.py --selfcheck` (or `uv run python selfcheck.py`) reports OK for each.

## 7. Documentation

- [x] 7.1 Update `mcp/cnreport-mcp/README.md` — add `list_report_types` and `get_special_report` to the tool table; add a "Special report types" example chain (list_report_types → list_filings(category=…) → get_special_report(section=…)); mention the `cninfo_categories.json` registry and that it's extensible.
- [x] 7.2 Update root `CLAUDE.md` `cnreport-mcp` section — bump the tool count (Eleven → Thirteen), add `list_report_types` and `get_special_report` to the tool list, note the `category` parameter on `list_filings` and the data-driven `cninfo_categories.json` registry (extensible by JSON edit, no code change).
- [x] 7.3 Add a one-line note to `construction/` docs if a construction doc covers cnreport-mcp's company API (check `construction/mcp.md`) — point at the registry as the source of truth for CNINFO category codes.
