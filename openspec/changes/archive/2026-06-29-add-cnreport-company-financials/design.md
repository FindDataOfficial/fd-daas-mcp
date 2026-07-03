## Context

`mcp/cnreport-mcp/` was built as a PDF-section extractor: hand it a URL or local file, get the 目录, pull a section by selector, optionally LLM-extract structured records, optionally index to Elasticsearch. That covers `report-outline-extraction`, `report-ai-processing`, and the two ES capabilities. What it does NOT cover is the discoverability step that `edgartools-mcp` covers for US filings — given a ticker, where ARE this company's filings? What are the URLs? Where are the structured statements?

This change adds that company-API layer. It is intentionally scoped to "make cnreport-mcp feature-parity with edgartools-mcp for CN-A-share", not to refactor the existing capabilities.

Two upstream sources are required:

1. **CNINFO** (`http://www.cninfo.com.cn`) — the official A-share / SZSE/SSE/BSE disclosure portal. Its public JSON endpoints (`/new/hisAnnouncement/query`, `/new/data/szse_stock`, etc.) cover company lookup and announcement listings without an API key. EdgarTools' analog: SEC's submissions JSON.
2. **akshare** — the project already depends on it (`akshare-agent-harness/`) and it ships a clean wrapper around Sina's structured-financials feed (`stock_financial_report_sina`). akshare is the path of least resistance for the three statements; building our own XBRL-style parser is out of scope.

## Goals / Non-Goals

**Goals:**

- One-call lookup (`get_company(ticker_or_name)`) covering all three Chinese exchanges (SSE / SZSE / BSE).
- Filing listings (`list_filings`) filterable by form type and year, returning real PDF URLs that the existing `extract_section` can consume.
- Three-statement financials (`get_financials`) shaped identically to `edgartools-mcp.get_financials` (`{columns, data}` records) so downstream agents written against EDGAR can be retargeted at CN with minimum code change.
- A `get_section(ticker, year, section)` shortcut that bridges the new company API and the existing PDF tooling — this is the "section data from financial PDF report" the proposal calls out.
- Offline-runnable tests for every new tool; the server must start even when `akshare` is uninstalled.

**Non-Goals:**

- XBRL parsing of CN annual reports. Sina's pre-parsed feed via akshare is good enough and matches the granularity edgartools' Financials object offers.
- Auth or paid-tier data sources (Tushare Pro, Wind, etc.). Keyless only.
- Caching layer. The MCP is stateless; if caching is needed, it belongs in a future change.
- Seeding the new tools into `daas-mcp`'s registry. A separate `add-cnreport-section-to-daas` change already exists for the section path; the company-API surface can be seeded in a follow-up.
- Modifying any of the existing six tools (`list_outline`, `extract_section`, `ai_extract`, `index_records`, `search_reports`, `delete_index`).

## Decisions

### CNINFO over scraping HTML

CNINFO exposes JSON endpoints that drive its own SPA. Calling those directly (with a plain `httpx` client and a browser-like User-Agent) is stable and license-clean. Alternatives considered:

- **Scrape HTML / use Playwright** — adds a heavy dep (`scrapling`/Playwright), and CNINFO's HTML is rendered client-side, so it requires headless browsing. JSON endpoints make this moot.
- **Use a third-party aggregator (Tushare, Wind)** — paid or rate-limited, and adds an API-key requirement to a previously keyless MCP.

### akshare for financials, not raw Sina/Eastmoney

akshare is already a project dependency and its `stock_financial_report_sina` returns a typed `pandas.DataFrame` with the layout we want. Alternatives:

- **Direct Sina HTTP** — duplicates akshare's parsing logic and creates a maintenance burden when Sina's response shape drifts. Skipped.
- **Eastmoney instead of Sina** — Eastmoney's data is fresher but its column naming is less standardized across statements. Pick Sina by default; can add an `eastmoney=True` flag later if quarterly data lag becomes a problem.

### Five tools, not three or seven

Five matches edgartools' surface and lets every Chinese filing question route through one obvious tool. Smaller (e.g. roll `get_filing` into `list_filings`) loses parity; larger (e.g. expose insider trades, related-party transactions, holders) drifts into "akshare-MCP" territory, which already exists separately.

### `get_section` returns `text`, not LLM output

`get_section` exists to bridge the company API to the existing `extract_section`. It returns the raw section body. Agents that want structured records still chain `ai_extract` themselves — keeps responsibilities orthogonal and the response size predictable.

### Two new modules, not one giant `cnreport_tools.py`

`cnreport_tools.py` is already 600+ lines mixing parsing, AI extraction, and ES. Adding CNINFO HTTP + akshare on top would push it past readability. Splitting into `cninfo_client.py` and `financials_client.py` keeps each module testable in isolation and makes the akshare dependency lazy (server starts even if akshare is missing; only `get_financials` returns an error).

### Errors as data, not exceptions

Matches the pattern in `edgartools-mcp` / `edinet-mcp` / `dartlab-mcp` — tools return `{"error": "..."}` on any upstream failure. The MCP transport layer is reserved for actual protocol errors. This is a project-wide convention; following it.

## Risks / Trade-offs

- **CNINFO endpoint stability** → CNINFO has been stable for years but is not an officially-documented public API; if response shapes shift, `cninfo_client.py` needs maintenance. Mitigation: keep the client module thin and snapshot a sample response in the test fixtures so a shape change fails loudly.
- **akshare upstream churn** → akshare itself wraps Sina/Eastmoney and occasionally breaks when those sites change. Mitigation: pin `akshare>=1.13` and let the tool's `error` field surface the upstream failure; do not crash the server.
- **PDF URL form drift across years** → Pre-2008 filings may live on different paths or have non-standard form labels. Mitigation: `list_filings`' `form` and `year` filters are best-effort, not strict; document the limitation in the SKILL.md.
- **Cross-jurisdiction confusion** → Agents may try to pass A-share tickers to `edgartools-mcp` and vice-versa. Mitigation: name parity (`get_company`, `list_filings`, `get_financials`) is deliberate — failure mode is "ticker not found", which is the right error.
- **akshare adding a heavy install footprint** → akshare pulls in many transitive deps. Mitigation: it lives in `cnreport-mcp`'s isolated venv; doesn't affect other MCPs. Lazy-import inside `financials_client.py` so missing-akshare is a graceful per-tool error, not a server-start failure.
- **No caching** → Repeated `get_financials` calls hit Sina each time. Acceptable for v1; CNINFO and Sina are both fast. If hot-path agents emerge, add a small TTL cache (`functools.lru_cache` keyed on `(ticker, period, statement)`).

## Migration Plan

No data migration; purely additive. Steps:

1. Add `akshare` and `pandas` to `mcp/cnreport-mcp/pyproject.toml` → `uv sync --directory mcp/cnreport-mcp` (or equivalent).
2. Land `cninfo_client.py` + `financials_client.py` + tool additions + tests.
3. `python server.py --selfcheck` passes with both real and mocked clients.
4. Update `.mcp.json` is unnecessary — entry already exists.
5. Update top-level `CLAUDE.md`'s cnreport-mcp section to list the new tools.

Rollback: the change is purely additive and the new tools each guard their imports. Reverting the commit removes the tools without touching existing behavior.

## Open Questions

- Should `get_company` accept a "fuzzy" name (e.g. `"贵州茅台酒"`) and return the best match, or require an exact substring? Default to substring-match; revisit if it produces noisy results.
- Should financials period support `"interim"` (半年报) in addition to `annual` and `quarterly`? Sina exposes 半年报 rows; akshare returns them inside the quarterly feed. Default to two values for v1; expand later if asked.
