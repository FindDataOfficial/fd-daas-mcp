## Why

daas-mcp is read-only today — 5 tools that list/search/fetch against a flat registry. There is no way to add, edit, or organize datasources through MCP, categories are flat strings (no hierarchy, no drill-down), and the EDGAR form/section/instruction knowledge we extract is ephemeral — it never persists. We need daas-mcp to *manage* datasources: register them, attach reusable extraction metadata (form → section → instruction), organize them in a hierarchical category tree, search at every level, and bundle them into named collections for reuse.

## What Changes

- **New `categories` table** — hierarchical (`parent_id` self-reference), replaces the flat `category` string on `DaasFunction`. A datasource lives under one category.
- **New `datasource_forms` table** — a DaasSource can expose many forms (e.g. `10-K`, `8-K`, `20-F`). FK → `sources`.
- **New `datasource_sections` table** — a form has many sections (e.g. `Item 1 Business`, `Item 7 MD&A`), each carrying an `instruction` (extraction prompt/rule). FK → `datasource_forms`.
- **New `datasource_collections` + `datasource_collection_items` tables** — named groups; an item references a datasource AND optionally a specific section (nullable `section_id`), so a collection can hold whole datasources or granular sections.
- **CRUD + management tools on daas-mcp** — `create_datasource`, `update_datasource`, `delete_datasource`, plus category/form/section/collection CRUD tools. daas-mcp becomes writable, not just readable.
- **Multi-level search tool** — `search_datasources` that drills category → source → form → section, with filters at each level.
- **Schema lives in `mcp/models/models.py`** first (the shared Base), then daas-mcp's `registry_service`/`daas_tools`/`server` grow the new tools. `Base.metadata.create_all` handles the new tables; no destructive migration of existing data.

## Capabilities

### New Capabilities
- `datasource-management`: CRUD over DaasSource rows — create, update, delete, and assign a datasource to a hierarchical category. Turns daas-mcp from read-only to managed.
- `datasource-category-tree`: Hierarchical `categories` table (self-referencing `parent_id`) with CRUD and tree traversal. Replaces the flat `category` string as the organizational axis for datasources.
- `datasource-forms-sections`: A datasource exposes forms; each form exposes sections; each section carries an extraction `instruction`. Persistent, reusable extraction metadata (the EDGAR form/section work made durable).
- `datasource-collections`: Named collections grouping datasources or specific datasource-sections. CRUD over collections and their items.
- `datasource-multi-level-search`: Search/filter datasources across levels — by category (incl. subtree), source, form, and section — in one tool.

### Modified Capabilities
None — daas-mcp has no existing OpenSpec specs to modify (the earlier `add-datasource-management` change upgraded leader-mcp, not daas-mcp).

## Impact

- **`mcp/models/models.py`** — add 6 new models: `Category`, `DatasourceForm`, `DatasourceSection`, `DatasourceCollection`, `DatasourceCollectionItem`. Extend `DaasSource` with a nullable `category_id` FK. (Existing `DaasFunction.category` string is left in place for backward compat — not migrated.)
- **`mcp/daas-mcp/registry_service.py`** — add management + search methods (create/update/delete datasource, category CRUD, form/section CRUD, collection CRUD, multi-level search).
- **`mcp/daas-mcp/daas_tools.py`** — add ~15 new MCP tool functions wrapping the service.
- **`mcp/daas-mcp/server.py`** — register the new tools.
- **`mcp/daas.db`** — new tables created automatically via `Base.metadata.create_all`; existing tables untouched (additive only).
- **No breaking changes** — all 5 existing tools keep their signatures and behavior. New `category_id` on `DaasSource` is nullable.
