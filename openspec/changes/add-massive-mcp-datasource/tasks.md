# Tasks — add-massive-mcp-datasource

> **Note:** The seed-script edits and spec edits already exist in the working tree (uncommitted) and `daas.db` already has the `massive` rows from a prior seed run. Most tasks below are **verify + commit**, not greenfield implementation. See `design.md` Decision 5.

## 1. Seed script — `mcp/daas-mcp/seed_external_mcps.py`

- [x] 1.1 Confirm the working-tree diff adds all seven pieces: `massive` in `OWNED_SOURCES`; a `massive` entry in `SOURCES`; the `("Massive", "Massive.com", "Market-Data")` row in `CATEGORIES`; the `MASSIVE_SECTIONS` list (3 tuples); the `("massive", "Search-Endpoints")` item in the `core` collection block; `massive` in the seed-loop `for src_name in (...)`; and the `7c. massive default form` block that calls `goc_form` + `goc_section` for the three sections.
- [x] 1.2 Run `uv run --directory mcp/daas-mcp python seed_external_mcps.py --dry-run` and confirm the plan prints an upsert for the `massive` source, the `Massive` category, the `default` form, the three sections, and one `core` collection item.

## 2. Spec — `openspec/specs/external-mcp-datasource-seed/spec.md`

- [x] 2.1 Confirm the working-tree spec adds exactly four new requirements (verified via `git diff HEAD`): "Massive datasource exposes the default form with three composable-tool sections", "massive sits under the Market-Data → Massive category", "massive joins the core collection", "`--unseed` removes the massive datasource" — and modifies no existing requirement.
- [x] 2.2 Confirm this change's `specs/external-mcp-datasource-seed/spec.md` delta matches those four requirement blocks verbatim (the `/opsx:apply` step merges this delta into the canonical spec; since the working-tree spec already has them, the merge is a content no-op).

## 3. Idempotency — re-run is a no-op on the live `daas.db`

- [x] 3.1 Snapshot row counts before re-seed: `sqlite3 mcp/daas.db "SELECT 'sources', COUNT(*) FROM sources UNION ALL SELECT 'categories', COUNT(*) FROM categories UNION ALL SELECT 'forms', COUNT(*) FROM datasource_forms UNION ALL SELECT 'sections', COUNT(*) FROM datasource_sections UNION ALL SELECT 'collections', COUNT(*) FROM datasource_collections UNION ALL SELECT 'items', COUNT(*) FROM datasource_collection_items;"`.
- [x] 3.2 Re-run `uv run --directory mcp/daas-mcp python seed_external_mcps.py` (no flags) and confirm exit status 0.
- [x] 3.3 Re-run the 3.1 count query and confirm every count is unchanged (idempotency — satisfies the spec's "Second run is a no-op on row counts" scenario).

## 4. Spot-check the seeded `massive` rows

- [x] 4.1 `sqlite3 mcp/daas.db "SELECT id, name, label, category_id FROM sources WHERE name='massive';"` → one row, `label='Massive.com'`, non-null `category_id`.
- [x] 4.2 `sqlite3 mcp/daas.db "SELECT s.name, f.form_type, sec.section_name, sec.instruction FROM sources s JOIN datasource_forms f ON f.source_id=s.id LEFT JOIN datasource_sections sec ON sec.form_id=f.id WHERE s.name='massive' ORDER BY sec.section_name;"` → one `default` form with exactly three sections (`Call-API`, `Query-Data`, `Search-Endpoints`) whose `instruction`s begin with `mcp=massive-mcp`.
- [x] 4.3 `sqlite3 mcp/daas.db "SELECT c.name, ci.source_id, sec.section_name FROM datasource_collections c JOIN datasource_collection_items ci ON ci.collection_id=c.id JOIN datasource_sections sec ON sec.id=ci.section_id WHERE c.name='core' AND s.name='massive';"` — adjust the join to confirm exactly one `core` item resolves to `massive` / `Search-Endpoints` (no duplicates).
- [x] 4.4 `sqlite3 mcp/daas.db "SELECT name FROM categories WHERE name='Massive';"` → one row; and its parent is `Market-Data`.

## 5. `--unseed` rollback symmetry (on a throwaway copy, not the live DB)

- [x] 5.1 Copy `mcp/daas.db` to a temp path and point `DAAS_DATABASE_URL` at it: `cp mcp/daas.db /tmp/daas-unseed-test.db && export DAAS_DATABASE_URL="sqlite:////tmp/daas-unseed-test.db"`.
- [x] 5.2 Run `uv run --directory mcp/daas-mcp python seed_external_mcps.py --unseed` against the copy and confirm: `massive` gone from `sources`; no `datasource_forms`/`datasource_sections` rows reference the removed source; the `Massive` leaf category is gone; the `core` collection no longer has a `massive` item; and `ckan` / `cnstats` / `worldbank` rows survive.
- [x] 5.3 Re-run the seed (no flags) against the copy and confirm `massive` and all its forms/sections/category/collection-item are restored — proves the `daas.db` state is fully reproducible from the committed seed.
- [x] 5.4 Discard the temp DB: `rm /tmp/daas-unseed-test.db; unset DAAS_DATABASE_URL`.

## 6. Commit

- [x] 6.1 Stage `mcp/daas-mcp/seed_external_mcps.py`, `openspec/specs/external-mcp-datasource-seed/spec.md`, and the `openspec/changes/add-massive-mcp-datasource/` artifacts. **`mcp/daas.db` is excluded** (per user decision — it carries unrelated churn from other seeds, and the `massive` rows are reproducible by re-running the seed).
- [x] 6.2 Commit in one revision with message `Add massive-mcp as the 7th daas datasource (external-mcp-datasource-seed)` — the seed-script edit, its spec contract, and the change artifacts land together so a future `--unseed` + re-seed reproduces the `massive` rows.
