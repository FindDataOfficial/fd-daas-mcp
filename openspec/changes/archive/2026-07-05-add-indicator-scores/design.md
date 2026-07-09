## Context

`daas-mcp` already ships a scored-datasource concept: `sources.score` (a default priority/quality weight) plus a per-collection override `datasource_collection_items.score`, with a 2-level effective-score resolution (item override → datasource default) surfaced by `list_collection`. The `/scores` dashboard page manages it (`loadSourceScores` / `loadCollectionScores` in `dashboard/src/lib/scores.ts` → sql.js reads; `/api/scores/*` → `collection_writer.py set-source-score` / `set-item-score` writes). The score column was added additively via guarded `ALTER TABLE` migrations (`_migrate_sources_score` / `_migrate_collection_items_score` in `daas_database.py`).

Indicators live in `indicator_rules` (shared `mcp/models` `Base`, owned by `daas-mcp` after the `move-process-tools-to-daas` relocation). Each rule has a `datasource` soft-ref to `sources.name`. There is **no** indicator score, and **no** indicator-collection concept — operators cannot weight indicators relative to each other, cannot group them into reusable bundles, and cannot re-weight a single indicator differently per bundle. The user asked for the inheritance chain: **datasource score → indicator score (inherits) → indicator-collection-item score (inherits/overrides)** — one level deeper than the datasource precedent.

Constraints: schema changes go in `mcp/models/` first; all MCPs and the dashboard read/write `mcp/daas.db`; additive migrations only (no Alembic); the dashboard reads via sql.js (WASM, read-only) and writes via spawning `collection_writer.py` (no direct DB writes from the browser).

## Goals / Non-Goals

**Goals:**
- Add a nullable `score` to `indicator_rules` with NULL meaning "inherit the datasource's `sources.score`".
- Add an indicator-collections concept (named, ordered, reusable groups of indicators) with membership CRUD, sort order, and a membership audit log.
- Add a per-item `score` override on `indicator_collection_items` whose effective resolution chains **item-override → indicator-default → datasource-default** (3-level), surfaced everywhere indicators-in-a-collection are listed.
- Provide MCP tools, `collection_writer.py` subcommands, `/api/...` routes, and dashboard UI (inline score on the indicators page + a new indicators-collection page) to manage all of the above.
- Stay strictly additive: no breaking schema change, no data loss, no removed tools.

**Non-Goals:**
- No re-weighting of `observations` rows or re-running of `run_indicator` based on scores (scores are curation metadata, not computation inputs — same as datasource scores).
- No change to the existing `/scores` page or `datasource-scores` / `datasource-collections` capabilities.
- No LLM, no cron, no alerting wired to indicator scores in this change (a future change could add an alerts-mcp rule template keyed on indicator score).
- No bulk import / rule-based (regex) membership for indicator collections in this change (manual membership + audit only, like the initial entity-collections cut — `sync_indicator_collection` for rule-based re-derivation is deferred).

## Decisions

### Decision 1: Mirror the datasource-scores capability layout exactly
Three new capabilities — `indicator-scores` (score on `indicator_rules` + `set_indicator_score`), `indicator-collections` (the collection concept + per-item score override + 3-level resolution), `indicator-scores-dashboard-ui` (dashboard + writer + API) — paralleling `datasource-scores` / `datasource-collections` / `score-dashboard-ui`. The score param on `create_indicator`/`update_indicator` is owned by `indicator-scores` (the datasource precedent put `create_datasource(..., score=…)` in `datasource-scores`, not `datasource-management`), so `daas-indicators` is NOT a modified capability.
- **Alternatives considered**: (a) modify `daas-indicators` to own the score column — rejected because it conflates the indicator-rule concern with the score concern and breaks the precedent. (b) Fold indicator scores into `datasource-scores` — rejected because the resolution chain and the underlying table differ, and capabilities should be substitutable per concept.

