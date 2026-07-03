## Why

The 11 Chinese-ministry open-information scrapers in `mcp/scrapling-uv-mcp/scripts/` (MOF, PBC, NDRC, MOFCOM, MOHURD, MOT, MOA, SAFE, MNR, MEE, MEM) are useful, reusable, and self-describing — each ships a `MANIFEST` of its crawl recipe + output schema. But today they only exist buried inside the `cli-anything` monorepo, coupled to its private `daas.db`, its MCP server layout, and a `scraw_contract` that resolves the DB by walking up the repo tree. None of that is shareable: a user who just wants "crawl the Ministry of Finance notice archive and know the columns" has to clone the whole monorepo and reverse-engineer the registration contract. We need a standalone, pip-installable Python package — published to GitHub — that bundles the scrapers and a self-contained registry (datasources + column schemas) so anyone can use the crawlers and discover the data structure without the monorepo.

## What Changes

- Add a new standalone Python package `gov-scraw/` at the repo root: pip-installable, own `pyproject.toml`, own minimal deps (`scrapling`, `pandas`, `sqlalchemy`), no dependency on the `mcp/` tree or `mcp/models`.
- Port the 11 ministry scraper scripts verbatim (crawl logic unchanged) plus `scraw_contract.py` into the package as importable modules (`gov_scraw.scripts.*`), with a thin CLI entry point (`gov-scraw crawl <name>`) reusing each script's existing `main()`.
- Ship a **self-contained registry** `gov_scraw/registry/` — a small SQLite DB (`registry.db`) plus a JSON export — holding the same rows the monorepo's `daas.db` has for these 11 sources: `sources` (id, name, label, url, description, category), `datasource_columns` (column_name, column_type, is_primary_key, is_nullable, description, source_field, unit, semantic_type), and `scraw_configs` (name, url, columns_json). Built from each script's `MANIFEST`, not hand-maintained.
- Add a read API (`gov_scraw.list_sources()`, `.get_source(name)`, `.get_columns(name)`) backed by the bundled `registry.db` so consumers can discover datasources and their schemas programmatically without the MCP layer.
- Add a one-shot `gov-scraw build-registry` command (and `build_registry.py`) that regenerates `registry.db` + `registry.json` from the live `MANIFEST`s — the source of truth stays the scripts, the DB is a derived artifact.
- Add a GitHub-ready `README.md` (purpose, per-ministry table, install, usage, registry schema, re-build instructions), `LICENSE`, and `.gitignore`.
- **No changes to the existing `mcp/scrapling-uv-mcp/scripts/`** — the package copies, not moves. The monorepo keeps working as-is. (A later change can swap the monorepo scripts to import from the package; out of scope here.)

## Capabilities

### New Capabilities
- `gov-scraw-package`: A standalone, pip-installable Python package that bundles the 11 Chinese-ministry open-information scrapers and a self-contained datasource registry (SQLite + JSON), exposing a crawl CLI, a read API for datasource/column discovery, and a registry rebuild command — distributable on GitHub with no monorepo or MCP dependency.

### Modified Capabilities
<!-- None. The existing mcp/scrapling-uv-mcp scripts and cn-ministry-scraw-sources capability are untouched; the package is a separate distribution channel. -->

## Impact

- **New code**: `gov-scraw/` directory at repo root (package, CLI, bundled registry, build script, README, LICENSE). ~12 Python modules + 1 generated SQLite + 1 generated JSON.
- **Existing code**: none modified. The package reads the same `MANIFEST` contract shape but vendors its own copy of `scraw_contract.py` (decoupled from `mcp/scrapling-uv-mcp/scripts/`).
- **Dependencies**: `scrapling`, `pandas`, `sqlalchemy` (declared in the package's own `pyproject.toml`); runtime is plain `python3`, no `uv`/MCP required.
- **Data**: ships a generated `registry.db` (the 11 sources' `sources` + `datasource_columns` + `scraw_configs` rows, no `daas.db` coupling). Regenerated on demand from the `MANIFEST`s.
- **Distribution**: GitHub repo (the `gov-scraw/` subtree can be split or pushed as-is). No PyPI publish in scope; `pip install git+https://...` is the install path.
- **Out of scope**: replacing the monorepo's scripts with imports from this package; cron/MCP integration; crawling detail-page bodies (still catalog-only).
