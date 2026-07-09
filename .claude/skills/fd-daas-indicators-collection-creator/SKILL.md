---
name: fd-daas-indicators-collection-creator
description: Create a curated collection of daas indicators, surface each member's resolved score (inheriting the datasource default via the existing 3-level resolution), and write a machine-readable CSV + a human-readable introduction markdown. Use this skill whenever the user wants to group indicators into a named collection, curate an indicator watchlist, or export an indicator set with its scores — phrases like "把这几个指标存成一个 collection", "create an indicators collection for these", "group these indicators", "curate an indicator set", "export these indicators with scores to a CSV", or any indicators + "collection / group / 专题 / 集合 / 导出". Make sure to use this skill when the user mentions indicators they already have and wants them grouped, exported, or documented together — even if they don't explicitly say "collection". The skill reuses the existing daas-mcp indicator-collection tools (no new tables); each member's score inherits its datasource's default via the existing 3-level resolution (item override → indicator default → datasource `sources.score`). Do NOT use this skill to create individual indicators (use fd-daas-indicators-creator) or to build dashboards (use fd-daas-dashboard-creator).
---

# fd-daas-indicators-collection-creator

Curate a named collection of indicators → surface each member's resolved score (inheriting the datasource default) → write a machine-readable **CSV** (the primary artifact) **and** a human-readable introduction markdown.

## Mental model

Five steps, with an explicit confirmation gate before any daas-mcp write:

1. **Propose** → collection name + member indicator list. Get user confirmation.
2. **Create + add** → `create_indicator_collection` + `add_indicator_to_collection` (existing daas-mcp tools).
3. **Surface resolved scores** → `list_indicator_collection_items` (renders the existing 3-level score resolution verbatim — do NOT recompute). The fetched data also feeds Step 4.
4. **Write the CSV** → `daas-doc/indicators-collections/<collection>.csv` — one row per member, the machine-readable export.
5. **Write the introduction md** → `daas-doc/indicators-collections/<collection>.md` — the human-readable companion, co-located with the CSV.

Never call `create_indicator_collection` / `add_indicator_to_collection` before Step 1's confirmation gate.

## Step 1 — Propose the collection

Goal: agree on the collection name + members before writing anything.

1. Collect a collection `name` (kebab-case) + optional `description` from the user. If the user gives a Chinese/English phrase, slugify it (e.g. "动量指标" → `momentum`).
2. Collect the member indicator names. These MUST already exist in `indicator_rules` — search with `mcp__daas-mcp__list_indicators` to show what's available. If the user is unsure which indicators to include, surface the list (filterable by `datasource` / `op` in your own reasoning) and help them pick. Do not invent indicator names.
3. Show the user a numbered proposal: collection name + description + members. Ask: "Create this collection with N members?"
4. Gate — do not proceed to Step 2 until the user confirms.

**Unknown indicator**: if a proposed member does not exist in `indicator_rules` (verify via `list_indicators`), tell the user, drop it from the proposal, and re-ask. Do not create a collection that references a missing indicator — `add_indicator_to_collection` rejects an unknown name and leaves a half-created collection.

## Step 2 — Create the collection and add members

Goal: persist the collection + membership via the existing daas-mcp tools.

1. `mcp__daas-mcp__create_indicator_collection(name="<name>", description="<description>")`.
   - **Duplicate name**: the tool returns `{"error": "indicator collection already exists"}`. Offer to add members to the existing collection instead of recreating, or pick a new name.
2. For each member, `mcp__daas-mcp__add_indicator_to_collection(collection_name="<name>", indicator_name="<member>", score?, reason?)`.
   - `score` is optional — leave it unset to inherit (NULL → 3-level resolution kicks in). "Inherit the score" is the default behavior; only set `score` when the user wants a per-collection override.
   - Already-member is a no-op (`action: "already_member"`) — not an error.
3. Report: "Collection `<name>` created with N members."

## Step 3 — Surface resolved scores (and fetch the CSV data)

Goal: show each member's resolved score, inheriting the datasource default — without recomputing — AND gather the data Step 4 needs.

1. Call `mcp__daas-mcp__list_indicator_collection_items(collection_name="<name>")` → returns `{collection, count, items: [...]}`. Each item already carries the 3-level resolution:
   - `score` — the resolved effective score (item override, else indicator default, else datasource `sources.score`, else null).
   - `item_score` — the raw per-item override (null = inherit).
   - `indicator_default_score` — the indicator rule's own `score` (null = inherit).
   - `source_default_score` — the datasource's `sources.score`.
   - `indicator_name`.
2. Call `mcp__daas-mcp__list_indicators()` **once** and join by `indicator_name == rule.name` to get each member's `op` / `params` / `source_table` / `value_column` / `date_column` / `enabled` (these live on the indicator rule, not the membership row). Keep this joined result in context — Step 4 writes the CSV from exactly this data.
3. Show the user a table: `indicator | datasource | op | params | source_table | value_column | resolved score | item_score | indicator_default_score | source_default_score`. Highlight the "inherit" rows (where `item_score` is null and the resolved score == `source_default_score`).

