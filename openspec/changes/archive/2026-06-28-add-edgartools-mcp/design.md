## Context

The MCP fleet wraps financial-data libraries behind a uniform FastMCP (stdio) interface. Two patterns exist today:

1. **Registry + live-call** (`akshare-mcp`, `yfinance-mcp`): a `*-agent-harness` ships a curated SQLite registry of hundreds of flat functions; the MCP exposes `search_functions` / `list_functions` / `get_function_info` / `list_categories` / `call_<lib>_function`. This fits libraries whose surface is many flat callables.
2. **Purpose-built** (`daas-mcp`, `worldbank-mcp`, `ckan-mcp`): a standalone MCP with a handful of domain-shaped tools, no registry.

EdgarTools (PyPI `edgartools`, import `edgar`) exposes a small **object model**, not flat functions: `Company(ticker)` → `.get_filings()`, `.get_financials()`; `find(form=, ticker=)`; `Filing.obj()` / `.xbrl()`. The registry pattern does not fit — there is nothing to enumerate. The purpose-built pattern is the correct shape.

The library is live-execution (hits `data.sec.gov` / `efts.sec.gov`), like `yfinance-mcp`. It does not write to `mcp/daas.db` and does not need `mcp/models/`.

## Goals / Non-Goals

**Goals:**
- Five purpose-built tools that cover the common EDGAR workflows: company facts, filings list, single-filing parse, financial statements, insider trades.
- Self-contained `mcp/edgartools-mcp/` venv, registered in `.mcp.json`, following the unified-env convention.
- Correct SEC identity handling (descriptive `User-Agent` is mandatory; SEC will 403 otherwise).
- Robust serialization of edgar's rich objects (DataFrames, dataclasses, `Filing`/`Financials` objects) to JSON.

**Non-Goals:**
- No `edgartools-agent-harness` CLI, no curated registry, no `mcp/models/` tables. (YAGNI — the library is the registry.)
- No writes to `mcp/daas.db`, no leader-mcp registration, no dashboard datasource. (Additive; can be layered later if discovery is needed.)
- No full-text filing search beyond `find(form=, ticker=)`; no bulk downloads.
- No XBRL dimensional/footnote deep-dive beyond the standard statements.

## Decisions

### Decision 1: Purpose-built tools, not a registry/harness
**Choice:** Five domain tools (`get_company`, `list_filings`, `get_filing`, `get_financials`, `get_insider_trades`).
**Why:** edgar's API is an object model (`Company`, `Filing`, `Financials`), not a flat function catalog. A registry of "ticker_history"-style entries would be fabricated ceremony.
**Alternative considered:** Mirror `yfinance-mcp` exactly with a harness + `call_edgar_function(name, params_json)` generic dispatcher. Rejected — there is no natural flat namespace to dispatch on, and a single generic dispatcher loses the parameter validation and docstrings that make purpose-built tools useful to an agent.

### Decision 2: Identity via `EDGAR_IDENTITY` env, set explicitly at startup
**Choice:** Root `.env` holds `EDGAR_IDENTITY="Name email@domain"`. At startup the server calls `edgar.set_identity(os.environ["EDGAR_IDENTITY"])` if present. Per-MCP `.env` may override.
**Why:** SEC mandates a descriptive `User-Agent`; the library reads `EDGAR_IDENTITY` automatically, but calling `set_identity()` explicitly fails fast with a clear message if it is missing, rather than silently 403-ing on the first call.
**Alternative:** `EDGAR_USER_AGENT`. Rejected — that is not the library's env-var name; `EDGAR_IDENTITY` is what `edgar` natively reads (`"Name email"` form, parsed into a UA header). *(This corrects the `EDGAR_USER_AGENT` mention in proposal.md.)*

### Decision 3: Tools return JSON-serializable dicts via a shared serializer
**Choice:** A `_serialize()` helper converts edgar results to dicts: `pd.DataFrame` → `{type:"dataframe", shape, columns, data: records}` (NaN→null), `pd.Series` → `{type:"series",...}`, dataclasses/`__dict__`-able objects → flattened dict, `Filing` → `{accession_number, form, company, filed, ...}`, fall back to `str()`.
**Why:** edgar returns rich objects (`Filing`, `Financials`, `TenK`, pandas). MCP tool results must be JSON. Mirrors `yfinance-mcp`'s `_serialize_result`.
**Alternative:** return raw `repr()`. Rejected — unusable for an agent consumer.

