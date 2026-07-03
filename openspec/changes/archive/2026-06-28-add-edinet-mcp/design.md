## Context

The MCP fleet wraps financial-data libraries behind a uniform FastMCP (stdio) interface. Two patterns exist today:

1. **Registry + live-call** (`akshare-mcp`, `yfinance-mcp`): a `*-agent-harness` ships a curated SQLite registry of hundreds of flat functions; the MCP exposes `search_functions` / `list_functions` / `get_function_info` / `list_categories` / `call_<lib>_function`. This fits libraries whose surface is many flat callables.
2. **Purpose-built** (`edgartools-mcp`, `daas-mcp`, `worldbank-mcp`, `ckan-mcp`): a standalone MCP with a handful of domain-shaped tools, no registry.

`edinet-tools` (PyPI `edinet-tools`, import `edinet_tools`, v0.7.1) exposes a small **functional API** keyed on entities and document types — `edinet_tools.entity("7203")`, `.search(...)`, `.documents("2026-01-20")`, `.supported_doc_types()`, `.doc_type("235")`, `doc.parse()`, `fetch_document(...)` — returning typed dataclasses (`net_sales`, `roe`, `segments`, `filer_name`, etc.) with `to_dict()` / `fields()` / `raw_fields` / `text_blocks`. It is an object model, not a flat function catalog. The registry pattern does not fit — there is nothing to enumerate. The purpose-built pattern is the correct shape, mirroring the recently-added `edgartools-mcp`.

The library is live-execution (hits `api.edinet-fsa.go.jp`), like `edgartools-mcp`/`yfinance-mcp`. It does not write to `mcp/daas.db` and does not need `mcp/models/`.

## Goals / Non-Goals

**Goals:**
- Five purpose-built tools covering the common EDINET workflows: entity search, entity detail, document listing by date, single-document parse, and document-type metadata.
- Self-contained `mcp/edinet-mcp/` venv, registered in `.mcp.json`, following the unified-env convention.
- Correct API-key handling: entity lookup/parsing work keyless; only `documents()`/`fetch_document` require `EDINET_API_KEY`. Surface a clear error when a key-requiring tool is called without a key, rather than failing opaquely.
- Robust serialization of edinet-tools' typed dataclasses and any `pandas` objects to JSON.

**Non-Goals:**
- No `edinet-agent-harness` CLI, no curated registry, no `mcp/models/` tables. (YAGNI — the library is the registry.)
- No writes to `mcp/daas.db`, no leader-mcp registration, no dashboard datasource. (Additive; can be layered later if discovery is needed.)
- No bulk document download of raw XBRL/PDF/HTML bytes as binary MCP results (fetch is surfaced as parse results / metadata, not raw file bytes).
- No deep dimensional/footnote extraction beyond what `doc.parse().to_dict()` exposes.

## Decisions

### Decision 1: Purpose-built tools, not a registry/harness
**Choice:** Five domain tools (`search_entities`, `get_entity`, `list_documents`, `get_document`, `supported_doc_types`).
**Why:** edinet-tools' API is a small functional surface keyed on entities and document-type codes, not a flat function catalog. A registry of "ticker_history"-style entries would be fabricated ceremony.
**Alternative considered:** Mirror `yfinance-mcp` with a harness + `call_edinet_function(name, params_json)` generic dispatcher. Rejected — there is no natural flat namespace to dispatch on, and a generic dispatcher loses the parameter validation and docstrings that make purpose-built tools useful to an agent.

### Decision 2: API key via `EDINET_API_KEY` env, lazy-checked per tool
**Choice:** Root `.env` (or per-MCP `.env`) holds `EDINET_API_KEY`. The server reads it at startup into a module-level variable. Only the tools that actually call the EDINET documents endpoint (`list_documents`, `get_document` when it must fetch) check the key and return a clear `error` if it is unset. Entity tools (`search_entities`, `get_entity`) and `supported_doc_types` work without a key.
**Why:** EDINET splits its API — metadata/entity endpoints are open; the document-list endpoint requires a key. Failing fast with a clear message beats a 403/empty result. Lazy per-tool check (not a blanket startup abort) keeps keyless entity lookup working.
**Alternative:** Require the key at startup for the whole server. Rejected — would break the keyless entity-lookup workflows the library explicitly supports.

### Decision 3: Tools return JSON-serializable dicts via a shared serializer
**Choice:** A `_serialize(result)` helper converts edinet-tools results to dicts: objects with `to_dict()` → call it; `pd.DataFrame` → `{type:"dataframe", shape, columns, data: records}` (NaN→null); `pd.Series` → `{type:"series",...}`; dataclasses/`__dict__`-able objects → flattened dict (depth-capped); lists/tuples → serialized elements; fall back to `str()`.
**Why:** edinet-tools returns typed dataclasses (`Document`, parsed report objects with `net_sales`/`segments`/etc.) and some pandas objects. MCP tool results must be JSON. Mirrors `edgartools-mcp`/`yfinance-mcp`'s `_serialize`.
**Alternative:** return raw `repr()`. Rejected — unusable for an agent consumer.

