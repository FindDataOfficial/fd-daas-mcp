## Why

The MCP fleet covers Chinese markets (akshare), US/global prices (yfinance), SEC EDGAR (edgartools), and macro statistics (worldbank/cnstats) — but it has no way to query **EDINET**, Japan's official securities-disclosure system (有価証券報告書, quarterly reports, large-shareholding notices, tender offers). [edinet-tools](https://pypi.org/project/edinet-tools/) (import `edinet_tools`, v0.7.1, MIT) is the canonical Python library: typed parsers for all 42 EDINET document codes, entity lookup by ticker/法人番号, and document fetching. An `edinet-mcp` fills the Japan-fundamentals gap alongside edgartools' US-fundamentals coverage.

## What Changes

- Add `mcp/edinet-mcp/` — a FastMCP (stdio) server wrapping the `edinet_tools` library with purpose-built tools (no registry/harness: edinet-tools is a small object model, not a flat function catalog, so the akshare/yfinance registry pattern does not fit — same call as `edgartools-mcp`).
- New tools: `search_entities`, `get_entity`, `list_documents`, `get_document`, `supported_doc_types`.
- Add `mcp/edinet-mcp/pyproject.toml` (deps `fastmcp`, `edinet-tools`, `pandas`, `python-dotenv`) and `.env`/`.env.example` declaring `EDINET_API_KEY`.
- Register `edinet-mcp` in root `.mcp.json` using the `uv run --directory <path> python server.py` invocation (parallel to `yfinance-mcp`/`edgartools-mcp`).
- Follow the unified-env convention: load root `.env` first, then per-MCP `.env` with `override=True`.
- Update root `CLAUDE.md` "MCP Servers" section with the new `edinet-mcp` entry.

## Capabilities

### New Capabilities
- `edinet-mcp-server`: FastMCP stdio server wrapping the `edinet_tools` library to expose EDINET entity lookup, document listings, single-document parsing, and document-type metadata as five purpose-built tools.

### Modified Capabilities
<!-- None. The new server is additive; it does not change existing MCP behavior. -->

## Impact

- **New code**: `mcp/edinet-mcp/` (server.py, pyproject.toml, .env, .env.example).
- **Config**: root `.mcp.json` gains one entry; root `CLAUDE.md` gains one subsection.
- **Dependencies**: adds `edinet-tools` (and transitive `pandas`, `python-dateutil`, `chardet`, `python-dotenv`) to a self-contained venv under `mcp/edinet-mcp/`. No change to `mcp/models/` or `mcp/daas.db` — this is a live-execution MCP like `edgartools-mcp`/`yfinance-mcp`, not a registry/data-snapshot MCP.
- **External**: hits `api.edinet-fsa.go.jp` at runtime. EDINET requires an `EDINET_API_KEY` only for document *fetching* (the `documents()` and `fetch_document` paths); entity lookup and parsing work without a key. The server SHALL read `EDINET_API_KEY` from env and surface a clear error when a key-requiring tool is called without it.
- **No breaking changes** to existing MCPs, the dashboard, or the schema package.
