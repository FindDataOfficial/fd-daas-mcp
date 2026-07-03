## 1. Scaffold the MCP directory

- [x] 1.1 Create `mcp/dartlab-mcp/` with `server.py`, `pyproject.toml`, `.env`, `.env.example`
- [x] 1.2 Write `pyproject.toml`: name `dartlab-mcp`, `requires-python>=3.12`, deps `fastmcp>=2.0`, `dartlab>=0.10`, `pandas>=1.0`, `python-dotenv>=1.0` (no `sqlalchemy`/`click`)
- [x] 1.3 Write `.env.example` and `.env` declaring an optional `DART_API_KEY=` (comment: free key from opendart.fss.or.kr; not required for basic use)

## 2. server.py — bootstrap, serializer

- [x] 2.1 Add unified-env dotenv load (root `.env` first, then per-MCP `.env` with `override=True`), matching `edgartools-mcp/server.py`
- [x] 2.2 Create `app = FastMCP(name="dartlab-mcp")`
- [x] 2.3 Add `_import_dartlab()` lazy-import helper returning `(module, error_dict)` — error dict says `pip install dartlab`
- [x] 2.4 Port `_serialize(result, depth, max_depth)` from `edgartools-mcp/server.py` verbatim: DataFrame→`{type:"dataframe",shape,columns,data}` (NaN→null), Series→`{type:"series",...}`, `__dict__`-bearing→depth-capped flattened dict, else `{type:"scalar", data:str(obj)}`
- [x] 2.5 Add `if __name__ == "__main__": app.run(transport="stdio", show_banner=False)`
- [x] 2.6 Do NOT gate tools on `DART_API_KEY` — basic use is keyless. Forward the env var by relying on dartlab's own env read (confirm exact var name against `dartlab.OpenDart` source; default `DART_API_KEY`)

## 3. server.py — the six tools

- [x] 3.1 `company_panel(ticker, topic=None, freq=None)`: `dartlab.Company(ticker).panel(topic, freq=freq)` — pass `freq` only when provided; pass `topic` through verbatim (uppercase=normalized, lowercase=native); serialize via `_serialize`
- [x] 3.2 `panel_search(ticker, query)`: `dartlab.Company(ticker).panel.search(query)`; serialize hits
- [x] 3.3 `list_filings(ticker, limit=20)`: `dartlab.Company(ticker).filings()` sliced to `limit` (cap 200); return `{count, filings}` with viewer links
- [x] 3.4 `get_credit(ticker)`: `dartlab.Company(ticker).credit("등급")`; serialize
- [x] 3.5 `analyze(ticker, kind="financial", aspect=None)`: `dartlab.Company(ticker).analysis(kind, aspect)`; pass `aspect` only when provided; serialize
- [x] 3.6 `scan(category, metric=None)`: `dartlab.scan(category, metric)`; pass `metric` only when provided; serialize
- [x] 3.7 Every tool: lazy `import dartlab` via `_import_dartlab()`, wrap calls in try/except returning `{"error": f"{type(e).__name__}: {e}"}`, route results through `_serialize`

## 4. Wire into the repo

- [x] 4.1 Add `dartlab-mcp` entry to root `.mcp.json`: `type: stdio`, command `uv run --directory /Users/chengsishi/code/cli-anything/mcp/dartlab-mcp python server.py`, parallel to `edgartools-mcp`
- [x] 4.2 Add `mcp/dartlab-mcp/` subsection to root `CLAUDE.md` under "MCP Servers": entry, deps, `requires-python>=3.12`, optional `DART_API_KEY`, six tools, purpose-built rationale

## 5. Verify

- [x] 5.1 `cd mcp/dartlab-mcp && uv sync` succeeds (creates an isolated 3.12 venv)
- [x] 5.2 `python3 server.py` starts without error
- [x] 5.3 Smoke-test each tool: `company_panel("005930")`, `company_panel("005930","IS")`, `company_panel("AAPL")`, `panel_search("005930","재고")`, `list_filings("005930",limit=3)`, `get_credit("005930")`, `analyze("005930")`, `scan("ratio","roe")`; confirm JSON-serializable output
- [x] 5.4 Add a small `__main__` self-check (opt-in, guarded by `dartlab` import) exercising `company_panel("005930","IS")`, so non-trivial logic has a runnable check