**Do NOT recompute or copy scores.** The "inherit the datasource score" property is the existing 3-level resolution (`COALESCE(item.score, indicator_rules.score, sources.score)`); this skill only surfaces it. Do not call `set_indicator_collection_item_score` to "sync" anything.

## Step 4 — Write the CSV

Goal: persist a machine-readable member table with the resolved scores. One row per member, exact column order:

| column | source | notes |
|---|---|---|
| `collection` | the collection name | constant across rows; makes the CSV self-describing if moved |
| `indicator` | `item.indicator_name` (= rule `name`) | the rule identifier |
| `datasource` | `rule.datasource` | soft-ref to `sources.name` |
| `op` | `rule.op` | `sma` / `ema` / `rsi` / … |
| `params` | `rule.params` (a dict) | render as compact JSON, e.g. `{"window":5}` |
| `source_table` | `rule.source_table` | the table the indicator reads |
| `datasource_columns` | `rule.value_column` + `rule.date_column` | joined as `"<value_column>, <date_column>"` — the datasource columns the indicator operates on |
| `score` | `item.score` | resolved effective score (the inherited-or-overridden value) |
| `item_score` | `item.item_score` | raw per-item override; empty cell = inherit |
| `indicator_default_score` | `item.indicator_default_score` | the indicator rule's own score; empty = inherit |
| `source_default_score` | `item.source_default_score` | the datasource's `sources.score` |
| `enabled` | `rule.enabled` | `true` / `false` |

**Path**:
- **Standalone** (no `workflow-name <X>` token in this skill's `args`): write to `daas-doc/indicators-collections/<collection>.csv`. Create `daas-doc/indicators-collections/` on first use.
- **Nested inside `fd-daas-workflow-creator`** (the invoker passed `workflow-name <X>` in `args`): write to `daas-doc/<X>/indicators-<collection>.csv`. Create `daas-doc/<X>/` if missing.

**CSV escaping (RFC 4180)** — important, because `params` and `datasource_columns` regularly contain commas:
- Fields containing a comma `,`, a double quote `"`, or a newline → wrap the whole field in double quotes.
- Inside a quoted field, escape each `"` as `""`.
- Empty cell for `null` / `None` (this is how "inherit" shows up in `item_score` / `indicator_default_score`).
- Render booleans as `true` / `false` (lowercase) and numbers plainly (`0.6`, not `0.60`).

Write the file with the `Write` tool. Then report the row count + path to the user: "Wrote `<path>` with N rows."

**Empty collection**: if `list_indicator_collection_items` returns `count: 0`, do not write an empty CSV — report the empty state and STOP. A header-only CSV is not useful.

## Step 5 — Write the introduction markdown

Goal: persist a human-readable companion alongside the CSV. Same path stem, `.md` extension.

1. **Path** — co-locate with the CSV:
   - **Standalone**: `daas-doc/indicators-collections/<collection>.md`.
   - **Nested** (`workflow-name <X>` in `args`): `daas-doc/<X>/indicators-<collection>.md`.
2. **Content** — plain markdown, no JS, no external fetch (see `references/introduction-template.md` for the shape):
   - `# <collection>` + description (one line).
   - Created date.
   - A member table with the columns from Step 3 (including the four score fields).
   - A pointer to the sibling CSV: "Machine-readable export: `<collection>.csv`."
   - A "How to refresh" note: "re-run `mcp__daas-mcp__run_indicator(name)` for each member."
   - A one-line score-inheritance note: "Members with `item_score = null` inherit `indicator_default_score`, else `source_default_score` (the datasource's default)."
3. Report the file path to the user.

## Gotchas

- **No score recomputation.** `list_indicator_collection_items` already returns the resolved `score` + the three raw fields. Render them verbatim in both the CSV and the md — do not call `set_indicator_collection_item_score` to "sync" anything. The skill only writes files; the score state is the daas-mcp tools' job.
- **Members must pre-exist.** `add_indicator_to_collection` rejects an unknown indicator. Confirm membership in Step 1 (via `list_indicators`) to avoid a half-created collection.
- **CSV escaping is the bug surface.** `params` (JSON, often has commas) and `datasource_columns` (the `, `-joined pair) both routinely contain commas — quote them per RFC 4180. If you are unsure whether a field needs quoting, quote it; an over-quoted field is always safe, an under-quoted one silently corrupts the row.
- **Nesting is signaled by `args`.** The only way this skill knows it's nested inside `fd-daas-workflow-creator` is a `workflow-name <X>` token in the `args` string the invoker passed. No env var, no sentinel file. If the token is absent, write to the standalone path.
- **Plain markdown only.** The introduction md is a pointer + a table, not an interactive artifact. No CDN, no JS — it must render in any markdown viewer (and in `cat`).
- **This skill stops at the CSV + md.** To compute new indicators, use `fd-daas-indicators-creator`. To build a dashboard over a collection, use `fd-daas-dashboard-creator`.
