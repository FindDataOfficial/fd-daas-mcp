## Why

`cnreport-mcp` hardcodes only the four periodic-report forms (`年度/半年度/第一季度/第三季度报告`) in `cninfo_client._FORM_CATEGORIES`. CNINFO exposes a far broader disclosure taxonomy — prospectuses (`招股说明书`), refinancing (`增发`/`配股`/`可转债`), earnings forecasts (`业绩预告`/`业绩快报`), shareholder-meeting and board resolutions, M&A (`收购报告书`/`权益变动报告书`), equity incentives, related-party transactions, and more — but the MCP cannot discover, filter by, or retrieve any of them. Agents today have no way to ask "what report types exist for this company?" or "fetch me its 收购报告书", which blocks scalable coverage of the CN disclosure surface. The taxonomy is also encoded in code, so adding a report type requires a code change rather than a data edit.

## What Changes

- **Add a data-driven CNINFO category catalog** — a JSON registry (`cninfo_categories.json`) mapping Chinese category names → CNINFO category codes, grouped by disclosure type (定期报告 / 融资 / 股权变动 / 公司治理 / 业绩 / 担保 / 其他). Adding a report type becomes a data edit, not a code change. The existing `_FORM_CATEGORIES` dict is retired in favor of this registry.
- **New `list_report_types` tool** — returns the catalog (optionally filtered by group), so agents can browse the full report-type surface before fetching. Self-documenting discovery layer.
- **Generalize `list_filings`** — add a `category` parameter accepting either a CNINFO code (`category_ndbg_szsh`) or a Chinese name from the catalog (`招股说明书`). This lifts the four-form restriction so any disclosure category can be listed. The existing `form` parameter is kept as a backward-compatible alias for the four periodic reports.
- **New `get_special_report` tool** — retrieves a special-type report for a company by category (e.g. `招股说明书`, `收购报告书`), optionally extracting a named section. Reuses the existing `fetch_source → parse_outline → resolve_selector → extract_section_text` pipeline — no PDF logic duplicated. Parallels `get_section` (which is annual-report-scoped) for the long tail of non-periodic disclosures.
- **`query_announcements` (in `cninfo_client.py`)** gains a `category` parameter that is passed through as the CNINFO `category` filter for any catalog code, replacing the four-form-only path internally.

## Capabilities

### New Capabilities
- `cnreport-report-type-catalog`: A browsable, data-driven catalog of CNINFO disclosure report types (category name → code, grouped), exposed via `list_report_types`. The discovery layer that makes the long tail of CN disclosures addressable.
- `cnreport-special-report-retrieval`: A `get_special_report` tool that resolves and retrieves any non-periodic report (prospectus, M&A, earnings forecast, etc.) for a company by category, with optional section extraction reusing the existing outline pipeline.

### Modified Capabilities
- `cnreport-company-api`: `list_filings` gains a `category` parameter (any catalog code or Chinese name) so it can list disclosures of any type, not just the four periodic forms. The internal `_FORM_CATEGORIES` dict is replaced by the JSON registry; `form` remains as a backward-compatible alias.

## Impact

- **`mcp/cnreport-mcp/cninfo_client.py`**: replace `_FORM_CATEGORIES` with registry loading; add `category` param to `query_announcements`; add a catalog loader (`load_categories`).
- **`mcp/cnreport-mcp/cninfo_categories.json`** (new): the data-driven category registry, grouped by disclosure type. Seeded with the four existing forms plus a curated set of common special types (招股说明书, 增发, 配股, 可转债, 业绩预告, 业绩快报, 股东大会决议, 董事会决议, 收购报告书, 权益变动报告书, 股权激励, 关联交易, 对外担保). Extensible by JSON edit.
- **`mcp/cnreport-mcp/cnreport_tools.py`**: `list_filings` wrapper gains `category`; add `list_report_types` and `get_special_report` wrappers.
- **`mcp/cnreport-mcp/server.py`**: register the two new `@app.tool`s; extend `list_filings` signature.
- **`mcp/cnreport-mcp/test_cnreport.py`** + **`test_fixtures/`**: offline tests for the catalog, `category`-filtered listing, and `get_special_report`; new fixture for a special-category announcement response.
- **`mcp/cnreport-mcp/selfcheck.py`**: exercise the two new tools against mocks.
- **`mcp/cnreport-mcp/README.md`** + **`CLAUDE.md`**: document the new tools and the category registry.
- **No breaking changes** — `form` and all existing tools behave unchanged; the four-form names still resolve through the new registry.
