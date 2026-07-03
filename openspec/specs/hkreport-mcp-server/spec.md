# hkreport-mcp-server Specification

## Purpose
TBD - created by archiving change add-hkreport-mcp. Update Purpose after archive.
## Requirements
### Requirement: FastMCP hkreport-mcp server with five purpose-built tools

The system SHALL provide a FastMCP server at `mcp/hkreport-mcp/server.py` using stdio transport, exposing five tools — `get_company`, `list_filings`, `get_filing`, `get_financials`, and `get_disclosure_calendar` — covering the Hong Kong stock market (HKEX) filing-and-financials surface. This follows the purpose-built pattern (like `edgartools-mcp` / `edinet-mcp` / `dartlab-mcp`), not the registry/harness pattern, because HKEX exposes neither a maintained Python library nor a flat function catalog.

#### Scenario: Server starts and registers tools

- **WHEN** the server is started with `uv run --directory mcp/hkreport-mcp python server.py`
- **THEN** all five tools are registered and callable over stdio

#### Scenario: Server uses FastMCP stdio transport

- **WHEN** the server is started
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, matching the other purpose-built MCPs

#### Scenario: Server loads unified env

- **WHEN** the server starts
- **THEN** it loads root `.env` first via `python-dotenv`, then `mcp/hkreport-mcp/.env` with `override=True`, matching the unified-env convention used by `edgartools-mcp` and `edinet-mcp`

### Requirement: hkreport-mcp is keyless for the core tools

The server SHALL function without any required API key for all five tools. HKEXnews and the `akshare` HK endpoints are public; the server SHALL NOT refuse to start, nor SHALL any tool emit a `requires-key` error, when no `HKEX_*` environment variable is set.

#### Scenario: Server starts without any HKEX-specific env

- **WHEN** the server starts with no `HKEX_*` env var defined
- **THEN** the server starts cleanly and every tool is callable

#### Scenario: Optional proxy env is honored

- **WHEN** `HTTPS_PROXY` or `HTTP_PROXY` is set in the environment
- **THEN** the HKEXnews client routes its HTTP calls through that proxy

### Requirement: get_company resolves a HK-listed company

The `get_company(ticker_or_name)` tool SHALL return a JSON-serializable dict describing a HK-listed company — including `stock_code` (5-digit zero-padded), `name` (English), `name_zh` (Chinese, if available), `board` (`Main` / `GEM`), `sector`, and `industry` — by querying the HKEXnews instrument-search endpoint. It SHALL accept either a 5-digit ticker (`"00700"`), a 4-digit `.HK`-suffixed form (`"0700.HK"`), or a name fragment (`"Tencent"` / `"腾讯"`).

#### Scenario: Lookup by 5-digit ticker

- **WHEN** `get_company(ticker_or_name="00700")` is called
- **THEN** it returns a dict whose `stock_code` is `"00700"` and `name` contains `"Tencent"`

#### Scenario: Lookup by .HK-suffixed ticker

- **WHEN** `get_company(ticker_or_name="0700.HK")` is called
- **THEN** it returns a dict whose `stock_code` is `"00700"`

#### Scenario: Lookup by Chinese name fragment

- **WHEN** `get_company(ticker_or_name="腾讯")` is called
- **THEN** it returns a dict whose `stock_code` is `"00700"`

#### Scenario: Unknown company returns an error

- **WHEN** `get_company(ticker_or_name="ZZZZZZ")` is called
- **THEN** it returns an `error` field indicating no match was found, without raising

### Requirement: list_filings lists HKEXnews disclosures

The `list_filings(ticker_or_name, form=None, year=None, language=None, limit=20)` tool SHALL list HKEXnews disclosures for a company, optionally filtered by document type (`Annual Report`, `Interim Report`, `Quarterly Report`, `Announcement`, `Circular`, `Listing Document`), year (4-digit calendar year), and language (`en` / `zh` / `both`). Each entry SHALL include `doc_id`, `title`, `form`, `published` (ISO-8601 HKT date), `language`, `stock_code`, and `documents` (a list of `{lang, url}` PDF references). Results SHALL be capped at `limit` (default 20).

#### Scenario: List recent filings

- **WHEN** `list_filings(ticker_or_name="00700", limit=5)` is called
- **THEN** it returns at most 5 entries, each with a `doc_id` and at least one `documents[].url` pointing to `hkexnews.hk`

#### Scenario: Filter by form type

- **WHEN** `list_filings(ticker_or_name="00700", form="Annual Report", limit=3)` is called
- **THEN** every returned entry has `form` equal to `"Annual Report"`

#### Scenario: Filter by year

- **WHEN** `list_filings(ticker_or_name="00700", year=2024, limit=10)` is called
- **THEN** every returned entry has a `published` date whose calendar year is `2024`

#### Scenario: Dual-language filings are collapsed

- **WHEN** HKEXnews returns separate English and Chinese filings for the same disclosure
- **THEN** they appear as a single result entry with two items in `documents` (`{lang:"en", url}`, `{lang:"zh", url}`)

### Requirement: get_filing fetches a single HKEXnews disclosure

The `get_filing(doc_id_or_url, detail="standard")` tool SHALL fetch one disclosure by its HKEXnews `doc_id` (or the canonical PDF URL) and return its metadata. The `detail` parameter SHALL control payload size: `"minimal"` returns metadata only; `"standard"` (default) adds the first ~50 KB of extracted PDF text plus the parsed cover page; `"full"` returns the full extracted text capped at ~200 KB with a `truncated: true` flag when the cap is hit.

