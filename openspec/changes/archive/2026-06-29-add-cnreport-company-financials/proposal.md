## Why

`cnreport-mcp` today is PDF-section-shaped: agents already get `list_outline` / `extract_section` / `ai_extract` for Chinese annual reports — but to use any of them they need a report URL in hand. There is no "edgartools-for-China" surface: you cannot ask "what filings has 600519 disclosed", "give me Kweichow Moutai's most recent annual report", or "show me their three statements" without leaving the MCP. EDGAR (US) and DART (KR) both have this company-API layer; CN does not.

## What Changes

- Add a CNINFO-backed company API to `mcp/cnreport-mcp/`: four new tools (`get_company`, `list_filings`, `get_filing`, `get_financials`) modeled on `edgartools-mcp`, plus a convenience `get_section` that resolves `(ticker, year, section)` to a PDF URL and reuses the existing `extract_section`.
- `get_company` / `list_filings` / `get_filing` SHALL hit the public CNINFO disclosure JSON API (`http://www.cninfo.com.cn/new/...`) — no API key, no scraping.
- `get_financials` SHALL pull structured income / balance / cashflow statements from `akshare` (already a project-level dep via `akshare-agent-harness/`). Wraps `stock_financial_report_sina` (annual/quarterly) and `stock_financial_abstract` as appropriate; returns `{columns, data}` records like `edgartools-mcp` does.
- Existing `list_outline` / `extract_section` / `ai_extract` / `index_records` / `search_reports` / `delete_index` are UNCHANGED — the new tools sit alongside them.
- `pyproject.toml` adds `akshare` and `pandas` to the `cnreport-mcp` venv (CNINFO calls reuse the existing `httpx` dep).
- Optional follow-up (not in scope of this change): seed the new tools into `daas-mcp`'s registry the way the existing `add-cnreport-section-to-daas` change wires `extract_section`.

## Capabilities

### New Capabilities

- `cnreport-company-api`: company lookup, filings listing, filing fetch, structured financials, and high-level section retrieval for Chinese A-share annual reports — the edgartools-style surface for CN.

### Modified Capabilities

(none — existing `report-outline-extraction` / `report-ai-processing` / `report-elasticsearch-store` / `report-elasticsearch-search` capabilities are untouched.)

## Impact

- Code: `mcp/cnreport-mcp/` — new module `cninfo_client.py` (CNINFO JSON-API wrapper), new module `financials_client.py` (akshare wrapper), additions to `cnreport_tools.py` (5 new tool functions), additions to `server.py` (`@mcp.tool` registrations). Existing files unchanged in their current behavior.
- Tests: extend `test_cnreport.py` with offline scenarios for each new tool (mock httpx for CNINFO, mock the akshare wrapper) plus the existing `--selfcheck` flag in `server.py`.
- Dependencies: `cnreport-mcp/pyproject.toml` gains `akshare>=1.13`, `pandas>=2.0`. `httpx` is already present.
- Database: none — purpose-built MCP, lives outside `mcp/daas.db` (same posture as `edgartools-mcp` / `edinet-mcp` / `dartlab-mcp`).
- Network: outbound HTTP to `cninfo.com.cn` and the data sources akshare uses (Sina / Eastmoney). No new credentials; CNINFO is keyless.
- No breaking changes to the MCP wire protocol — only new tool registrations.
