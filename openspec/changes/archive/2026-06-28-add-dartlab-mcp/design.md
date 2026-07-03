## Context

The MCP fleet wraps financial-data libraries behind a uniform FastMCP (stdio) interface. Two patterns exist:

1. **Registry + live-call** (`akshare-mcp`, `yfinance-mcp`): a `*-agent-harness` ships a curated SQLite registry of hundreds of flat functions; the MCP exposes `search_functions` / `list_functions` / `get_function_info` / `list_categories` / `call_<lib>_function`. Fits libraries whose surface is many flat callables.
2. **Purpose-built** (`edgartools-mcp`, `daas-mcp`, `worldbank-mcp`, `ckan-mcp`): a standalone MCP with a handful of domain-shaped tools, no registry.

[dartlab](https://pypi.org/project/dartlab/) exposes a small **object model**, not flat functions: `dartlab.Company(ticker)` → `.panel(topic)`, `.panel.search(q)`, `.filings()`, `.analysis(kind, aspect)`, `.credit("등급")`, `.story()`, `.quant()`; plus top-level `dartlab.scan(category, metric)`, `.compare([...], topic=)`, `.gather(kind, ticker)`, `.macro(...)`, `.search(q)`. The registry pattern does not fit — there is nothing to enumerate. The purpose-built pattern is correct, exactly as decided for `edgartools-mcp`.

The library is live-execution: pre-built parquet auto-downloads from HuggingFace to a local cache on first use; US EDGAR data fetched live from SEC. It does not write to `mcp/daas.db` and does not need `mcp/models/`. dartlab also ships a built-in `dartlab mcp` server, but it exposes generic agent-scaffolding tools (`ask`, `RunPython`, `WebSearch`, `ReadSkill`, `SaveArtifact`, …), not the data API — so wrapping the library ourselves gives agents typed tools with docstrings instead of free-form Python.

## Goals / Non-Goals

**Goals:**
- Six purpose-built tools covering the common DART workflows: company panel (statements/ratios/business text/notes), in-filing text search, filing links, credit rating, deep analysis, market-wide scan.
- Self-contained `mcp/dartlab-mcp/` venv, registered in `.mcp.json`, following the unified-env convention.
- Robust serialization of dartlab's rich objects (DataFrames, panel grids, nested dicts) to JSON.
- Optional `DART_API_KEY` passthrough (no gating) — basic use needs no key.

**Non-Goals:**
- No `dartlab-agent-harness` CLI, no curated registry, no `mcp/models/` tables. (YAGNI — the library is the registry.)
- No writes to `mcp/daas.db`, no leader-mcp registration, no dashboard datasource. (Additive; can be layered later.)
- No `dartlab.ask()` AI-analysis passthrough (it needs an LLM provider key and duplicates what the host agent already is), no `dartlab.channel()` mobile tunnel, no `publishReport` blog generation.
- No `compare`/`gather`/`macro`/`story`/`quant` tools in v1. `scan` covers cross-sectional; `panel` + `analyze` + `credit` cover single-company. The rest can be added later if asked.

## Decisions

### Decision 1: Purpose-built tools, not a registry/harness
**Choice:** Six domain tools (`company_panel`, `panel_search`, `list_filings`, `get_credit`, `analyze`, `scan`).
**Why:** dartlab's API is an object model (`Company`, panel grid, credit rating), not a flat function catalog. A registry would be fabricated ceremony — same reasoning as `edgartools-mcp`.
**Alternative considered:** Wrap the built-in `dartlab mcp`. Rejected — it exposes generic agent tools (`RunPython`, `WebSearch`), not the data surface, and would hand the host agent a free-form Python execution tool. Alternative: a generic `call_dartlab_function(name, params_json)` dispatcher. Rejected — no natural flat namespace, and it loses parameter validation and docstrings.

### Decision 2: Optional `DART_API_KEY`, no gating
**Choice:** Root/per-MCP `.env` may set `DART_API_KEY` (free key from opendart.fss.or.kr). The server passes it through but does NOT gate tools on it — basic use relies on dartlab's pre-built HuggingFace data and needs no key. The key only matters for raw re-collection via `dartlab.OpenDart()` / `dartlab collect`.
**Why:** Unlike SEC EDGAR (where a descriptive User-Agent is mandatory or SEC 403s), DART's pre-built dataset is keyless. Gating would break the common path.
**Alternative:** Require `DART_API_KEY` like edgartools requires `EDGAR_IDENTITY`. Rejected — incorrect for this library. **Open question:** confirm the exact env-var name dartlab reads (likely `DART_API_KEY` or `DART_KEY`) by inspecting `dartlab.OpenDart` at implementation time; the server just forwards whatever is set.

### Decision 3: Tools return JSON-serializable dicts via a shared serializer
**Choice:** A `_serialize()` helper converts dartlab results to dicts: `pd.DataFrame` → `{type:"dataframe", shape, columns, data: records}` (NaN→null), `pd.Series` → `{type:"series",...}`, dict/list/scalar passthrough, `__dict__`-bearing objects → depth-capped flattened dict, `str()` fallback. Mirrors `edgartools-mcp`'s `_serialize` verbatim.
**Why:** dartlab returns rich objects (panel grids as DataFrames, credit-rating dicts, analysis objects). MCP tool results must be JSON.
**Alternative:** raw `repr()`. Rejected — unusable for an agent.

### Decision 4: Tool signatures (the contract)
| Tool | Params | Returns |
|---|---|---|
| `company_panel` | `ticker: str`, `topic: Optional[str]=None`, `freq: Optional[str]=None` | `dartlab.Company(ticker).panel(topic, freq=freq)` serialized. `topic` selects the statement: `IS`/`BS`/`ratios`/`사업`/`inventory`/`borrowings`/`segments`/… (uppercase = finance-normalized, lowercase = native as-reported). None = full disclosure grid. |
| `panel_search` | `ticker: str`, `query: str` | `Company(ticker).panel.search(query)` — full-text hits within the company's filings |
| `list_filings` | `ticker: str`, `limit: int=20` | `Company(ticker).filings()` sliced to `limit` — raw filing links to the DART viewer |
| `get_credit` | `ticker: str` | `Company(ticker).credit("등급")` — dCR grade, healthScore 0-100, PD estimate |
| `analyze` | `ticker: str`, `kind: str="financial"`, `aspect: Optional[str]=None` | `Company(ticker).analysis(kind, aspect)` — deep analysis (e.g. `kind="financial"`, `aspect="수익성"`) |
| `scan` | `category: str`, `metric: Optional[str]=None` | `dartlab.scan(category, metric)` — cross-sectional across all listed companies (e.g. `category="ratio"`, `metric="roe"`; `category="governance"`) |

**Why these six:** `company_panel` is the workhorse (one method covers statements, ratios, business text, notes via `topic`). `panel_search` for in-filing text. `list_filings` for raw links. `get_credit` and `analyze` for the two distinct deep-dive surfaces (rating vs. analysis). `scan` for the only market-wide operation. `compare`/`gather`/`macro`/`story`/`quant` are deliberately deferred (YAGNI).

### Decision 5: Lazy import of `dartlab` inside tool bodies
**Choice:** `import dartlab` happens inside each tool, not at top of file. The module top only loads dotenv + creates the FastMCP app.
**Why:** Matches `edgartools-mcp`/`yfinance-mcp` (lazy imports). Keeps the server importable/fast even if `dartlab` is not yet installed, and lets tools return `{"error": "dartlab is not installed", "hint": "pip install dartlab"}`. dartlab's first-use HuggingFace download is heavy — lazy import also keeps `app.run()` startup snappy.

### Decision 6: Packaging mirrors `edgartools-mcp`, with Python ≥3.12
**Choice:** `mcp/dartlab-mcp/pyproject.toml` with `fastmcp>=2.0`, `dartlab>=0.10`, `pandas>=1.0`, `python-dotenv>=1.0`, `requires-python>=3.12` (dartlab's floor). `.mcp.json` entry: `uv run --directory <path> python server.py`. No `sqlalchemy`/`click`.
**Why:** Minimal deps for a live-execution wrapper. `requires-python>=3.12` because dartlab declares `Python >=3.12`; each MCP runs in its own isolated uv venv (the `edgartools-mcp` venv is already cpython-3.12), so this does not touch the project's 3.10+ baseline.
**Alternative:** pin lower and hope. Rejected — dartlab will refuse to install.

## Risks / Trade-offs

- **[Heavy first-use download]** dartlab pulls tens of MB of parquet from HuggingFace on first `Company(...)` call. → Mitigation: lazy import so startup is fast; the first tool call pays the cost once and caches locally. Document in `.env.example` / CLAUDE.md.
- **[Rich-object serialization loss]** `panel()` returns grids whose shape varies by topic; `analysis()`/`credit()` return nested objects. → Mitigation: `_serialize()` flattens recursively with a depth cap and `str()` fallback; `company_panel` returns the grid as dataframe records when possible. Some fields may come back as strings — acceptable for an agent-facing tool.
- **[Topic string is Korean/mixed-case]** `panel("IS")` vs `panel("is")` differ (normalized vs as-reported); `panel("사업")` is Korean. → Mitigation: pass `topic` through verbatim (no normalization) and document the convention in the tool docstring; agents can read the docstring.
- **[Network in tests]** Live calls hit HuggingFace/SEC/DART. → Mitigation: a small `__main__` self-check uses a stable ticker (`005930` — Samsung) and is opt-in, not part of CI. No pytest suite in v1 (YAGNI; the library is the surface).
- **[DART_API_KEY env-var name]** The exact env var dartlab reads is unconfirmed. → Mitigation: forward `DART_API_KEY` (conventional name) and confirm against `dartlab.OpenDart` source during implementation; basic use is keyless regardless.
- **[Library churn]** dartlab is v0.10.x (pre-1.0); API may shift. → Mitigation: keep tool bodies thin; pin `dartlab>=0.10` and document the targeted version.

## Migration Plan

Additive — no migration. Rollout:
1. Create `mcp/dartlab-mcp/` (server.py, pyproject.toml, .env, .env.example).
2. `uv sync` in the dir (creates an isolated 3.12 venv).
3. Optionally add `DART_API_KEY` to root `.env`.
4. Add `dartlab-mcp` entry to `.mcp.json`; update `CLAUDE.md`.
5. Restart MCP clients; verify the tool list and one live call per tool (`005930` for Korea, `AAPL` for US).

Rollback: remove the `.mcp.json` entry and the directory. No shared state touched.

## Open Questions

- Exact env-var name dartlab reads for the DART API key (`DART_API_KEY` vs `DART_KEY`?). Resolve by inspecting `dartlab.OpenDart` at implementation. Non-blocking — basic use is keyless.
- Whether `panel(topic, freq=...)` accepts `freq` for all topics or only statements. Resolve by smoke-testing at implementation; the tool will pass `freq` only when provided.
