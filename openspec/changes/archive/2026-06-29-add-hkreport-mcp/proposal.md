## Why

We have purpose-built financial-filing MCPs for the US (`edgartools-mcp`), Japan (`edinet-mcp`), Korea (`dartlab-mcp`), and mainland China A-shares (`cnreport-mcp`), but no equivalent for the Hong Kong market. Hong Kong is the third-largest financial center for Chinese issuers (H-shares, red chips, dual-listed mainland giants like Tencent, Alibaba, BYD), and agents asking about HK-listed companies currently have to fall back to generic web search or partial coverage via `akshare`/`yfinance`. A dedicated `hkreport-mcp` closes that gap with an edgartools-style company-and-filings API surface.

## What Changes

- Add a new `mcp/hkreport-mcp/` FastMCP server with the same purpose-built shape as `edgartools-mcp` (no registry, no harness — `hkex` doesn't expose a flat function catalog).
- Five tools, mirroring the edgartools surface: `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_disclosure_calendar`.
  - `get_company` — resolve a HK-listed company by 5-digit stock code (e.g. `00700`) or name fragment (e.g. `Tencent` / `腾讯`), returning code, name, sector, board, and basic profile.
  - `list_filings` — list HKEXnews disclosures for a company, optionally filtered by document type (Annual Report, Interim Report, Announcement, Circular, ...) and year. Each entry includes title, date, document type, language (en/zh), and the canonical HKEXnews PDF URL.
  - `get_filing` — fetch a single filing by its HKEXnews document id (or URL) and return parsed metadata + (optionally) a text extract of the PDF.
  - `get_financials` — return structured income statement / balance sheet / cash-flow records for an HK ticker, backed by `akshare`'s `stock_financial_hk_*` functions. Shape matches `edgartools-mcp.get_financials` (`{columns, data}` records per statement).
  - `get_disclosure_calendar` — list upcoming / recent results-announcement and AGM dates from the HKEX calendar feed for a ticker.
- Data sources, in priority order: (1) HKEXnews public title-search and disclosure-list HTTP endpoints (keyless) for filings; (2) `akshare` `stock_financial_hk_*` for normalized financials; (3) `yfinance` (`<ticker>.HK`) as a fallback only for basic profile/last-price when HKEXnews is unreachable. No paid API.
- Register the new MCP in `.mcp.json` and seed it into `daas-mcp` (`seed_external_mcps.py`) as a datasource named `hkex` with category `markets/hk` and a `core` collection entry — same shape as `edgar` / `edinet` / `cnreport`.
- Ship a `selfcheck.py` (no network) and a small offline `test_hkreport.py` that mocks HKEXnews + akshare.

## Capabilities

### New Capabilities
- `hkreport-mcp-server`: a purpose-built FastMCP stdio server at `mcp/hkreport-mcp/` exposing the five HK-market filing/financial tools above, with HKEXnews + akshare backing and graceful errors when network or optional deps are unavailable.

### Modified Capabilities
- `external-mcp-datasource-seed`: extend `daas-mcp`'s `seed_external_mcps.py` to register `hkex` alongside the existing `edgar` / `edinet` / `yfinance` / `cnreport` datasources (new form/section rows + `core` collection membership). The seed script's idempotency, `--unseed`, and `--dry-run` semantics SHALL continue to apply.

## Impact

- New code: `mcp/hkreport-mcp/{server.py, hkex_client.py, financials_client.py, pyproject.toml, selfcheck.py, test_hkreport.py, README.md, .env.example}`.
- Modified files: `.mcp.json` (one new stdio entry), `mcp/daas-mcp/seed_external_mcps.py` (one new datasource block), root `CLAUDE.md` (add an `### mcp/hkreport-mcp/` section), `construction/mcp.md` (one row added to the MCP table).
- New optional env var: none required for the core tools (HKEXnews + akshare are keyless). The shared `LLM_*` and proxy vars in root `.env` are reused if present.
- Dependencies: `fastmcp>=2.0`, `httpx>=0.27`, `pypdf>=4.0`, `akshare>=1.13`, `pandas>=2.0`, `python-dotenv>=1.0`, `mcp-models` (for the optional `Document`/`Section` provenance rows, only if we choose to persist filings — otherwise drop this dep). No database tables added; the MCP is live-execution only, like `edgartools-mcp`.
- No breaking changes to existing MCPs or specs. Only `external-mcp-datasource-seed` gains one new datasource entry.