### Decision 2: 3-level effective-score resolution
For an indicator in a collection, the resolved score is: `indicator_collection_items.score` if not NULL → else `indicator_rules.score` if not NULL → else `sources.score` (the datasource the indicator points at via `indicator_rules.datasource`). Surfaced as `score` (resolved) plus `item_score`, `indicator_default_score`, `source_default_score` for transparency, mirroring the `item_score` / `source_default_score` shape already returned for datasource collections. The resolution is computed in SQL (`COALESCE(i.score, ir.score, s.score)`) inside `list_indicator_collection_items` so the dashboard's sql.js read path returns the resolved value without a second round-trip.
- **Alternatives**: compute resolution only in Python — rejected because the dashboard reads via sql.js and would otherwise need a parallel resolver in TS.

### Decision 3: Real FK `indicator_collection_items.indicator_id → indicator_rules.id` with ON DELETE CASCADE
Unlike `indicator_rules.datasource` (a soft ref to `sources.name`, no FK — matching `ProcessRule`), the collection-item link is a real FK to `indicator_rules.id` with `ON DELETE CASCADE`, so deleting an indicator rule cleans up its collection memberships automatically. This matches `datasource_collection_items.source_id → sources.id` and `entity_collection_items.entity_id → entities.id`. `PRAGMA foreign_keys=ON` is already set per-connection by daas-mcp.
- **Alternatives**: soft ref by indicator name — rejected because it would leave dangling membership rows on rename/delete (the exact problem `entity_collection_items` avoided with a real FK).

### Decision 4: Membership audit log (add-in / remove-out) mirroring `entity_collection_changes`
A `indicator_collection_changes` table (`action` ∈ {add_in, remove_out}, `source` ∈ {manual, cron}, `reason`, `changed_at`) records every membership transition. `add_indicator_to_collection` / `remove_indicator_from_collection` write a row; no-op if membership is already in the target state. This gives the same audit surface the entity-collections feature ships, useful for "why is indicator X in this bundle" traceability.
- **Alternatives**: skip the audit log — rejected because the user explicitly wants per-collection indicator weighting and the audit log is the established pattern for collection membership in this repo.

### Decision 5: Additive schema, guarded ALTER for the score column
`indicator_collections` / `indicator_collection_items` / `indicator_collection_changes` are created via `Base.metadata.create_all` (additive, idempotent — same as `datasource_collections` and `entity_collections`). The `indicator_rules.score` column is added via a guarded `_migrate_indicator_rules_score` in `daas_database.py` that checks `PRAGMA table_info(indicator_rules)` for a `score` column before altering — exactly `_migrate_sources_score`'s shape. No Alembic, no data loss; existing rows get `score = NULL`.
- **Alternatives**: require a fresh `daas.db` — rejected; the project never does destructive migrations.

### Decision 6: `collection_writer.py` subcommands + `/api/...` routes mirror the score sidecar
New subcommands: `set-indicator-score` (args `{name, score}`), `set-indicator-collection-item-score` (args `{collection_name, indicator_name, score}`), plus the indicator-collection CRUD/membership subcommands (`create-indicator-collection`, `add-indicator-item`, `remove-indicator-item`, `reorder-indicator-items`, `delete-indicator-collection`). Routes: `POST /api/indicators/score`, `POST /api/indicators/collections`, `POST /api/indicators/collections/[name]/items/[indicator]/score`, etc. Each route spawns `collection_writer.py`, parses one JSON line, and calls `invalidateDb('daas')` on success — the same contract as `/api/scores/*`.
- **Alternatives**: have the dashboard call daas-mcp tools directly via `getMCPTools()` — rejected because the existing score write path deliberately uses the `collection_writer.py` sidecar (sql.js reads + writer writes resolve to the same `daas.db` only via the repo-root-relative URL fix; mixing in MCP-tool writes would re-introduce the dual-DB hazard documented in `daas-writer-relative-db-url-broken`).

### Decision 7: Dashboard route placement — `/process/indicators/collections`
The new indicators-collection page lives under the existing `/process/indicators` section (not a new top-level nav entry), because indicators themselves live there and the collection is a grouping of indicators. A "Collections" sub-tab/link on `/process/indicators` leads to `/process/indicators/collections` (list) and `/process/indicators/collections/[name]` (detail with add/remove/reorder + per-item score). The indicators page (`/process/indicators`) gains an inline-editable score column.
- **Alternatives**: top-level `/indicator-collections` mirroring `/collections` + `/entities` — rejected because indicators are already nested under `/process`; a top-level entry would orphan the collection from its concept. Revisit if the dashboard grows a top-level "Indicators" nav later.

