## 1. Scaffold mcp/hkreport-mcp

- [x] 1.1 Create `mcp/hkreport-mcp/` with `pyproject.toml` (deps: `fastmcp>=2.0`, `httpx>=0.27`, `pypdf>=4.0`, `akshare>=1.13`, `pandas>=2.0`, `python-dotenv>=1.0`; `requires-python>=3.10`; `[tool.setuptools] py-modules = [server, hkex_client, financials_client]`)
- [x] 1.2 Add empty `.env.example` (documents optional `HTTPS_PROXY` only; no required vars)
- [x] 1.3 Add `README.md` summarizing the five tools, the data sources (HKEXnews + akshare), and the keyless contract
- [x] 1.4 `uv sync` inside the new dir to lock deps

## 2. HKEXnews client (hkex_client.py)

- [x] 2.1 `_normalize_ticker(value) -> str` accepting `"00700"`, `"700"`, `"0700.HK"`, `"700.HK"` and producing the 5-digit zero-padded form
- [x] 2.2 `lookup_company(query)` hitting `instrument_search.json` → returns `{stock_code, name, name_zh, board, sector, industry}` or raises `LookupError`
- [x] 2.3 `list_announcements(stock_code, doc_type=None, year=None, language=None, limit=20)` POSTing to `titleSearchServlet.aspx` → list of `{doc_id, title, form, published, language, stock_code, documents:[{lang,url}]}`
- [x] 2.4 Duplicate collapsing: group rows that share `(stock_code, published, form, normalized_title)` and merge their PDFs into the `documents` list
- [x] 2.5 `fetch_announcement(doc_id_or_url, with_text=True, text_cap_bytes=200_000)` downloads the PDF and extracts text via `pypdf` (lazy import); returns text + parsed metadata, surfacing a `truncated: true` flag when cap is hit
- [x] 2.6 `list_calendar(stock_code, kind=None)` parsing the HKEX calendar HTML → list of `{date, kind, event, stock_code}`
- [x] 2.7 Centralized `httpx.Client` with timeout, retry on 5xx (exponential backoff, max 3), proxy via env, custom UA `cli-anything/hkreport-mcp`
- [x] 2.8 All client functions raise typed errors (`LookupError`, `httpx.HTTPError`); the server is responsible for translating them to `{error, hint}` dicts

## 3. akshare financials client (financials_client.py)

- [x] 3.1 Lazy `import akshare as ak` inside each call; raise `ImportError` with hint if missing
- [x] 3.2 `fetch_income_statement(stock_code, period)` wrapping `stock_financial_hk_report_em(symbol=stock_code, indicator="利润表", report_type=period)`; normalize to `{columns, data}` records
- [x] 3.3 `fetch_balance_sheet(stock_code, period)` and `fetch_cashflow(stock_code, period)` (same pattern)
- [x] 3.4 Map `period`: `"annual"` → akshare's annual indicator, `"interim"` → akshare's interim indicator
- [x] 3.5 Reuse a `_serialize_df(df)` helper copied from `mcp/edgartools-mcp/server.py._serialize` (object dtype, NaN→None)

## 4. server.py — FastMCP wiring

- [x] 4.1 Load env: root `.env` first, then per-MCP `.env` with `override=True` (copy from `mcp/edgartools-mcp/server.py`)
- [x] 4.2 Instantiate `FastMCP(name="hkreport-mcp")` and register five `@app.tool()` functions
- [x] 4.3 `get_company(ticker_or_name: str)` → calls `hkex_client.lookup_company`, returns dict or `{error, hint}`
- [x] 4.4 `list_filings(ticker_or_name: str, form: str|None = None, year: int|None = None, language: str|None = None, limit: int = 20)` → calls `lookup_company` then `list_announcements`
- [x] 4.5 `get_filing(doc_id_or_url: str, detail: str = "standard")` → calls `fetch_announcement`; map `detail` to text-cap bytes (minimal=0, standard=50_000, full=200_000)
- [x] 4.6 `get_financials(ticker_or_name: str, statement: str|None = None, period: str = "annual")` → calls `lookup_company` for code resolution, then the `financials_client` calls
- [x] 4.7 `get_disclosure_calendar(ticker_or_name: str, kind: str|None = None, limit: int = 10)` → calls `list_calendar`
- [x] 4.8 Common decorator `@_safe_tool` wraps each tool to catch `LookupError`/`httpx.HTTPError`/`ImportError`/`Exception` and convert to structured `{error, hint}` dicts
- [x] 4.9 `if __name__ == "__main__": app.run(transport="stdio", show_banner=False)`

