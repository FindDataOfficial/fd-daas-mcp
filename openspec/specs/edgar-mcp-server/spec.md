### Requirement: FastMCP edgartools server with five purpose-built tools

The system SHALL provide a FastMCP server at `mcp/edgartools-mcp/server.py` using stdio transport, exposing five tools: `get_company`, `list_filings`, `get_filing`, `get_financials`, and `get_insider_trades`, wrapping the `edgar` (EdgarTools) library. This follows the purpose-built pattern (like `daas-mcp`/`worldbank-mcp`), not the registry pattern, because `edgar` exposes an object model rather than a flat function catalog.

#### Scenario: Server starts and registers tools

- **WHEN** the server is started with `python3 server.py`
- **THEN** all five tools are registered and callable over stdio

#### Scenario: Server uses FastMCP stdio transport

- **WHEN** the server is started
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, matching the other MCPs

### Requirement: SEC identity is configured at startup

The server SHALL call `edgar.set_identity(...)` at module load using the `EDGAR_IDENTITY` environment variable (loaded from root `.env` first, then the per-MCP `.env` with `override=True`). If `EDGAR_IDENTITY` is unset, the server SHALL still start but each tool SHALL return a clear `error` advising the user to set `EDGAR_IDENTITY`, rather than emitting unauthenticated SEC requests.

#### Scenario: Identity loaded from env

- **WHEN** the server starts with `EDGAR_IDENTITY` set in the environment
- **THEN** `edgar.set_identity` is called with that value before any tool runs

#### Scenario: Missing identity surfaces a clear error

- **WHEN** any tool is called and `EDGAR_IDENTITY` was never set
- **THEN** the tool returns an `error` field instructing the user to set `EDGAR_IDENTITY` in `.env`

### Requirement: get_company returns company facts

The `get_company(ticker_or_cik)` tool SHALL return a JSON-serializable dict of company facts — including name, CIK, tickers, SIC, state, and description — by constructing `edgar.Company(ticker_or_cik)` and serializing its summary fields.

#### Scenario: Lookup by ticker

- **WHEN** `get_company(ticker_or_cik="AAPL")` is called and `edgar` is installed
- **THEN** it returns a dict with `name`, `cik`, and `tickers` fields for Apple Inc.

#### Scenario: Missing edgartools returns a clear error

- **WHEN** `get_company` is called and `edgar` is not importable
- **THEN** it returns an `error` field with an install hint (`pip install edgartools`)

### Requirement: list_filings lists a company's filings

The `list_filings(ticker_or_cik, form=None, limit=20)` tool SHALL list filings for a company via `edgar.Company(ticker_or_cik).get_filings(form=form)`, capped by `limit`, returning a list of `{accession_number, form, company, filed, primary_document, url}` dicts.

#### Scenario: List recent filings

- **WHEN** `list_filings(ticker_or_cik="AAPL", limit=5)` is called
- **THEN** it returns at most 5 filing entries, each with an `accession_number` and `form`

#### Scenario: Filter by form type

- **WHEN** `list_filings(ticker_or_cik="AAPL", form="10-K", limit=3)` is called
- **THEN** every returned entry has `form` equal to `10-K`

### Requirement: get_filing parses a single filing

The `get_filing(accession_number, ticker_or_cik=None, detail="standard")` tool SHALL fetch a specific filing (by accession number, optionally scoped to a ticker/CIK) and return its metadata plus a parsed-object summary from `filing.obj()`, with `detail` controlling payload size (`minimal`, `standard`, `full`).

#### Scenario: Fetch a filing by accession

- **WHEN** `get_filing(accession_number="<accession>", ticker_or_cik="AAPL")` is called
- **THEN** it returns `accession_number`, `form`, `company`, `filed`, and a parsed `data_object_type`/`context` summary

#### Scenario: Unknown accession returns an error

- **WHEN** `get_filing(accession_number="invalid")` is called
- **THEN** it returns an `error` field indicating the filing could not be found

