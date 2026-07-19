---
name: fd-daas-indicators-collection-creator
description: Create a curated collection of daas indicators, surface each member's resolved score (inheriting the datasource default via the existing 3-level resolution), and write a machine-readable CSV + a human-readable introduction markdown. Use this skill whenever the user wants to group indicators into a named collection, curate an indicator watchlist, or export an indicator set with its scores - phrases like "把这几个指标存成一个 collection", "create an indicators collection for these", "group these indicators", "curate an indicator set", "export these indicators with scores to a CSV", or any indicators + "collection / group / 专题 / 集合 / 导出". Each member's score inherits its datasource's default via the existing 3-level resolution (item override -> indicator default -> datasource sources.score). Do NOT use this skill to create individual indicators (use fd-daas-indicators-creator) or to build dashboards (use fd-daas-dashboard-creator). Uses sqlite3 on daas.db - NO MCP tools.
---

# fd-daas-indicators-collection-creator

Curate a named collection of indicators -> surface each member's resolved score (inheriting the datasource default) -> write a machine-readable **CSV** + a human-readable introduction markdown. All via **sqlite3** on daas.db.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` (currently `sqlite:///daas.db`). From repo root, `sqlite3 daas.db "..."` works.

## Mental model

1. **Propose** -> collection name + member indicator list. Confirm.
2. **Create + add** -> `sqlite3` INSERT into `indicator_collections` + `indicator_collection_items`.
3. **Surface resolved scores** -> `sqlite3` query with `COALESCE(item.score, r.score, s.score)` (3-level resolution).
4. **Write the CSV** -> `daas-doc/indicators-collections/<collection>.csv`.
5. **Write the introduction md** -> `daas-doc/indicators-collections/<collection>.md`.

## Step 1 - Propose the collection

1. Collect a `name` (kebab-case) + optional `description`.
2. Collect member indicator names. They MUST already exist in `indicator_rules`:
   ```bash
   sqlite3 daas.db "SELECT name, datasource, op FROM indicator_rules ORDER BY name"
   ```
   If a proposed member doesn't exist, tell the user, drop it, re-ask. Do not invent indicator names.
3. Show a numbered proposal (name + description + members). Ask: "Create this collection with N members?" **Gate** until confirmed.

## Step 2 - Create the collection and add members

```bash
sqlite3 daas.db "INSERT INTO indicator_collections (name, description) VALUES ('<name>', '<desc>')"
# per member (indicator_id from indicator_rules by name)
sqlite3 daas.db "INSERT INTO indicator_collection_items (collection_id, indicator_id, sort_order) VALUES ((SELECT id FROM indicator_collections WHERE name='<name>'), (SELECT id FROM indicator_rules WHERE name='<member>'), <n>)"
```

`score` is optional - leave NULL to inherit (3-level resolution). **Duplicate name**: UNIQUE constraint fails - offer to add to the existing collection.

## Step 3 - Surface resolved scores

```bash
sqlite3 daas.db "SELECT r.name AS indicator, r.datasource, r.op, r.params_json, r.source_table, r.value_column, r.date_column, r.enabled, COALESCE(i.score, r.score, s.score) AS resolved_score, i.score AS item_score, r.score AS indicator_default_score, s.score AS source_default_score FROM indicator_collection_items i JOIN indicator_rules r ON r.id=i.indicator_id JOIN sources s ON s.name=r.datasource WHERE i.collection_id=(SELECT id FROM indicator_collections WHERE name='<name>') ORDER BY i.sort_order"
```

Show a table: `indicator | datasource | op | params | source_table | value_column | resolved score | item_score | indicator_default_score | source_default_score`. Highlight "inherit" rows (item_score null, resolved == source_default_score). **Do NOT recompute scores** - the `COALESCE` is the resolution.

## Step 4 - Write the CSV

One row per member, columns: `collection, indicator, datasource, op, params, source_table, datasource_columns (value_column, date_column), score (resolved), item_score, indicator_default_score, source_default_score, enabled`.

**Path**: `daas-doc/indicators-collections/<collection>.csv` (create the dir on first use). **CSV escaping (RFC 4180)**: fields with a comma/quote/newline get wrapped in `"..."`; `"` inside -> `""`; null -> empty cell; booleans lowercase. Write with the `Write` tool. Report row count + path. **Empty collection**: don't write a header-only CSV - report empty and STOP.

## Step 5 - Write the introduction markdown

**Path**: `daas-doc/indicators-collections/<collection>.md`. Content: `# <collection>` + description, created date, a member table (the columns from Step 3), a pointer to the sibling CSV, a "How to refresh" note ("re-run `run_indicator.py <name>` for each member"), and a one-line score-inheritance note.

## Gotchas

- **No score recomputation.** The `COALESCE(item.score, r.score, s.score)` IS the 3-level resolution - render it verbatim. Don't `UPDATE` scores to "sync".
- **Members must pre-exist** in `indicator_rules`. Confirm in Step 1.
- **CSV escaping is the bug surface** - `params` (JSON) and `datasource_columns` routinely contain commas. Quote per RFC 4180.
- **Nesting** is signaled by a `workflow-name <X>` token in `args` (if used inside a workflow skill) -> write to `daas-doc/<X>/indicators-<collection>.{csv,md}` instead.
- This skill stops at the CSV + md. To compute new indicators, use `fd-daas-indicators-creator`. To build a dashboard, use `fd-daas-dashboard-creator`.
