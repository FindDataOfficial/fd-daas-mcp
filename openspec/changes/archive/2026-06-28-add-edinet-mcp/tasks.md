## 1. Scaffold the MCP directory

- [x] 1.1 Create `mcp/edinet-mcp/` with `server.py`, `pyproject.toml`, `.env`, `.env.example`
- [x] 1.2 Write `pyproject.toml`: name `edinet-mcp`, `requires-python>=3.10`, deps `fastmcp>=2.0`, `edinet-tools>=0.7`, `pandas>=1.0`, `python-dotenv>=1.0` (no `sqlalchemy`/`click`)
- [x] 1.3 Write `.env.example` and `.env` declaring `EDINET_API_KEY=` (with a comment: keyless for entity tools, required for document tools)

## 2. server.py — bootstrap, env, serializer

- [x] 2.1 Add unified-env dotenv load (root `.env` first, then per-MCP `.env` with `override=True`), matching `edgartools-mcp/server.py`
- [x] 2.2 Create `app = FastMCP(name="edinet-mcp")`
- [x] 2.3 At module load, read `EDINET_API_KEY` into a module-level variable; do not abort startup if unset (entity tools work keyless)
- [x] 2.4 Implement `_serialize(result)` helper: `to_dict()`-bearing objects → call it; DataFrame→`{type:"dataframe",shape,columns,data}` (NaN→null); Series→`{type:"series",...}`; dataclass/`__dict__` objects → depth-capped flattened dict; list/tuple → serialize elements; else `str()`
- [x] 2.5 Add a `_require_api_key()` guard returning an `error` dict when `EDINET_API_KEY` is unset, called at the top of `list_documents` and `get_document`
- [x] 2.6 Add `if __name__ == "__main__": app.run(transport="stdio", show_banner=False)`

## 3. server.py — the five tools

- [x] 3.1 `search_entities(query, limit=10)`: `edinet_tools.search(query, limit=limit)`, serialize each match (edinet_code, name, english_name, ...)
- [x] 3.2 `get_entity(ticker_or_code)`: if input is a 13-digit number → `edinet_tools.entity_by_corporate_number(...)`; else `edinet_tools.entity(...)`; serialize name/edinet_code/corporate_number/sector/...
- [x] 3.3 `list_documents(date, doc_type=None, limit=50)`: guard with `_require_api_key()`; `edinet_tools.documents(date)`, filter by `doc_type` if given, slice to `limit`; return `{doc_id, doc_type_code, filer_name, ...}` per filing
- [x] 3.4 `get_document(doc_id, doc_type_code=None, detail="standard")`: guard with `_require_api_key()`; fetch + `doc.parse()`; return `to_dict()`; honor `detail` (`minimal` excludes `raw_fields`/`text_blocks`); return `error` on fetch/parse failure
- [x] 3.5 `supported_doc_types()`: `edinet_tools.supported_doc_types()`, serialize the list of all 42 doc-type codes with names/descriptions (keyless)

## 4. Wire into the repo

- [x] 4.1 Add `edinet-mcp` entry to root `.mcp.json`: `type: stdio`, command `uv run --directory /Users/chengsishi/code/cli-anything/mcp/edinet-mcp python server.py`, parallel to `edgartools-mcp`
- [x] 4.2 Add `mcp/edinet-mcp/` subsection to root `CLAUDE.md` under "MCP Servers": entry, deps, `EDINET_API_KEY` env (keyless entity tools vs key-required document tools), five tools

## 5. Verify

- [x] 5.1 `cd mcp/edinet-mcp && uv sync` succeeds
- [x] 5.2 `python3 server.py` starts without error
- [x] 5.3 Smoke-test keyless tools: `supported_doc_types()` (expect ~42 types), `search_entities(query="bank", limit=5)`, `get_entity(ticker_or_code="7203")` (Toyota); confirm JSON-serializable output
- [ ] 5.4 Smoke-test key-required tools with a valid `EDINET_API_KEY`: pick a recent date with `list_documents(date=..., limit=3)`, then `get_document(doc_id=..., detail="minimal")` and `detail="standard"`; confirm `minimal` omits `raw_fields`/`text_blocks`
- [x] 5.5 Confirm `list_documents`/`get_document` return a clear `error` when `EDINET_API_KEY` is unset
- [x] 5.6 Add a small `__main__` self-check (opt-in, guarded by `edinet_tools` import) exercising one keyless tool (`supported_doc_types` or `get_entity`), so non-trivial logic has a runnable check
