## 1. Scaffold the MCP directory

- [x] 1.1 Create `mcp/edgartools-mcp/` with `server.py`, `pyproject.toml`, `.env`, `.env.example`
- [x] 1.2 Write `pyproject.toml`: name `edgartools-mcp`, `requires-python>=3.10`, deps `fastmcp>=2.0`, `edgartools>=2.0`, `pandas>=1.0`, `python-dotenv>=1.0` (no `sqlalchemy`/`click`)
- [x] 1.3 Write `.env.example` and `.env` declaring `EDGAR_IDENTITY=` (with a comment showing the `"Name email@domain"` format)

## 2. server.py — bootstrap, identity, serializer

- [x] 2.1 Add unified-env dotenv load (root `.env` first, then per-MCP `.env` with `override=True`), matching `yfinance-mcp/server.py`
- [x] 2.2 Create `app = FastMCP(name="edgartools-mcp")`
- [x] 2.3 At module load, read `EDGAR_IDENTITY` from env and call `edgar.set_identity(...)` if set; stash a module-level flag indicating whether identity is configured
- [x] 2.4 Implement `_serialize(result)` helper: DataFrame→`{type:"dataframe",shape,columns,data}` (NaN→null), Series→`{type:"series",...}`, `__dict__`-bearing objects→depth-capped flattened dict, else `{type:"scalar", data:str(obj)}`
- [x] 2.5 Add a `_require_identity()` guard returning an `error` dict if identity is unset, called at the top of each tool
- [x] 2.6 Add `if __name__ == "__main__": app.run(transport="stdio", show_banner=False)`

## 3. server.py — the five tools

- [x] 3.1 `get_company(ticker_or_cik)`: build `edgar.Company(...)`, serialize name/cik/tickers/sic/state/description (and market caps if available)
- [x] 3.2 `list_filings(ticker_or_cik, form=None, limit=20)`: `Company(...).get_filings(form=form)`, slice to `limit`, return `{accession_number, form, company, filed, primary_document, url}` per filing
- [x] 3.3 `get_filing(accession_number, ticker_or_cik=None, detail="standard")`: fetch filing (scoped by ticker/CIK if given), return metadata + `filing.obj()` summary; honor `detail` (`minimal`/`standard`/`full`); return `error` on not-found
- [x] 3.4 `get_financials(ticker_or_cik, statement=None, period="annual")`: use `Company(...).get_financials()` (and/or latest 10-K `filing.xbrl().statements`); return the three standard statements when `statement` is None, else only the named one; serialize via `_serialize`
- [x] 3.5 `get_insider_trades(ticker_or_cik, limit=20)`: `Company(...).get_filings(form="4").head(limit)`, parse each `.obj()`, serialize to `{owner, reported_at, type, shares, value}` where available

## 4. Wire into the repo

- [x] 4.1 Add `edgartools-mcp` entry to root `.mcp.json`: `type: stdio`, command `uv run --directory /Users/chengsishi/code/cli-anything/mcp/edgartools-mcp python server.py`, parallel to `yfinance-mcp`
- [x] 4.2 Add `mcp/edgartools-mcp/` subsection to root `CLAUDE.md` under "MCP Servers": entry, deps, identity env, five tools

## 5. Verify

- [x] 5.1 `cd mcp/edgartools-mcp && uv sync` succeeds
- [x] 5.2 `python3 server.py` starts without error (or fails fast with a clear message if `EDGAR_IDENTITY` unset)
- [x] 5.3 Smoke-test each tool with a stable ticker (AAPL): `get_company`, `list_filings(limit=3)`, `list_filings(form="10-K", limit=1)` → `get_filing`, `get_financials`, `get_insider_trades(limit=3)`; confirm JSON-serializable output
- [x] 5.4 Add a small `__main__` self-check (opt-in, guarded by `edgartools` import) exercising one tool, so non-trivial logic has a runnable check
