## Why

The MCP fleet already covers Chinese markets (akshare), global/US market prices (yfinance), macro statistics (worldbank/cnstats), and open data portals (ckan) — but it has no way to query **SEC EDGAR**: company filings (10-K/10-Q/8-K), financial statements (XBRL), and insider trades. [EdgarTools](https://github.com/dgunning/edgartools) (PyPI `edgartools`, import `edgar`) is the canonical Python library for this. An `edgartools-mcp` fills the gap and completes the US-fundamentals coverage alongside yfinance's US-prices coverage.

## What Changes

- Add `mcp/edgartools-mcp/` — a FastMCP (stdio) server wrapping the `edgar` library with purpose-built tools (no registry/harness: edgartools' API is a small object model, not hundreds of flat functions, so the yfinance/akshare registry pattern does not fit).
- New tools: `get_company`, `list_filings`, `get_filing`, `get_financials`, `get_insider_trades`.
- Add `mcp/edgartools-mcp/pyproject.toml` (deps `fastmcp`, `edgartools`, `pandas`) and `.env`/`.env.example`.
- Register `edgartools-mcp` in root `.mcp.json` using the `uv run --directory <path> python server.py` invocation (parallel to `yfinance-mcp`).
- Follow the unified-env convention: load root `.env` first, then per-MCP `.env` with `override=True`.
- Update root `CLAUDE.md` "MCP Servers" section with the new `edgartools-mcp` entry.

## Capabilities

### New Capabilities
- `edgar-mcp-server`: FastMCP stdio server wrapping the `edgartools` library to expose SEC EDGAR company info, filings, financial statements, and insider trades as five purpose-built tools.

### Modified Capabilities
<!-- None. The new server is additive; it does not change existing MCP behavior. -->

## Impact

- **New code**: `mcp/edgartools-mcp/` (server.py, pyproject.toml, .env, .env.example).
- **Config**: root `.mcp.json` gains one entry; root `CLAUDE.md` gains one subsection.
- **Dependencies**: adds `edgartools` (and its transitive deps) to a self-contained venv under `mcp/edgartools-mcp/`. No change to `mcp/models/` or `mcp/daas.db` — this is a live-execution MCP like `yfinance-mcp`, not a registry/data-snapshot MCP.
- **External**: hits `data.sec.gov` / `efts.sec.gov` at runtime; SEC requires a descriptive `User-Agent`. The server SHALL set `EDGAR_USER_AGENT` from env (root `.env`).
- **No breaking changes** to existing MCPs, the dashboard, or the schema package.
