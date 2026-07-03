## Why

The MCP fleet covers Chinese markets (akshare), global/US prices (yfinance), US SEC fundamentals (edgartools), and macro/open-data portals (worldbank/cnstats/ckan) — but it has no way to query **Korea DART**: corporate filings, normalized financial statements, business reports, credit ratings, and cross-sectional scans of all KRX-listed companies. [dartlab](https://pypi.org/project/dartlab/) (Apache-2.0) is the canonical Python library for this, normalizing DART (and US EDGAR) filings into one comparable `Company(ticker)` object model. A `dartlab-mcp` fills the Korea-fundamentals gap and complements the existing US-fundamentals coverage from `edgartools-mcp`.

dartlab ships a built-in `dartlab mcp` server, but it exposes *generic agent* tools (`ask`, `RunPython`, `WebSearch`, `ReadSkill`, …), not its financial-data surface. This MCP instead wraps the data API directly — `Company.panel()`, `.credit()`, `.analysis()`, `scan()`, etc. — so an agent calls typed, documented tools instead of free-form Python.

## What Changes

- Add `mcp/dartlab-mcp/` — a FastMCP (stdio) server wrapping the `dartlab` library with purpose-built tools. No registry/harness: dartlab's API is a small object model (`Company(ticker)` → `.panel()`, `.credit()`, `.analysis()`; top-level `scan`/`compare`/`gather`), not a flat function catalog, so the yfinance/akshare registry pattern does not fit — same decision as `edgartools-mcp`.
- New tools: `company_panel`, `panel_search`, `list_filings`, `get_credit`, `analyze`, `scan`.
- Add `mcp/dartlab-mcp/pyproject.toml` (deps `fastmcp`, `dartlab`, `pandas`, `python-dotenv`; `requires-python>=3.12` — dartlab's own floor) and `.env`/`.env.example` (optional `DART_API_KEY`).
- Register `dartlab-mcp` in root `.mcp.json` via `uv run --directory <path> python server.py`, parallel to `edgartools-mcp`.
- Follow the unified-env convention: load root `.env` first, then per-MCP `.env` with `override=True`.
- Update root `CLAUDE.md` "MCP Servers" section with the new `dartlab-mcp` entry.

## Capabilities

### New Capabilities
- `dartlab-mcp-server`: FastMCP stdio server wrapping the `dartlab` library to expose Korea DART (and US EDGAR) company panels, filing text search, filing links, credit ratings, deep analysis, and market-wide scans as six purpose-built tools.

### Modified Capabilities
<!-- None. The new server is additive; it does not change existing MCP behavior. -->

## Impact

- **New code**: `mcp/dartlab-mcp/` (server.py, pyproject.toml, .env, .env.example).
- **Config**: root `.mcp.json` gains one entry; root `CLAUDE.md` gains one subsection.
- **Dependencies**: adds `dartlab` (and transitive deps) to a self-contained venv under `mcp/dartlab-mcp/`. No change to `mcp/models/` or `mcp/daas.db` — live-execution MCP like `edgartools-mcp`/`yfinance-mcp`, not a registry/data-snapshot MCP.
- **Python floor**: dartlab requires Python ≥3.12. Each MCP runs in its own uv venv, so this is isolated to `mcp/dartlab-mcp/` and does not affect the project's 3.10+ baseline.
- **External**: pre-built parquet auto-downloads from HuggingFace to a local cache on first use; EDGAR data fetched live from SEC. No key required for basic use. An optional `DART_API_KEY` (free, from opendart.fss.or.kr) enables raw re-collection via `dartlab.OpenDart()` — surfaced as an env passthrough, not a gate.
- **No breaking changes** to existing MCPs, the dashboard, or the schema package.