### Decision 4: Tool signatures (the contract)
| Tool | Params | Returns |
|---|---|---|
| `get_company` | `ticker_or_cik: str` | name, cik, tickers, sic, description, market caps, state |
| `list_filings` | `ticker_or_cik: str`, `form: Optional[str]=None`, `limit: int=20` | list of `{accession_number, form, company, filed, primary_document, url}` |
| `get_filing` | `accession_number: str`, `ticker_or_cik: Optional[str]=None`, `detail: str="standard"` | filing metadata + `obj()` parsed summary (financials/sections/transactions by form type) |
| `get_financials` | `ticker_or_cik: str`, `statement: Optional[str]=None` (e.g. `income_statement`, `balance_sheet`, `cashflow`), `period: str="annual"` | statements as dataframe records; if `statement` omitted, return the standard three |
| `get_insider_trades` | `ticker_or_cik: str`, `limit: int=20` | list of Form-4 derived transactions `{owner, reported_at, type, shares, value}` |

**Why these five:** they map 1:1 to the workflows in the edgartools docs (Company, get_filings, find/filing.obj, get_financials/xbrl, Form-4 ownership). `detail` mirrors the library's `edgar_filing` MCP design (`minimal`/`standard`/`full`).

### Decision 5: Lazy import of `edgar` inside tool bodies
**Choice:** `import edgar` happens inside each tool (and `set_identity` at module load), not at top of file.
**Why:** Matches `yfinance-mcp` (lazy `importlib.import_module("yfinance")`). Keeps the server importable/fast even if `edgartools` is not yet installed, and lets tools return a clear `{"error": "edgartools is not installed", "hint": ...}`.

### Decision 6: Packaging mirrors `yfinance-mcp`
**Choice:** `mcp/edgartools-mcp/pyproject.toml` with `fastmcp>=2.0`, `edgartools>=2.0`, `pandas>=1.0`, `python-dotenv>=1.0`. `.mcp.json` entry: `uv run --directory <path> python server.py`. No `sqlalchemy`/`click` (no registry, no CLI).
**Why:** Minimal deps for a live-execution wrapper. Parallel to `yfinance-mcp`'s entry shape.

## Risks / Trade-offs

- **[SEC rate limits / 403]** SEC throttles by IP+UA and rejects non-descriptive UAs. → Mitigation: require `EDGAR_IDENTITY` at startup; surface a clear error if unset. No client-side rate-limiting (the library handles polite delays); document that heavy bulk use is out of scope.
- **[Rich-object serialization loss]** `Filing.obj()` returns form-specific dataclasses (TenK, Form4, etc.) whose shape varies. → Mitigation: `_serialize()` flattens `__dict__` recursively with a depth cap and falls back to `str()`; `detail` param lets the caller opt into `minimal` to avoid large payloads. Some fields may come back as strings — acceptable for an agent-facing tool.
- **[Network in tests]** Live calls hit SEC. → Mitigation: tests skip when `edgartools` not installed (`@pytest.mark.skipif`) and a network guard; a small `__main__` self-check uses a stable ticker (AAPL) and is opt-in, not part of CI.
- **[Library churn]** `edgar` API evolves. → Mitigation: keep tool bodies thin; pin `edgartools>=2.0` and document the version the design targets.

## Migration Plan

Additive — no migration. Rollout:
1. Create `mcp/edgartools-mcp/` (server.py, pyproject.toml, .env, .env.example).
2. `uv sync` in the dir; add `EDGAR_IDENTITY` to root `.env` (or per-MCP `.env`).
3. Add `edgartools-mcp` entry to `.mcp.json`; update `CLAUDE.md`.
4. Restart MCP clients; verify tools list and one live call per tool.

Rollback: remove the `.mcp.json` entry and the directory. No shared state touched.
