## ADDED Requirements

### Requirement: FastMCP dartlab server with six purpose-built tools

The system SHALL provide a FastMCP server at `mcp/dartlab-mcp/server.py` using stdio transport, exposing six tools: `company_panel`, `panel_search`, `list_filings`, `get_credit`, `analyze`, and `scan`, wrapping the `dartlab` library. This follows the purpose-built pattern (like `edgartools-mcp`), not the registry pattern, because `dartlab` exposes an object model (`Company(ticker)` → `.panel()`/`.credit()`/`.analysis()`) rather than a flat function catalog.

#### Scenario: Server starts and registers tools

- **WHEN** the server is started with `python3 server.py`
- **THEN** all six tools are registered and callable over stdio

#### Scenario: Server uses FastMCP stdio transport

- **WHEN** the server is started
- **THEN** it runs FastMCP with `transport="stdio"` and `show_banner=False`, matching the other MCPs

### Requirement: Optional DART API key is passed through without gating

The server SHALL load `DART_API_KEY` from the environment (root `.env` first, then the per-MCP `.env` with `override=True`) and forward it to dartlab. The server SHALL NOT gate any tool on `DART_API_KEY` — basic use relies on dartlab's pre-built keyless dataset. Tools SHALL function without the key set.

#### Scenario: Keyless basic use works

- **WHEN** the server starts with no `DART_API_KEY` set and `company_panel` is called
- **THEN** the tool executes against dartlab's pre-built dataset and does not return a key-missing error

#### Scenario: Key is forwarded when present

- **WHEN** the server starts with `DART_API_KEY` set in the environment
- **THEN** the value is available to dartlab for raw re-collection without any extra tool configuration

### Requirement: company_panel returns a company's disclosure grid or a named statement

The `company_panel(ticker, topic=None, freq=None)` tool SHALL construct `dartlab.Company(ticker)` and call `.panel(topic, freq=freq)` (passing `freq` only when provided). When `topic` is None it SHALL return the full disclosure grid; when `topic` is provided (e.g. `IS`, `BS`, `ratios`, `사업`, `inventory`) it SHALL return that single panel. The `topic` string SHALL be passed through verbatim — uppercase topics return finance-normalized numbers, lowercase return native as-reported figures.

#### Scenario: Full disclosure grid

- **WHEN** `company_panel(ticker="005930")` is called and `dartlab` is installed
- **THEN** it returns a serialized disclosure grid for Samsung Electronics

#### Scenario: Named income statement

- **WHEN** `company_panel(ticker="005930", topic="IS")` is called
- **THEN** it returns the finance-normalized income statement panel

#### Scenario: US ticker works through the same interface

- **WHEN** `company_panel(ticker="AAPL")` is called
- **THEN** it returns a panel for Apple via the identical `Company` interface

#### Scenario: Missing dartlab returns a clear error

- **WHEN** `company_panel` is called and `dartlab` is not importable
- **THEN** it returns an `error` field with an install hint (`pip install dartlab`)

### Requirement: panel_search does full-text search within a company's filings

The `panel_search(ticker, query)` tool SHALL construct `dartlab.Company(ticker)` and call `.panel.search(query)`, returning serialized full-text hits within that company's filings.

#### Scenario: Search by Korean keyword

- **WHEN** `panel_search(ticker="005930", query="재고")` is called
- **THEN** it returns matching in-filing text hits for Samsung Electronics

### Requirement: list_filings returns raw filing links

The `list_filings(ticker, limit=20)` tool SHALL construct `dartlab.Company(ticker)` and call `.filings()`, slicing to `limit`, returning a list of filing entries with links to the DART viewer.

#### Scenario: List recent filings

- **WHEN** `list_filings(ticker="005930", limit=5)` is called
- **THEN** it returns at most 5 filing entries

### Requirement: get_credit returns the credit rating

The `get_credit(ticker)` tool SHALL construct `dartlab.Company(ticker)` and call `.credit("등급")`, returning the serialized credit rating (dCR grade, healthScore 0-100, PD estimate where available).

