## Context

daas-mcp wraps the `daas-agent-harness` source registry (`akshare`, `worldbank`, `ckan`, `cnstats`, …). Today it exposes 5 **read-only** tools (`list_sources`, `search_functions`, `get_function_detail`, `list_categories`, `fetch_data`) over four tables in the shared `mcp/models/models.py` Base: `DaasSource` (`sources`), `DaasFunction` (`daas_functions`), `DaasFunctionColumn` (`daas_function_columns`), `Observation` (`observations`).

Categories are a flat `category` string on `DaasFunction` — no hierarchy, no table, no drill-down. Sources can only be read, never created/edited through MCP. And the extraction knowledge we build interactively (EDGAR form `10-K` → section `Item 1 Business` → "extract the company-description paragraph") is ephemeral: it lives in a throwaway script and is gone next session.

The earlier `add-datasource-management` change upgraded **leader-mcp** (the `functions` table) — daas-mcp's `DaasSource` was untouched and remains unmanaged. This change promotes daas-mcp into a managed, categorized, collection-capable registry with persistent extraction metadata.

Constraints: single shared `Base` (schema changes go in `mcp/models/models.py` first); single DB `mcp/daas.db`; `Base.metadata.create_all` handles additive table creation; FastMCP stdio transport; relative imports — run from within `mcp/daas-mcp/`.

## Goals / Non-Goals

**Goals:**
- Make daas-mcp **writable**: create/update/delete datasources through MCP tools.
- Introduce a **hierarchical category tree** as the primary organizational axis for datasources.
- Persist **form → section → instruction** extraction metadata attached to a datasource (the EDGAR-style knowledge, made durable and reusable).
- Support **multi-level search** (category subtree → source → form → section) in a single tool.
- Support **collections** that bundle whole datasources or specific datasource-sections.

**Non-Goals:**
- No migration of the existing flat `DaasFunction.category` string — left in place; the new `categories` table is the datasource axis, not the function axis.
- No executing extraction instructions (no LLM/scraper invocation) — instructions are *stored* metadata, not run by daas-mcp. Execution is a future concern (likely cnreport-mcp / scrapling territory).
- No dashboard UI changes in this change (dashboard can adopt later).
- No renaming/removing existing tools — additive only.

## Decisions

### D1. Extraction metadata attaches to DaasSource, not DaasFunction
Forms (`10-K`, `8-K`) and their sections are a property of a **source** (e.g. EDGAR), not of a single callable function. One source → many forms → many sections → one instruction each.
- *Alternative considered:* attach to `DaasFunction`. Rejected — couples extraction metadata to specific callable functions, and a form/section applies source-wide regardless of which function fetches it.

Schema:
```
sources (DaasSource)  + category_id (nullable FK → categories)
   │
   ├──< datasource_forms (id, source_id, form_type, label)
   │        │
   │        └──< datasource_sections (id, form_id, section_name, instruction, ...)
   │
categories (id, name, parent_id NULL→self, sort_order)
   └── self-referencing tree

datasource_collections (id, name, description)
   └──< datasource_collection_items (id, collection_id, source_id, section_id NULLABLE)
```
`section_id` nullable on the join table is what lets a collection hold either a whole datasource (`section_id = NULL`) or a specific section.

### D2. Hierarchical categories via self-referencing `parent_id`
A `categories` table with `parent_id` self-FK. Subtree search = recursive CTE on SQLite (or Python-side traversal for simplicity/portability).
- *Alternative:* flat categories with a `path` ltree-style string. Rejected — SQLite has no native ltree; a `path` string is fragile under rename. Self-ref + traversal is simplest correct option.

### D3. CRUD tools are explicit per-entity, not a generic RPC
Separate `create_datasource` / `update_datasource` / `delete_datasource`, `create_category` / `move_category`, `add_form` / `add_section`, `create_collection` / `add_to_collection`. More tools, but each is self-documenting and type-checkable in FastMCP.
- *Alternative:* one generic `upsert_entity(table, payload)` tool. Rejected — opaque, harder to validate, bad MCP ergonomics.

### D4. Multi-level search is one tool with optional level filters
`search_datasources(category=None, include_subtree=True, source=None, form=None, section=None, query=None)` — every filter optional; combining them drills the levels. `query` does free-text across source label/description, form label, section name/instruction.
- *Alternative:* separate per-level browse tools. Rejected — the user explicitly wants "search them in different level" as one capability; one tool with composable filters serves it.

### D5. Additive schema, `create_all` only, no Alembic
New tables + a nullable `category_id` on `sources`. `Base.metadata.create_all` creates new tables; the nullable column is added with a guarded `ALTER TABLE ... ADD COLUMN` in a one-shot idempotent check inside the daas Database init (SQLite supports `ADD COLUMN`; guard on `PRAGMA table_info`). No Alembic, no destructive migration.
- *Alternative:* Alembic migration. Rejected — overkill for additive SQLite changes; the project already relies on `create_all` everywhere.

### D6. Backward compatibility for existing tools
Existing 5 tools untouched. `list_sources` continues to return flat source dicts; it will additionally include `category_id` and `category_path` (cheap join) but no existing caller breaks. `DaasFunction.category` string is NOT removed.

## Risks / Trade-offs

- **[Self-ref category cycles]** A user could set a category's `parent_id` to its own descendant, creating a cycle. → Mitigation: `move_category` rejects any ancestor-chain target; traversal uses a visited-set guard with a depth cap.
- **[Orphaned sections/forms on datasource delete]** Deleting a source should cascade. → Mitigation: `ON DELETE CASCADE` on `datasource_forms.source_id` and `datasource_sections.form_id`; collection items referencing the deleted source are also removed (cascade or explicit cleanup).
- **[Collection item dangling refs]** A collection item points at a section that gets deleted with its form. → Mitigation: `ON DELETE CASCADE` on `section_id` FK removes the collection item; `source_id` is always set so a whole-datasource collection item survives section deletion.
- **[Subtree search performance]** Recursive traversal on a large category tree. → Mitigation: category trees are small (tens to low hundreds of nodes); Python-side BFS with a visited set is fine. Index `parent_id`.
- **[Instruction stored as free text]** No schema/validation on `instruction` content. → Mitigation: accept it; intentional — instructions are prompts/rules, validating structure is out of scope (Non-Goal).
- **[Flat `category` string duplication]** Two category concepts now coexist (new `categories` table + old `DaasFunction.category` string). → Mitigation: documented as intentional; the string is the *function* axis, the table is the *datasource* axis. No migration.

## Migration Plan

1. Add models to `mcp/models/models.py` (additive). Reinstall `pip install -e mcp/models`.
2. On next daas-mcp start, `Base.metadata.create_all` creates the 5 new tables; the guarded `ALTER TABLE sources ADD COLUMN category_id` runs once.
3. Existing data untouched. Users opt in by creating categories and assigning datasources.
4. **Rollback:** drop the 5 new tables and the `category_id` column. No existing data depends on them. Existing tools keep working throughout.

## Open Questions

- Should `list_sources` auto-populate `category_path`, or is a separate `get_datasource_tree` tool cleaner? → Lean: include `category_path` in `list_sources` (cheap), add `get_category_tree` as the dedicated browse tool.
- Do collections need ordering/sorting of items? → Defer; add a `sort_order` column now (nullable) so we don't need a second migration.
- Should a section carry an optional `output_schema` (expected columns of the extracted data)? → Out of scope for this change; `instruction` text is enough. Revisit if execution is added later.
