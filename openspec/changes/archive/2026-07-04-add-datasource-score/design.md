## Context

daas-mcp manages datasources (rows in `sources`) and groups them into named `datasource_collections` via the `datasource_collection_items` join table. Today there is no notion of priority or quality weight on a datasource, and no per-collection override — when an agent or the collection chat resolves a request against several datasources in a collection, there is no signal for which to prefer.

The dashboard already has a collections workspace (`/collections`, `/collections/manage`) that reads via sql.js (`getDb('daas.db')` + `queryAll`) and writes through a Python CLI sidecar (`collection_writer.py`) spawned one-process-per-call by Next.js API routes. The schema lives in the shared `mcp/models/models.py` package; migrations are guarded `ALTER TABLE ADD COLUMN` calls in `daas_database.py` (see `_migrate_sources_category_id`, `_migrate_collection_items_sort_order`). Score columns fit this exact pattern.

## Goals / Non-Goals

**Goals:**
- Add a nullable `score` (Float) to `sources` (default score) and to `datasource_collection_items` (per-collection override).
- Define and surface a resolution rule: effective score = item override if not NULL, else datasource default, else NULL.
- Let agents set scores via MCP tools (`create_datasource` / `update_datasource` / `add_to_collection` / new `set_collection_item_score`) and read resolved scores via `list_collection`.
- Let users manage both levels from a single `/scores` dashboard page using the existing sql.js read path + `collection_writer.py` write sidecar.
- Zero impact on existing tools, queries, and the catalog/chat workspace — new columns default to NULL.