#### Scenario: Credit rating for a company

- **WHEN** `get_credit(ticker="005930")` is called
- **THEN** it returns a credit-rating object including a grade field

### Requirement: analyze returns deep analysis

The `analyze(ticker, kind="financial", aspect=None)` tool SHALL construct `dartlab.Company(ticker)` and call `.analysis(kind, aspect)`, returning the serialized deep-analysis result. When `aspect` is None it SHALL return the whole `kind` analysis; when provided (e.g. `aspect="수익성"`) it SHALL return that aspect.

#### Scenario: Full financial analysis

- **WHEN** `analyze(ticker="005930", kind="financial")` is called
- **THEN** it returns the serialized financial analysis for Samsung Electronics

#### Scenario: Single aspect

- **WHEN** `analyze(ticker="005930", kind="financial", aspect="수익성")` is called
- **THEN** it returns only the profitability aspect

### Requirement: scan returns a cross-sectional market scan

The `scan(category, metric=None)` tool SHALL call `dartlab.scan(category, metric)` (passing `metric` only when provided), returning a serialized cross-sectional scan across listed companies (e.g. `category="ratio"`, `metric="roe"`; `category="governance"`).

#### Scenario: Scan a ratio across the market

- **WHEN** `scan(category="ratio", metric="roe")` is called
- **THEN** it returns a cross-sectional scan of ROE across listed companies

#### Scenario: Scan a category with no metric

- **WHEN** `scan(category="governance")` is called
- **THEN** it returns the governance scan across listed companies

### Requirement: Results are JSON-serialized via a shared serializer

The server SHALL include a `_serialize()` helper that converts dartlab results to JSON-serializable dicts: `pandas.DataFrame` → `{type:"dataframe", shape, columns, data}` (NaN→null), `pandas.Series` → `{type:"series",...}`, objects with `__dict__` → flattened dict (depth-capped), and a `str()` fallback. Every tool SHALL return its result through this helper.

#### Scenario: DataFrame result is serialized

- **WHEN** a tool returns a `pandas.DataFrame`
- **THEN** `_serialize` produces a dict with `type:"dataframe"`, `columns`, and `data` as records

#### Scenario: Non-serializable object falls back to string

- **WHEN** a tool returns an object that cannot be dict-flattened
- **THEN** `_serialize` returns `{type:"scalar", data: str(obj)}`

### Requirement: Server packaged and registered in .mcp.json

The system SHALL ship `mcp/dartlab-mcp/pyproject.toml` (deps `fastmcp>=2.0`, `dartlab>=0.10`, `pandas>=1.0`, `python-dotenv>=1.0`, `requires-python>=3.12`), `.env`/`.env.example` declaring an optional `DART_API_KEY`, and root `.mcp.json` SHALL register `dartlab-mcp` using the `uv run --directory <path> python server.py` invocation, parallel to the `edgartools-mcp` entry. Root `CLAUDE.md` SHALL document the new `mcp/dartlab-mcp/` subsection.

#### Scenario: pyproject declares dependencies and Python floor

- **WHEN** `mcp/dartlab-mcp/pyproject.toml` is inspected
- **THEN** it declares `fastmcp>=2.0`, `dartlab>=0.10`, `pandas>=1.0`, and `python-dotenv>=1.0`, with `requires-python>=3.12`, and does NOT declare `sqlalchemy` or `click`

#### Scenario: .mcp.json registers the server

- **WHEN** root `.mcp.json` is inspected
- **THEN** it contains a `dartlab-mcp` entry with `type: stdio` and a `uv run --directory ... python server.py` command, parallel to the `edgartools-mcp` entry

#### Scenario: dotenv loads root env first

- **WHEN** the server starts
- **THEN** it loads the root `.env` before its own `.env` with `override=True`, matching the unified-env convention used by the other MCPs

#### Scenario: CLAUDE.md documents the new MCP

- **WHEN** root `CLAUDE.md` is inspected
- **THEN** it contains an `mcp/dartlab-mcp/` subsection under "MCP Servers" describing the entry, deps, optional key, and tools
