## Context

The repo already runs four purpose-built financial-filing MCPs — `edgartools-mcp` (US), `edinet-mcp` (JP), `dartlab-mcp` (KR), `cnreport-mcp` (CN A-shares). HK is the only major Asia-Pacific market without an MCP. HKEX disclosures live on the public HKEXnews portal, and `akshare` ships a reasonable set of `stock_financial_hk_*` functions for normalized HK financial statements. Together they cover the company-API surface we want, with zero paid keys.

The four existing MCPs split into two camps:
- **Object-model wrappers** (`edgartools-mcp`, `dartlab-mcp`, `edinet-mcp`) — wrap a third-party library that already speaks the market's filings.
- **Hand-rolled clients** (`cnreport-mcp`) — no upstream library exists, so we hit the regulator's HTTP API directly.

HK has no `edgartools`-equivalent Python library, so this MCP belongs in the second camp: a thin hand-rolled HKEXnews client + an `akshare` pass-through for financials. The shape of the tool surface, however, mirrors `edgartools-mcp` exactly (five tools, same names where it makes sense) so agents already trained on the US surface generalize.

## Goals / Non-Goals

**Goals:**
- Five tools — `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_disclosure_calendar` — covering the HK-listed-company lookup → filings → financials path.
- Live-execution only (no DB writes). Match `edgartools-mcp`'s lifecycle: lazy imports, JSON-serializable returns, structured `{"error": ..., "hint": ...}` failure dicts.
- Keyless out of the box. HKEXnews and `akshare` HK endpoints don't require auth; the MCP MUST work the moment it's installed.
- Seed into `daas-mcp` as the `hkex` datasource so the unified registry and the dashboard see it.
- Offline-runnable selfcheck + tests (HTTP mocked).

**Non-Goals:**
- XBRL parsing. HKEX doesn't mandate machine-readable filings; PDFs are the source of truth. Section extraction stays out of v1 (cnreport already shows how to layer that on; we can copy the pattern later).
- Real-time price/quote data — covered by `yfinance-mcp` with the `.HK` suffix.
- A registry/harness or a `daas.db` table. This is a live-execution wrapper, like `edgartools-mcp`.
- Mainland-China dual-listings de-duplication. If a company is listed on both Shanghai/Shenzhen and Hong Kong, agents pick the appropriate MCP themselves.
- Cantonese-only filings; we'll surface whatever language(s) HKEXnews returns and tag each entry with `language: "en" | "zh" | "both"`.

## Decisions

### D1. Hand-rolled HKEXnews client over a third-party library

There is no maintained Python wrapper for HKEXnews. The closest options are scrapers that pull from third-party mirrors. We hit `https://www1.hkexnews.hk/` directly with `httpx` instead.

- `hkex_client.py` exposes `lookup_company(query)`, `list_announcements(stock_code, doc_type=None, year=None, limit=20)`, `fetch_announcement(doc_id_or_url)`, `list_calendar(stock_code, kind=None)`.
- Endpoints used (all public, JSON or POST-form):
  - `https://www1.hkexnews.hk/ncms/script/eds/instrument_search.json` for the company-name / code lookup (returns code, name, board, sector).
  - `https://www1.hkexnews.hk/search/titleSearchServlet.aspx` (POST form-data) for the disclosure list — supports filters by stock id, doc type, language, date range.
  - `https://www1.hkexnews.hk/listedco/listconews/sehk/<yyyy>/<mmdd>/<filename>.pdf` for the actual PDFs (URL is in each disclosure record).
  - `https://www.hkex.com.hk/eng/services/timesandqueries/Issuer/Calendar.aspx` (HTML, fallback only) for the disclosure calendar.
- Rationale: keeps deps tiny (`httpx` only), keyless, and we own the bugs. Same shape as `cnreport-mcp/cninfo_client.py`.

**Alternative considered:** scraping `hkexnews.hk` via headless browser. Rejected — the JSON/POST endpoints already work without JS; adding Playwright would balloon the install footprint and the maintenance surface.

### D2. `akshare` for financials, not a hand-rolled XBRL parser

HKEX filings are PDFs, not XBRL. `akshare.stock_financial_hk_report_em(symbol, indicator)` already returns normalized income statement / balance sheet / cash-flow records, scraped from EastMoney's HK terminal. The data is reliable enough for an agent surface, and we already depend on `akshare` for `cnreport-mcp` and `akshare-mcp`.

