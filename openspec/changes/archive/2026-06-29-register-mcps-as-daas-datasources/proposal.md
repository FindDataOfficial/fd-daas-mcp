## Why

The daas-mcp datasource registry shipped with the management capability (CRUD over `sources`/`forms`/`sections`/`collections`) but no data: only the three pre-seeded macro sources (`ckan`, `cnstats`, `worldbank`) exist, all without forms or sections. Meanwhile four purpose-built MCPs already serve real disclosure/market data — `edgartools-mcp` (SEC EDGAR), `edinet-mcp` (Japan EDINET), `yfinance-mcp` (Yahoo Finance), and `cnstats-mcp` (NBS China) — but none of them is discoverable through daas-mcp's `search_datasources` / category tree / collections. An agent asking "which datasource exposes 10-K Item 1A?" today gets zero results. This change closes that gap by seeding each MCP's data surface as a daas datasource with its natural form/section structure, so the daas-mcp registry becomes a single discovery layer over all four.

## What Changes

- Seed four datasources in `daas.db` via the existing daas-mcp management tools (no schema change):
  - `edgar` — new datasource; forms `10-K`, `10-Q`, `8-K`, `4`; each form populated with its canonical item sections plus a per-section extraction `instruction` pointing at the right `edgartools-mcp` tool.
  - `edinet` — new datasource; forms = EDINET doc-type codes (`120` 有価証券報告書, `130` 四半期報告書, `140` 半期報告書, `150` 臨時報告書, `160` 訂正届出書, `170` 自己株式取得状況, `180` 親会社等状況報告書, `350` 大量保有報告書, `360` 公開買付届出書); section per typed parser.
  - `yfinance` — new datasource; single `default` form; sections per top yfinance category (`price-history`, `fundamentals`, `options`, `holders`, `news`, `search-download`); each section's instruction names the matching `yfinance-mcp` tool.
  - `cnstats` — existing row reused; one `default` form added; sections per CNStats top category.
- Add a hierarchical category tree (`Filings → US-SEC`, `Filings → JP-EDINET`, `Market-Data → Global`, `Macro → China`) and assign each datasource to its category, so `get_category_tree` shows them grouped.
- Add a `core` collection wiring the most-used (datasource, section) pairs across all four sources so agents can pull a curated set in one call.
- Ship a single idempotent seed script (`mcp/daas-mcp/seed_external_mcps.py`) that performs all the above by calling the registry service directly — safe to re-run; no-ops on existing rows.

## Capabilities

### New Capabilities

- `external-mcp-datasource-seed`: An idempotent seed routine, owned by daas-mcp, that registers a fixed set of sibling-MCPs (`edgar`, `edinet`, `yfinance`, `cnstats`) as daas datasources — including their categories, forms, sections with extraction instructions, and a baseline collection — using the existing management tools. Defines which datasources/forms/sections are in scope, the category tree they sit under, idempotency semantics, and how the seed is invoked.

### Modified Capabilities

<!-- None — schema and management tools are unchanged. This is data only. -->

## Impact

- Code: new file `mcp/daas-mcp/seed_external_mcps.py`; a one-line note in the daas-mcp section of `CLAUDE.md` pointing at the seed script.
- Data: `mcp/daas.db` gains rows in `sources` (3 new: edgar/edinet/yfinance — cnstats already exists), `categories` (4), `datasource_forms` (~14), `datasource_sections` (~50), `datasource_collections` (1), `datasource_collection_items` (~10). All writes go through the existing registry service, so cascade/uniqueness invariants are reused.
- APIs: no changes — uses existing daas-mcp tools and registry service methods.
- Dependencies: none added. The seed script only imports the daas-mcp registry service.
- Sibling MCPs (`edgartools-mcp`, `edinet-mcp`, `yfinance-mcp`, `cnstats-mcp`): untouched. Sections store the *names* of tools that the agent should call on the right MCP, not direct couplings.