#### Scenario: Fetch a filing by doc_id

- **WHEN** `get_filing(doc_id_or_url="<doc_id>")` is called
- **THEN** it returns `doc_id`, `title`, `form`, `published`, `stock_code`, and `documents`

#### Scenario: Fetch a filing by canonical URL

- **WHEN** `get_filing(doc_id_or_url="https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0820/2024082000123.pdf")` is called
- **THEN** it returns the same shape as the `doc_id` form, resolving the `doc_id` from the URL

#### Scenario: detail=standard returns truncated text

- **WHEN** `get_filing(doc_id_or_url="<doc_id>", detail="standard")` is called on a 100-page report
- **THEN** the response contains a `text` field no larger than ~50 KB and a `truncated: true` flag when applicable

#### Scenario: Unknown doc returns an error

- **WHEN** `get_filing(doc_id_or_url="not-a-real-id")` is called
- **THEN** it returns an `error` field indicating the filing could not be found

### Requirement: get_financials returns HK financial statements

The `get_financials(ticker_or_name, statement=None, period="annual")` tool SHALL return financial statements for an HK-listed company, backed by `akshare.stock_financial_hk_report_em`. When `statement` is omitted, the response SHALL contain three keys — `income_statement`, `balance_sheet`, `cashflow` — each with the dataframe-style shape `{columns: [...], data: [{...}, ...]}`. When `statement` is provided (one of `income_statement` / `balance_sheet` / `cashflow`), the response SHALL contain only that one key. `period` SHALL accept `"annual"` (default) or `"interim"`; HK does not file quarterly reports.

#### Scenario: All standard statements

- **WHEN** `get_financials(ticker_or_name="00700")` is called
- **THEN** the response contains `income_statement`, `balance_sheet`, and `cashflow`, each with `columns` and `data`

#### Scenario: Single statement

- **WHEN** `get_financials(ticker_or_name="00700", statement="income_statement")` is called
- **THEN** the response contains only `income_statement`

#### Scenario: Interim period

- **WHEN** `get_financials(ticker_or_name="00700", period="interim")` is called
- **THEN** the returned statements include interim (half-year) records, not annual

#### Scenario: akshare unavailable

- **WHEN** `get_financials` is called and `akshare` is not importable
- **THEN** it returns an `error` field with the hint `"install with: pip install akshare"`

#### Scenario: Ticker normalization

- **WHEN** `get_financials(ticker_or_name="0700.HK")` is called
- **THEN** the call succeeds with the same payload as `ticker_or_name="00700"` would produce

### Requirement: get_disclosure_calendar lists results-announcement dates

The `get_disclosure_calendar(ticker_or_name, kind=None, limit=10)` tool SHALL return upcoming or recent results-announcement and AGM dates for a HK-listed company. `kind` SHALL accept `"results"`, `"agm"`, or `None` (both). Each entry SHALL include `date` (ISO-8601 HKT), `kind`, `event`, and `stock_code`. The tool SHALL return an empty list (not an error) when no events are scheduled.

#### Scenario: Upcoming calendar entries

- **WHEN** `get_disclosure_calendar(ticker_or_name="00700", limit=3)` is called
- **THEN** it returns at most 3 entries, each with a `date` and a `kind` in `{"results", "agm"}`

#### Scenario: Filter by kind

- **WHEN** `get_disclosure_calendar(ticker_or_name="00700", kind="results")` is called
- **THEN** every returned entry has `kind` equal to `"results"`

#### Scenario: No scheduled events

- **WHEN** the calendar feed has no upcoming entries for the ticker
- **THEN** the tool returns `[]` (empty list), not an `error`

### Requirement: Failures return structured error dicts, not exceptions

Every tool SHALL catch network, parsing, and serialization failures and return a dict shaped `{"error": "<short message>", "hint": "<actionable next step>"}`. The server SHALL NOT propagate raw exceptions to the MCP client. Missing-dependency errors (`akshare`, `pypdf`) SHALL surface as `{"error": "<dep> is not installed", "hint": "pip install <dep>"}`.

#### Scenario: Network error becomes a structured error

- **WHEN** the HKEXnews endpoint returns a 5xx or times out
- **THEN** the tool returns `{"error": ..., "hint": ...}` rather than raising

#### Scenario: Missing dep becomes a structured error

- **WHEN** `pypdf` is not installed and `get_filing(detail="standard")` is called
- **THEN** the tool returns `{"error": "pypdf is not installed", "hint": "pip install pypdf"}`

### Requirement: hkreport-mcp ships an offline selfcheck and tests

The MCP SHALL include `selfcheck.py` (offline; HTTP and `akshare` mocked) and `test_hkreport.py` (offline pytest suite). The selfcheck SHALL verify that the server module imports, registers all five tools, and that each tool returns the documented success shape against mocked HKEXnews/`akshare` responses. Live network calls SHALL be gated behind an explicit `HKREPORT_LIVE=1` env var so CI does not hit external endpoints.

#### Scenario: selfcheck passes without network

- **WHEN** `uv run python selfcheck.py` is run with no network access
- **THEN** the selfcheck exits with status 0 and prints `OK` for each of the five tools

#### Scenario: pytest passes without network

- **WHEN** `uv run --with pytest python -m pytest test_hkreport.py -v -p no:logfire` is run with no network access
- **THEN** every test passes and no test hits a real HKEXnews or `akshare` endpoint