- `financials_client.py` wraps `stock_financial_hk_report_em` + `stock_financial_hk_analysis_indicator_em` and normalizes the dataframe shape to `{columns, data}` records — same shape `edgartools-mcp.get_financials` returns. The serializer is copy-pasted from `edgartools-mcp.server._serialize`.
- Ticker conversion: HK stock codes are 5 digits with a leading zero (`00700`, `09988`). EastMoney expects the same 5-digit form. `yfinance` expects `0700.HK` (4 digits + `.HK`). We normalize internally and accept either form on input.

**Alternative considered:** parsing the financial-statements tables directly out of the annual-report PDF. Rejected for v1 — too slow, too noisy, and PDF table extraction has known failure modes. Punt to a follow-up that copies cnreport's PDF/AI/ES tools.

### D3. Live-execution only, no `daas.db` writes

Mirror `edgartools-mcp`, `edinet-mcp`, `dartlab-mcp`. No tables, no schema changes to `mcp/models/`, no `mcp-models` dep at runtime.

- If we later decide to persist filings (mirror `cnreport-mcp`'s use of `Document`/`Section`/`EsIndex` rows), it's an additive change with its own proposal.
- Trade-off: agents can't ask "what HK reports have we cached" because we cache nothing. Fine for v1; that's an MCP-level cache concern, not a market-coverage concern.

### D4. Tool surface: five tools, names aligned with `edgartools-mcp`

| edgartools-mcp     | hkreport-mcp                | Notes                                                                 |
|--------------------|-----------------------------|-----------------------------------------------------------------------|
| `get_company`      | `get_company`               | accepts 5-digit code or name fragment (en/zh)                         |
| `list_filings`     | `list_filings`              | `form` enum is HK-specific (Annual Report / Interim Report / ...)     |
| `get_filing`       | `get_filing`                | input is HKEXnews `doc_id` or full PDF URL                            |
| `get_financials`   | `get_financials`            | `statement` enum: `income_statement` / `balance_sheet` / `cashflow`   |
| `get_insider_trades` | `get_disclosure_calendar` | HK doesn't have a Form-4 equivalent agents would query; results calendar is what investors actually ask for |

Rationale: keep the first four names identical so an agent's mental model transfers. Replace the fifth with the HK-meaningful counterpart.

**Alternative considered:** also wrap `stock_hk_main_board_spot_em` / `stock_hk_index_*` for quotes and indices. Rejected — that's `yfinance-mcp` and `akshare-mcp`'s job. This MCP stays scoped to filings + financials.

### D5. Seed shape in `daas-mcp`

In `seed_external_mcps.py`, add an entry mirroring the `edgar` block:

- Datasource name `hkex`, label `Hong Kong Stock Exchange (HKEXnews + akshare)`.
- Category path: `markets / hk`.
- Five forms (one per tool), each with one section containing the routing-grammar instruction `mcp=hkreport-mcp tool=<tool> param=<k>=<v>`.
- Membership in the `core` collection — same as `edgar` / `edinet` / `cnreport`.
- Idempotency / `--unseed` / `--dry-run` already covered by the existing helpers; no schema change needed.

### D6. Test strategy

- `selfcheck.py` (offline) instantiates the server, asserts the five tools register, and calls each with HTTP mocked via `respx`. Same shape as `cnreport-mcp/selfcheck.py`.
- `test_hkreport.py` (offline) covers the three error-path branches per tool: missing dep, network error, empty result. Live HTTP is gated behind a `HKREPORT_LIVE=1` env var so CI never hits the network.

## Risks / Trade-offs

- **HKEXnews HTML/JSON shape changes** → mitigation: keep the client small, cover it with unit tests against captured response fixtures, and surface a single `error` field if the response shape no longer parses. Same exposure cnreport-mcp already has against CNINFO.
- **akshare HK functions break or rate-limit** → mitigation: try/except around the akshare call, return `{"error": "akshare HK provider unavailable", "hint": "..."}` and let agents fall back to `list_filings` + PDF for the same period.
- **Dual-language filings (en/zh) are duplicate-listed by HKEXnews** → mitigation: collapse duplicates by `(date, document_type)` and surface both PDF URLs in a single record under `documents: [{lang, url}, ...]`.
- **PDF size for `get_filing` with full-text** → mitigation: default to metadata-only (`detail="standard"`); `detail="full"` returns at most the first ~200 KB of extracted text, with a `truncated: true` flag, mirroring `edgartools-mcp`.
- **Time-zone confusion** → all dates are HKT; we return ISO-8601 strings and document the TZ in the response, never silently convert.

## Migration Plan

Pure additive. No existing files change behavior; new files are created and `.mcp.json` gains one entry. Rollback = delete `mcp/hkreport-mcp/`, revert the one-line `.mcp.json` and `seed_external_mcps.py` additions.