## 5. selfcheck.py and tests

- [x] 5.1 Write `selfcheck.py` that uses `respx` (or `httpx.MockTransport`) to mock HKEXnews endpoints, monkeypatches `akshare.stock_financial_hk_report_em` with a tiny DataFrame, then calls each of the five tools end-to-end, asserting the documented response shapes; prints `OK <tool>` and exits 0
- [x] 5.2 Add `respx` to the dev dependencies in `pyproject.toml` (`[project.optional-dependencies] dev = [...]`)
- [x] 5.3 Write `test_hkreport.py` with one test per tool covering: success path, missing-dep (akshare), network error, empty result
- [x] 5.4 Guard live-network tests behind `@pytest.mark.skipif(not os.environ.get("HKREPORT_LIVE"), reason="live")` — none enabled by default in CI
- [x] 5.5 Verify offline: `uv run --with pytest python -m pytest test_hkreport.py -v -p no:logfire` passes with no network

## 6. Register the MCP and seed it into daas-mcp

- [x] 6.1 Add a `hkreport-mcp` entry to `.mcp.json` with `command: "uv"` and `args: ["run", "--directory", "mcp/hkreport-mcp", "python", "server.py"]`
- [x] 6.2 Edit `mcp/daas-mcp/seed_external_mcps.py` to add an `hkex` block: datasource (name `hkex`, label `Hong Kong Stock Exchange (HKEXnews + akshare)`, url `https://www1.hkexnews.hk`), category `Filings → HK-HKEX`, five forms (`Annual Report`, `Interim Report`, `Announcement`, `Financials`, `Calendar`) each with one section whose instruction is `mcp=hkreport-mcp tool=<tool> param=ticker_or_name=<query>`, and a `core` collection membership entry
- [x] 6.3 Make sure `--unseed` removes the `hkex` rows and the empty `HK-HKEX` leaf category (use the existing helpers; don't roll new SQL)
- [x] 6.4 Run the seed against a temp db: `DAAS_DATABASE_URL="sqlite:////tmp/seed-check.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py` and verify `list_sources`/`list_forms`/`list_collection` show `hkex` correctly; re-run and confirm idempotency

## 7. Docs

- [x] 7.1 Add an `### mcp/hkreport-mcp/` section to root `CLAUDE.md` (mirror the `mcp/edgartools-mcp/` block)
- [x] 7.2 Add one row to the MCP table in `construction/mcp.md`
- [x] 7.3 Mention the `hkex` seed in the `seed_external_mcps.py` paragraph (same place where `edgar`/`edinet`/`cnreport` are listed)

## 8. Verify

- [x] 8.1 `uv run --directory mcp/hkreport-mcp python selfcheck.py` returns 0
- [x] 8.2 `uv run --directory mcp/hkreport-mcp python -m pytest test_hkreport.py -v -p no:logfire` passes offline
- [x] 8.3 `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py` runs cleanly twice (idempotent)
- [x] 8.4 With `.mcp.json` updated, an interactive Claude Code session can list the five `hkreport-mcp` tools
- [ ] 8.5 With `HKREPORT_LIVE=1`, a live smoke test against ticker `00700` returns a non-empty `list_filings` result and a non-empty `get_financials` payload
