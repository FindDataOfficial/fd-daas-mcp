## 1. Schema (mcp/models/models.py)

- [x] 1.1 Add `Category` model: `categories` table with `id`, `name` (unique), `label`, `parent_id` (self-FK nullable, `ON DELETE CASCADE`), `sort_order` (nullable); index `parent_id`; `to_dict()` + a `children`/`parent` relationship
- [x] 1.2 Add `DatasourceForm` model: `datasource_forms` table — `id`, `source_id` (FK `sources.id` `ON DELETE CASCADE`), `form_type` (e.g. `10-K`), `label` (nullable); unique `(source_id, form_type)`; relationship to sections
- [x] 1.3 Add `DatasourceSection` model: `datasource_sections` table — `id`, `form_id` (FK `datasource_forms.id` `ON DELETE CASCADE`), `section_name`, `instruction` (Text, nullable), `sort_order` (nullable); unique `(form_id, section_name)`
- [x] 1.4 Add `DatasourceCollection` model: `datasource_collections` table — `id`, `name` (unique), `description` (nullable), timestamps
- [x] 1.5 Add `DatasourceCollectionItem` model: `datasource_collection_items` table — `id`, `collection_id` (FK `ON DELETE CASCADE`), `source_id` (FK `sources.id` `ON DELETE CASCADE`), `section_id` (FK `datasource_sections.id` `ON DELETE CASCADE`, nullable); unique `(collection_id, source_id, section_id)`
- [x] 1.6 Extend `DaasSource`: add nullable `category_id` (FK `categories.id`, `ON DELETE SET NULL`); update `to_dict()` to include `category_id`
- [x] 1.7 Reinstall shared schema package (`pip install -e mcp/models`) and verify `Base.metadata.create_all` builds all new tables against a temp DB

## 2. DB init migration guard

- [x] 2.1 In `mcp/daas-mcp/daas_database.py` Database init, add an idempotent guarded `ALTER TABLE sources ADD COLUMN category_id INTEGER` (check `PRAGMA table_info` first; ignore if column exists) so existing `daas.db` gains the column without Alembic
- [x] 2.2 Confirm `create_all` creates the 5 new tables on existing `daas.db` without touching existing rows

## 3. Registry service layer (mcp/daas-mcp/registry_service.py)

- [x] 3.1 Category methods: `create_category`, `move_category` (with cycle/ancestor + self-parent rejection), `delete_category` (reject if children; null-out `category_id` on assigned datasources), `get_category_tree` (nested, with `datasource_count`), `get_subtree_ids` (cycle-safe BFS with visited set + depth cap)
- [x] 3.2 Datasource CRUD methods: `create_datasource` (reject dup name + nonexistent category), `update_datasource` (partial update incl. nullable category clear), `delete_datasource` (cascade verified via FK)
- [x] 3.3 Form/section methods: `add_form` (reject unknown source), `add_section` (reject unknown form), `list_forms` (nested with sections + instruction)
- [x] 3.4 Collection methods: `create_collection` (reject dup name), `add_to_collection` (resolve section by name under source; reject dup item + unknown section), `list_collection` (resolve source/form/section names + instruction), `remove_from_collection`
- [x] 3.5 `search_datasources(category_id=None, include_subtree=True, source_name=None, form=None, section=None, query=None, limit=100)` — composable filters; compact shape when no form/section/query, expanded shape otherwise; cycle-safe subtree

## 4. MCP tools (mcp/daas-mcp/daas_tools.py + server.py)

- [x] 4.1 Datasource CRUD tools: `create_datasource`, `update_datasource`, `delete_datasource` — wrap service, JSON-serializable returns
- [x] 4.2 Category tools: `create_category`, `move_category`, `delete_category`, `get_category_tree`
- [x] 4.3 Form/section tools: `add_form`, `add_section`, `list_forms`
- [x] 4.4 Collection tools: `create_collection`, `add_to_collection`, `list_collection`, `remove_from_collection`
- [x] 4.5 Search tool: `search_datasources`
- [x] 4.6 Register all new tools in `server.py` via `app.tool(...)`; leave existing 5 tools untouched
- [x] 4.7 Update the daas-mcp section of `CLAUDE.md` (tools list + new tables)

## 5. Verification

- [x] 5.1 Self-check script (`mcp/daas-mcp/selfcheck.py` or extend existing): create category tree → datasource → form → section with instruction → collection (whole source + specific section) → multi-level search at each level; assert cycle rejection and cascade deletes; runs against a temp DB (does not touch `daas.db`)
- [x] 5.2 Manual: start daas-mcp, call `create_datasource`/`add_form`/`add_section`/`create_collection`/`search_datasources` end-to-end against the real `daas.db`, confirm existing `list_sources`/`search_functions` still work unchanged
- [x] 5.3 Run `openspec validate add-daas-datasource-management --strict` and fix any spec/task issues