**Non-Goals:**
- Auto-deriving scores from data quality, freshness, or coverage metrics (manual entry only for v1).
- Changing the collection chat routing to actually consume scores (scores are surfaced but the chat's tool selection is unchanged — a future change can wire consumption).
- Scoring pipeline-collection items (`pipeline_collection_items`) — only the curation `datasource_collection_items` are scored.
- Bulk import / scoring formulas / weight templates.

## Decisions

### Decision 1: Float (REAL), nullable, default NULL

**Chosen**: `score = Column(Float, nullable=True, default=None)` on both tables. NULL means "unset" / "inherit".

**Rationale**: Float allows decimal weights like `0.85` (a normalized 0–1 score) and integer scores like `5` equally. Nullable + NULL default means every existing row is "no score" after migration, so resolution has a clean fallback chain (item → source → NULL) and the dashboard shows blank rather than `0` for unscored datasources (a `0` score would be a deliberate "deprioritize" signal, distinct from "no opinion"). This mirrors how `category_id` and `sort_order` were added (nullable/`NOT NULL DEFAULT 0` respectively, additive `ALTER TABLE`).

**Alternative considered**: `Integer` 1–100. Rejected — too prescriptive about scale; users may want 0–1 or arbitrary weights.

**Alternative considered**: A separate `datasource_scores` table keyed by `(source_id, collection_id)`. Rejected — it would duplicate the join semantics already captured by `datasource_collection_items` and require a JOIN for every read of a collection. The per-item override belongs on the item row; the default belongs on the source row.

### Decision 2: Per-item override lives on `datasource_collection_items`, not on a new join

**Chosen**: Add `score` directly to `datasource_collection_items`.

**Rationale**: An item already uniquely identifies a `(collection, source, optional section)` triple via its existing UNIQUE constraint. A score is an attribute of *that item in that collection*, so it belongs on the item row. This matches how `sort_order` is stored on the item. `list_collection` already reads every item row, so the override is free to surface (no extra query); the datasource default comes from the already-joined `sources` row.

**Alternative considered**: A separate `collection_item_scores` table. Rejected — same JOIN cost as putting it on the item, with no benefit.

### Decision 3: One new tool `set_collection_item_score`, default-score set via `update_datasource`

**Chosen**: Default score is set through the existing `update_datasource(name, score=…, clear_score=…)`. Per-item override is set through a new `set_collection_item_score(collection_name, source_name, section_name?, score)` tool. `add_to_collection` also accepts an optional `score` for set-at-add-time convenience.

**Rationale**: There is already an "update a datasource" tool — adding `score` to it is the natural extension and avoids a redundant `set_datasource_score` tool. There is *no* "update a collection item" tool today (items are only added/removed/reordered), so a dedicated `set_collection_item_score` is needed; reusing `update_collection` would be wrong (that edits collection metadata, not items). `add_to_collection(score=…)` is a convenience that avoids a second call right after adding.

**Alternative considered**: A generic `update_collection_item` tool that edits any item field. Rejected — `score` is the only mutable item field today; a generic editor is speculative surface area. Add it later if more fields appear.

### Decision 4: Resolution surfaced in `list_collection`, not a separate tool

**Chosen**: `list_collection` returns each item with three fields: `score` (resolved), `item_score` (raw override), `source_default_score` (raw default). No separate `get_effective_score` tool.

**Rationale**: Consumers (agents, dashboard, collection chat) already call `list_collection` to enumerate items; baking the resolution into that result avoids an extra round-trip per item. Surfacing all three values (not just the resolved one) lets the UI show "override = 0.8 (default 0.5)" without a second query. A standalone `get_effective_score` would be N calls for N items.

**Alternative considered**: Return only the resolved `score`. Rejected — the dashboard needs to show the default alongside the override so the user knows what they're overriding.

### Decision 5: Dashboard write path = `collection_writer.py` subcommands (existing sidecar)

**Chosen**: Add `set-source-score` and `set-item-score` subcommands to the existing `collection_writer.py`. Two new API routes (`/api/scores/source`, `/api/scores/item`) call them via `runPythonCli`. Reads go through sql.js (`getDb('daas.db')` + `queryAll`).

**Rationale**: This is the established write pattern (see `/api/collections/[name]/items` → `collection_writer.py add-item`). Spawning one Python process per write is slow but writes are infrequent (a user editing scores), and it keeps all DB writes behind the same sidecar that already loads `.env` and resolves the DB URL against the repo root (the resolution bug that `daas-writer-relative-db-url-broken` fixed). A new sidecar would duplicate that bootstrap; calling `RegistryService` directly from Next.js is impossible (Python vs. TS).

**Alternative considered**: A new `score_writer.py` sidecar. Rejected — `collection_writer.py` already owns collection-item writes and the same `__file__`-anchored repo-root resolution; `set-item-score` is a collection-item write, so it belongs there. `set-source-score` is a datasource write, but keeping both score subcommands in one sidecar keeps the score feature's write surface in one place.

### Decision 6: `set_collection_item_score` resolves items by `(collection, source, section)`, not by item id

**Chosen**: The tool takes `collection_name` + `source_name` + optional `section_name` — the same identifiers `add_to_collection` / `remove_from_collection` use.

**Rationale**: Consistent with the existing collection-item tools (which are name-based, not id-based), so an agent doesn't need to first call `list_collection` to learn an item id. The dashboard also works in names (it already has them from the catalog). Internally the service resolves names to ids exactly as `remove_from_collection` does.

## Risks / Trade-offs

- **Schema migration on live `daas.db`**: Adding a nullable REAL column via `ALTER TABLE` is safe in SQLite and non-destructive. → Mitigation: guarded migration checking `PRAGMA table_info` (same as `category_id` / `sort_order`); idempotent on re-run; no-op on fresh DBs where `create_all` already added the column.
- **NULL vs 0 confusion in the UI**: A user may type `0` meaning "deprioritize" or leave the field blank meaning "no opinion". → Mitigation: dashboard treats an empty input as `null` (clear) and an explicit `0` as `0`; the Save button sends `null` when the field is blank. Documented in the spec scenarios.
- **Resolution not consumed yet**: Scores are stored and surfaced but nothing in the collection chat yet prefers high-score datasources. → Mitigation: explicitly a Non-Goal for v1; a future change can wire consumption. Surfacing resolved scores in `list_collection` is the prerequisite that this change delivers.
- **Float comparison drift**: Comparing floats for equality is fragile, but scores are user-entered single values (not accumulations), so direct equality is fine. → Mitigation: none needed; no arithmetic is performed on scores by this change.

## Migration Plan

1. Ship `mcp/models/models.py` with the two new `score` columns (additive; `create_all` adds them on fresh DBs).
2. Ship `daas_database.py` guarded `_migrate_sources_score` + `_migrate_collection_items_score` (idempotent `ALTER TABLE ADD COLUMN score REAL`).
3. Ship the service / tool / writer changes.
4. On next `daas-mcp` start, the migrations run against the existing `mcp/daas.db`; existing rows get `score = NULL`. No data backfill is required.
5. Rollback: drop the two columns (`ALTER TABLE … DROP COLUMN` is supported in SQLite ≥ 3.35) — but since the columns are nullable and unused by existing tools, rollback is unnecessary; leaving them in place is harmless. The writer subcommands and API routes can be reverted independently.

## Open Questions

None — the resolution rule, types, and tool/dashboard split are decided above.