### Requirement: get_financials returns financial statements

The `get_financials(ticker_or_cik, statement=None, period="annual")` tool SHALL return financial statements for a company. When `statement` is omitted, it SHALL return the three standard statements (income, balance sheet, cash flow); when `statement` is provided (e.g. `income_statement`, `balance_sheet`, `cashflow`), it SHALL return only that one. Statements SHALL be serialized as dataframe-style `{columns, data}` records.

#### Scenario: All standard statements

- **WHEN** `get_financials(ticker_or_cik="AAPL")` is called
- **THEN** it returns income_statement, balance_sheet, and cashflow entries, each with `columns` and `data`

#### Scenario: Single statement

- **WHEN** `get_financials(ticker_or_cik="AAPL", statement="income_statement")` is called
- **THEN** it returns only the income statement

### Requirement: get_insider_trades returns Form 4 transactions

The `get_insider_trades(ticker_or_cik, limit=20)` tool SHALL return recent insider transactions derived from Form 4 filings via `edgar.Company(ticker_or_cik).get_filings(form="4").head(limit)`, each parsed with `.obj()` and serialized to `{owner, reported_at, type, shares, value}` where available.

#### Scenario: Recent insider trades

- **WHEN** `get_insider_trades(ticker_or_cik="AAPL", limit=5)` is called
- **THEN** it returns at most 5 transaction entries, each with an `owner` field

### Requirement: Results are JSON-serialized via a shared serializer

The server SHALL include a `_serialize()` helper that converts edgar results to JSON-serializable dicts: `pandas.DataFrame` → `{type:"dataframe", shape, columns, data}` (NaN→null), `pandas.Series` → `{type:"series",...}`, objects with `__dict__` → flattened dict (depth-capped), and a `str()` fallback. Every tool SHALL return its result through this helper.

#### Scenario: DataFrame result is serialized

- **WHEN** a tool returns a `pandas.DataFrame`
- **THEN** `_serialize` produces a dict with `type:"dataframe"`, `columns`, and `data` as records

#### Scenario: Non-serializable object falls back to string

- **WHEN** a tool returns an object that cannot be dict-flattened
- **THEN** `_serialize` returns `{type:"scalar", data: str(obj)}`

### Requirement: Server packaged and registered in .mcp.json

The system SHALL ship `mcp/edgartools-mcp/pyproject.toml` (deps `fastmcp>=2.0`, `edgartools>=2.0`, `pandas>=1.0`, `python-dotenv>=1.0`, `requires-python>=3.10`), `.env`/`.env.example` declaring `EDGAR_IDENTITY`, and root `.mcp.json` SHALL register `edgartools-mcp` using the `uv run --directory <path> python server.py` invocation, parallel to the `yfinance-mcp` entry. Root `CLAUDE.md` SHALL document the new `mcp/edgartools-mcp/` subsection.

#### Scenario: pyproject declares dependencies

- **WHEN** `mcp/edgartools-mcp/pyproject.toml` is inspected
- **THEN** it declares `fastmcp>=2.0`, `edgartools>=2.0`, `pandas>=1.0`, and `python-dotenv>=1.0`, with `requires-python>=3.10`, and does NOT declare `sqlalchemy` or `click`

#### Scenario: .mcp.json registers the server

- **WHEN** root `.mcp.json` is inspected
- **THEN** it contains an `edgartools-mcp` entry with `type: stdio` and a `uv run --directory ... python server.py` command, parallel to the `yfinance-mcp` entry

#### Scenario: dotenv loads root env first

- **WHEN** the server starts
- **THEN** it loads the root `.env` before its own `.env` with `override=True`, matching the unified-env convention used by the other MCPs

#### Scenario: CLAUDE.md documents the new MCP

- **WHEN** root `CLAUDE.md` is inspected
- **THEN** it contains an `mcp/edgartools-mcp/` subsection under "MCP Servers" describing the entry, deps, and tools