### Decision 4: Tool signatures (the contract)
| Tool | Params | Returns | Needs key? |
|---|---|---|---|
| `search_entities` | `query: str`, `limit: int = 10` | list of `{edinet_code, name, english_name, ...}` matches | no |
| `get_entity` | `ticker_or_code: str` | entity facts (name, edinet_code, corporate_number, sector, ...) via `entity()`/`entity_by_corporate_number()` | no |
| `list_documents` | `date: str` (YYYY-MM-DD), `doc_type: Optional[str]=None`, `limit: int = 50` | filings for that date from `documents(date)`, optionally filtered by doc-type code | yes |
| `get_document` | `doc_id: str`, `doc_type_code: Optional[str]=None` | metadata + `doc.parse().to_dict()` parsed fields for the document; `raw_fields`/`text_blocks` included only when `detail != "minimal"` | yes |
| `supported_doc_types` | none | all 42 EDINET document codes with names/descriptions from `supported_doc_types()` | no |

**Why these five:** they map 1:1 to the library's documented entry points (search, entity, documents, doc.parse, supported_doc_types/doc_type). `detail` on `get_document` mirrors the edgartools-mcp `minimal`/`standard`/`full` knob to avoid huge payloads.

### Decision 5: Lazy import of `edinet_tools` inside tool bodies
**Choice:** `import edinet_tools` happens inside each tool, not at top of file.
**Why:** Matches `yfinance-mcp`/`edgartools-mcp` (lazy import). Keeps the server importable/fast even if `edinet-tools` is not yet installed, and lets tools return a clear `{"error": "edinet-tools is not installed", "hint": ...}`.
**Alternative:** top-level import. Rejected — couples server startup to the lib being present and offers no upside.

### Decision 6: Packaging mirrors `edgartools-mcp`/`yfinance-mcp`
**Choice:** `mcp/edinet-mcp/pyproject.toml` with `fastmcp>=2.0`, `edinet-tools>=0.7`, `pandas>=1.0`, `python-dotenv>=1.0`. `.mcp.json` entry: `uv run --directory <path> python server.py`. No `sqlalchemy`/`click` (no registry, no CLI).
**Why:** Minimal deps for a live-execution wrapper. Parallel to the other live-execution MCPs' entry shape.

## Risks / Trade-offs

- **[EDINET rate limits / 403]** EDINET throttles and rejects keyless document-list calls. → Mitigation: require `EDINET_API_KEY` for the document tools; surface a clear error if unset. No client-side rate-limiting (the library handles polite access); document that heavy bulk date-range sweeps are out of scope.
- **[Parsed-object shape variance]** `doc.parse()` returns form-specific dataclasses (SecuritiesReport, LargeShareholding, TenderOffer, ...) whose fields vary across the 42 doc types. → Mitigation: `_serialize()` prefers `to_dict()`, then flattens `__dict__` recursively with a depth cap and falls back to `str()`; `detail` param lets the caller opt into `minimal`. Some fields may come back as strings — acceptable for an agent-facing tool.
- **[Network in tests]** Live calls hit EDINET. → Mitigation: tests skip when `edinet-tools` not installed (`@pytest.mark.skipif`); a small `__main__` self-check uses a stable entity (Toyota `7203` / `edinet_code`) and is opt-in, not part of CI.
- **[Library churn / API naming]** `edinet-tools` is a younger library; function names may shift. → Mitigation: keep tool bodies thin; pin `edinet-tools>=0.7` and document the version the design targets; wrap each library call so a rename is a one-line fix in the server.
- **[Gaiji / full-width text]** EDINET text contains full-width chars and gaiji; the library handles normalization. → Mitigation: rely on the library's handling; ensure JSON output is UTF-8 (FastMCP default).

## Migration Plan

Additive — no migration. Rollout:
1. Create `mcp/edinet-mcp/` (server.py, pyproject.toml, .env, .env.example).
2. `uv sync` in the dir; add `EDINET_API_KEY` to root `.env` (or per-MCP `.env`) — optional, only needed for document tools.
3. Add `edinet-mcp` entry to `.mcp.json`; update `CLAUDE.md`.
4. Restart MCP clients; verify tools list and one live call per tool.

Rollback: remove the `.mcp.json` entry and the directory. No shared state touched.

## Open Questions

- Exact field names returned by `entity()` / `doc.parse().to_dict()` for each doc type are library-version-dependent; the `__main__` self-check and `detail=minimal` knob are the mitigation, but implementers should verify against the installed `0.7.x` at build time and adjust the serializer's known-field extraction if needed.