### Decision 8: Indicator score on the indicator page references the datasource default
The inline score input on `/process/indicators` shows the indicator's `score` (blank when NULL = inherit) with a read-only "datasource default" hint column, so the operator sees what NULL inherits. The indicators-collection detail page shows, per row: indicator name, inline-editable item `score` (blank = inherit), read-only "indicator default" and "datasource default" columns, and the resolved effective score — mirroring the `/scores` collection layout.

## Risks / Trade-offs

- **[3-level resolution is one level deeper than the datasource precedent]** → document the chain explicitly in tool docstrings + the dashboard hint columns; the SQL `COALESCE(i.score, ir.score, s.score)` is the single source of truth and is covered in the self-check.
- **[`indicator_rules.datasource` is a soft ref, so the join to `sources.score` could miss if the datasource name is stale]** → the resolution falls through to NULL when the join misses (LEFT JOIN on `sources.name = indicator_rules.datasource`); `list_indicators` already surfaces the datasource name so staleness is visible. A future `entity_sync`-style reconciliation could mark stale datasources, but that is out of scope here.
- **[Real FK + cascade deletes membership rows when an indicator rule is deleted]** → this is intentional (no dangling memberships) but the audit log row survives (it is not FK-linked to the indicator), preserving "indicator X was removed from collection Y" history. Trade-off: the audit log references indicator *name* as a denormalized string for this reason.
- **[No rule-based / regex membership sync in this cut]** → manual-only membership; if an operator wants "all RSI indicators", they add them by hand. `sync_indicator_collection` is deferred to a future change (mirrors the entity-collections rule-based sync follow-on).
- **[Dashboard writes spawn a Python subprocess per action]** → acceptable for an admin-curation UI (same as `/scores` and `/entities`); not on a hot path.
- **[New `/api/indicators/collections/*` routes add surface area]** → each route is thin (spawn writer, parse JSON line, invalidate cache); the writer subcommands are the real logic and are covered by `selfcheck_indicator_scores.py`.

## Migration Plan

1. **Schema (additive, no breakage)**: add `IndicatorRule.score`, `IndicatorCollection`, `IndicatorCollectionItem`, `IndicatorCollectionChange` to `mcp/models/models.py`. On next daas-mcp/dashboard start, `Base.metadata.create_all` adds the 3 new tables and the guarded `_migrate_indicator_rules_score` adds the `score` column to any existing `indicator_rules`. Existing rows: `score = NULL` (inherit datasource). No data migration needed.
2. **Backend tools**: implement the indicator-score + indicator-collection tools in daas-mcp; wire into `process_api.py` / `server.py`.
3. **Writer + API**: add `collection_writer.py` subcommands; add dashboard `/api/indicators/*` routes.
4. **Dashboard UI**: extend `/process/indicators` score column; add `/process/indicators/collections` page tree.
5. **Self-check**: add `selfcheck_indicator_scores.py` (temp DB, no network) and run it; extend the existing dashboard E2E if a collection-creation flow is added (optional).
6. **Rollback**: drop the 3 new tables and the `indicator_rules.score` column (`ALTER TABLE indicator_rules DROP COLUMN score` on SQLite ≥3.35). No downstream data depends on them. The `.mcp.json` and existing tools are untouched.

## Open Questions

- Should `list_indicators` (the existing tool) resolve and return each indicator's effective default score (indicator score or datasource default)? **Proposed: yes, return `score` (raw) + `effective_score` (coalesced with datasource default) so the dashboard can show inheritance without a second query.** Confirm in tasks.
- Should the indicators-collection detail page reuse the NotebookLM-style 3-pane (catalog → collection → chat) from `/collections`, or stay a simple list+detail like `/entities`? **Proposed: simple list+detail (mirrors `/entities/[name]`)** — the chat pane is out of scope for this change. Confirm in tasks.
