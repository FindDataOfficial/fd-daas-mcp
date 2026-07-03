## 1. Dependencies & scaffolding

- [x] 1.1 Add `akshare>=1.13` and `pandas>=2.0` to `mcp/cnreport-mcp/pyproject.toml` under `[project].dependencies`
- [x] 1.2 Add the two new modules to `[tool.setuptools].py-modules`: `cninfo_client`, `financials_client`
- [x] 1.3 Run `uv sync --directory mcp/cnreport-mcp` and commit the updated `uv.lock`

## 2. CNINFO client (`cninfo_client.py`)

- [x] 2.1 Create `mcp/cnreport-mcp/cninfo_client.py` with a module-level `httpx.Client` factory (timeout, browser-like UA, no API key)
- [x] 2.2 Implement `lookup_company(ticker_or_name: str) -> dict | None` against `/new/data/szse_stock` (and SSE/BSE equivalents); resolve to `{stock_code, name, name_en, org_id, exchange, category}`
- [x] 2.3 Implement `query_announcements(stock_code: str, *, form: str | None, year: int | None, limit: int) -> list[dict]` against `/new/hisAnnouncement/query`; map response rows to `{announcement_id, title, form, published, pdf_url, stock_code}`
- [x] 2.4 Implement `get_announcement(announcement_id: str, *, stock_code: str | None) -> dict | None` (calls the same listing endpoint with a narrower query, picks the match)
- [x] 2.5 Add a `pdf_url(announcement_id, adjunct_url) -> str` helper that builds the static-cdn URL CNINFO uses for PDFs
- [x] 2.6 Snapshot one happy-path response JSON for each endpoint into `mcp/cnreport-mcp/test_fixtures/cninfo_*.json` (used by tests)

## 3. Financials client (`financials_client.py`)

- [x] 3.1 Create `mcp/cnreport-mcp/financials_client.py` with lazy akshare import (`import akshare as ak` inside the function, not at module top)
- [x] 3.2 Implement `get_statements(stock_code: str, *, period: str = "annual") -> dict[str, dict]` returning three keys: `income_statement`, `balance_sheet`, `cashflow`
- [x] 3.3 Each value is `{columns: list[str], data: list[list]}` — convert `pandas.DataFrame` via `df.to_dict(orient="split")` minus the `index` key
- [x] 3.4 Add `_serialize_df(df: pandas.DataFrame) -> dict` helper; handle NaN → None
- [x] 3.5 Map `period="annual"` → `report_type` Sina uses for 年报; `period="quarterly"` → 季报
- [x] 3.6 Return a `MissingDependencyError` (custom Exception) when akshare can't be imported, so the tool layer can convert it to `{"error": ...}`

## 4. Tool functions (`cnreport_tools.py` additions)

- [x] 4.1 Add `def get_company(ticker_or_name: str) -> dict:` — wraps `cninfo_client.lookup_company`, returns the dict or `{"error": "no match"}`
- [x] 4.2 Add `def list_filings(ticker_or_name: str, form: str | None = None, year: int | None = None, limit: int = 20) -> list[dict] | dict:` — resolves ticker → stock_code via `lookup_company`, then `query_announcements`
- [x] 4.3 Add `def get_filing(announcement_id: str, ticker_or_name: str | None = None) -> dict:` — wraps `cninfo_client.get_announcement`
- [x] 4.4 Add `def get_financials(ticker_or_name: str, statement: str | None = None, period: str = "annual") -> dict:` — calls `financials_client.get_statements`, filters to the requested statement if any
- [x] 4.5 Add `def get_section(ticker_or_name: str, year: int, section: str, form: str = "年度报告") -> dict:` — calls `list_filings` with `form` + `year`, picks the first match, then routes into the existing `fetch_source` / `parse_outline` / `resolve_selector` / `extract_section_text` chain; returns `{stock_code, company_name, year, form, section, pdf_url, text, outline_entry}` or `{"error": ...}`
- [x] 4.6 Wrap every new function body in a try/except that converts any exception to `{"error": str(e)}` — matches `edgartools-mcp` pattern
- [x] 4.7 Wire the lazy akshare error: if `financials_client.MissingDependencyError` is raised, return `{"error": "akshare not installed. Run: uv sync --directory mcp/cnreport-mcp"}`

## 5. Server registration (`server.py`)

- [x] 5.1 Import the five new tool functions into `server.py`
- [x] 5.2 Register each one with `@mcp.tool` (or `mcp.add_tool(...)`, whichever pattern the existing file uses); copy/adapt the docstrings from `edgartools-mcp/server.py` so MCP clients see good descriptions
- [x] 5.3 Confirm `server.py --selfcheck` still launches and prints "OK" for the six existing tools

## 6. Tests (`test_cnreport.py`)

- [x] 6.1 Add a `tests/fixtures/` directory loader (or reuse `test_fixtures/`); load the snapshots from task 2.6
- [x] 6.2 Add `test_get_company_by_ticker` — patches `cninfo_client._client()` (or whatever the http entry is) with a `respx`/`httpx` mock returning the snapshot; asserts `stock_code == "600519"`
- [x] 6.3 Add `test_get_company_by_name` — same fixture, name input
- [x] 6.4 Add `test_get_company_unknown_returns_error` — empty response → `{"error": ...}`
- [x] 6.5 Add `test_list_filings_basic` + `test_list_filings_filter_form` + `test_list_filings_filter_year`
- [x] 6.6 Add `test_get_filing_by_id` + `test_get_filing_invalid_returns_error`
- [x] 6.7 Add `test_get_financials_all` + `test_get_financials_single_statement` + `test_get_financials_missing_akshare_returns_error` (patch the import to raise)
- [x] 6.8 Add `test_get_section_happy_path` — mock CNINFO listing + a small in-memory PDF/text fixture for outline extraction
- [x] 6.9 Add `test_get_section_unknown_section_returns_error` and `test_get_section_no_filing_returns_error`
- [x] 6.10 Extend `server.py --selfcheck` to exercise each of the five new tools against the same mocks (or skip cleanly if mocks not available)

## 7. Documentation

- [x] 7.1 Update `CLAUDE.md` → `mcp/cnreport-mcp/` section: add the five new tools to the description, note `EDGAR_IDENTITY`-equivalent is unnecessary (CNINFO is keyless), call out the new akshare dep
- [x] 7.2 Add a short usage example to `mcp/cnreport-mcp/` README (or create one if missing) showing the typical `get_company → list_filings → get_section → ai_extract` chain
- [x] 7.3 Verify `openspec validate add-cnreport-company-financials` passes

## 8. End-to-end smoke

- [x] 8.1 Run `uv run --directory mcp/cnreport-mcp pytest -v` — all old + new tests green, fully offline
- [x] 8.2 Run `uv run --directory mcp/cnreport-mcp python server.py --selfcheck` — green
- [x] 8.3 Manual live check (network required, off-CI): `get_company("600519")` returns Kweichow Moutai; `list_filings("600519", form="年度报告", limit=3)` returns ≥1 PDF URL; `get_financials("600519")` returns three statements with non-empty `data`; `get_section("600519", 2023, "管理层讨论与分析")` returns non-empty `text`
