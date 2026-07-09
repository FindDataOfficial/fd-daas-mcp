## Context

daas-mcp already has two parallel collection concepts:

1. **`datasource_collections`** — NotebookLM-style curation of *datasources* (CRUD + membership + scores + reorder). Backend in `registry_service.py` + `daas_tools.py`, writes via the `collection_writer.py` CLI sidecar, dashboard at `/collections`.
2. **`pipeline_collections`** — managed fetch+cron collections binding a source MCP tool to a `scraw_<slug>` table with a cron cadence.

It also has an **entity registry** (`entities` table of stocks + countries, `entity_datasource_links` to datasources, `entity_sync.py` for akshare-backed population + idempotent `--register-cron`).

What is missing is the *combination*: named collections of **entities** (watchlists/portfolios), an audit trail of membership transitions (add-in / remove-out), and a scheduled re-evaluation of rule-based membership. The `entity-registry` and `entity-datasource-coverage` specs stay unchanged; this is a new layer on top of `entities`.

Constraints inherited from the repo:
- Schema lives in `mcp/models/models.py` (single `Base`); tables created via `Base.metadata.create_all`, no Alembic; additive `ALTER TABLE` migrations are guarded on `PRAGMA table_info`.
- daas-mcp tools are thin wrappers over a `RegistryService` (`registry_service.py`); writes are idempotent and return `{"success": ..., ...}` / `{"success": false, "error": ...}`.
- Dashboard writes spawn `uv run --directory mcp/daas-mcp python collection_writer.py <command> --json {...}` (`dashboard/src/lib/py-cli.ts`); reads use sql.js (`getDb('daas.db')` + `queryAll`).
- cron-mcp tasks are shell commands; the daas-mcp server already has `--run-rule` / `--run-indicator` / `--fetch-item` CLI branches that run a path in-process and exit. `entity_sync.py --register-cron` is the template for idempotent cron registration.
- SQLite `PRAGMA foreign_keys=ON` is set per-connection in `daas_database.py`, so `ON DELETE CASCADE` works.

## Goals / Non-Goals

**Goals:**
- Named entity collections (CRUD) on top of the existing `entities` table, parallel in shape to `datasource_collections`.
- Membership add/remove that **records every transition** in a dedicated audit-log table (`entity_collection_changes`) with `action ∈ {add_in, remove_out}`, `source ∈ {manual, cron}`, `reason`, `changed_at`.
- Optional rule-based membership (`rule_json`) that can be re-evaluated deterministically by a `sync_entity_collection` operation.
- A cron-mcp-schedulable sync (CLI branch + idempotent registrar) that applies add-in/remove-out diffs and logs them.
- A dashboard `/entities` workspace for the whole lifecycle, including a history view.
- Docs updated (`construction/daas-storage.md`, `CLAUDE.md`).

**Non-Goals:**
- No LLM extraction, no scoring, no per-item column aggregation — those belong to datasource collections / coverage, not entity collections.
- No changes to `entities`, `entity_datasource_links`, `entity_sync.py`, or the `entity-registry` / `entity-datasource-coverage` / `entity-sync` specs.
- No chat pane in the entity-collections workspace (the `/collections` chat is scoped to datasource collections; entity collections get list/detail/history only).
- No rule language beyond the fixed `rule_json` keys (`entity_type`, `exchange`, `country_code`, `codes`, `name_regex`); arbitrary Python/SQL rule expressions are out of scope.
- No bulk import / CSV upload in v1 (members are added one at a time via search; a `codes` list in `rule_json` covers the bulk-rule case).

## Decisions

### Decision: Three tables — current membership + append-only audit log

Use `entity_collections` (metadata), `entity_collection_items` (current members, `UNIQUE(collection_id, entity_id)`), and `entity_collection_changes` (append-only audit log of every add_in / remove_out).

**Why not a single table with a `status` column**: the user explicitly asked for "a table to record it" (the add-in / remove-out transitions). A separate append-only log is queryable independently of current membership, preserves full history after deletes, and matches the "record every transition" semantic. Keeping `entity_collection_items` as the *current* truth makes `list_entity_collection_items` a simple filtered query (no `status='active'` plumbing everywhere) and lets `sync` diff two sets cleanly.

**Why cascade on both `entity_id` and `collection_id`**: deleting an entity should not leave dangling membership/history; deleting a collection should remove all its rows. `PRAGMA foreign_keys=ON` is already set per-connection.

**Alternatives considered**: (a) single `entity_collection_items` with `status` + `removed_at` — rejected per above; (b) reuse `datasource_collection_items` with a polymorphic `entity_id` column — rejected, mixes two domains and breaks FK integrity.

### Decision: Membership rule is a fixed-shape JSON, not a DSL

`rule_json` = `{"entity_type"?, "exchange"?, "country_code"?, "codes"?, "name_regex"?}`. `sync_entity_collection` builds a single SQLAlchemy query with `AND`-combined filters. `codes` is a list matched by `Entity.code.in_(...)`. `name_regex` uses `Entity.name.op('REGEXP')` (SQLite `REGEXP` is registered by SQLAlchemy's default for Python-side regex via `RE` if available; otherwise fall back to `LIKE` on a pre-filtered set — see Risks).

**Why not a generic expression DSL** (like alerts-mcp's `expressions.evaluate`): entity collections are curated watchlists, not alert conditions. A fixed shape is auditable, trivially serializable in the dashboard form, and enough for "all SSE stocks", "these 30 codes", "US country". The alerts-mcp DSL is deliberately narrow and `ast.parse`-whitelisted; reusing it here would import complexity (and a whitelist of funcs) that has no watchlist use case.

**Why `rule_json` lives on the collection, not per-item**: the rule defines the *intended set*; sync diffs intended vs current. Per-item rules would not compose into a set.

### Decision: Sync is set-diff, source='cron', idempotent

`sync_entity_collection(name)`:
1. Load `rule_json`; if NULL → no-op summary.
2. Compute `intended = set(entity_id)` by applying the rule filter to `entities`.
3. Load `current = set(entity_id)` from `entity_collection_items`.
4. `to_add = intended - current` → insert membership rows (sort_order = max+1 each) + append `add_in`/`source='cron'` changes.
5. `to_remove = current - intended` → delete membership rows + append `remove_out`/`source='cron'` changes.
6. Commit; return `{"added": [...], "removed": [...], "unchanged": len(intended & current)}`.

Re-running with no entity changes → `to_add` and `to_remove` empty → no changes recorded. This satisfies the idempotent scenario.

**Why `source='cron'` even when sync is triggered manually from the dashboard**: the dashboard "Sync now" button calls the same sync path. We distinguish `manual` (a human adding/removing one entity) from `cron` (a bulk rule-driven re-evaluation) — the latter is `source='cron'` regardless of trigger, because it's the rule-driven path. This keeps the history readable: "these 12 add_ins happened in one sync tick". (If we later want to distinguish dashboard-triggered syncs from cron-triggered ones, add a `trigger` field; out of scope here.)

### Decision: CLI branch + `entity_collection_sync.py` registrar (mirror `entity_sync.py`)

- `server.py --sync-entity-collection <name>` → in-process sync, JSON summary, exit. This is the cron-mcp task command.
- `entity_collection_sync.py` is a small script with `--sync <name>`, `--register-cron <name>`, `--unregister-cron <name>`, `--dry-run`. `--register-cron` inserts `tasks`/`schedules` rows idempotently (names `entity-collection-sync-<name>` / `entity-collection-sync-<name>-daily`), mirroring `entity_sync.py --register-cron`.

**Why a separate script and not just the CLI branch**: the CLI branch is the *runtime* entry point (what cron-mcp runs); the script is the *management* entry point (register/unregister the schedule, ad-hoc sync with `--dry-run`). This is exactly the split `entity_sync.py` already has (`--sync-all` runtime vs `--register-cron` management), so operators get one consistent mental model.

**Why daily default cadence**: watchlist membership rarely changes intra-day; daily is a safe default. The schedule row's `cron_expr` can be edited in the dashboard's `/cron` page after registration.

### Decision: Dashboard writes reuse `collection_writer.py` (extended), reads use sql.js

Extend `collection_writer.py` with new subcommands: `create-entity-collection`, `update-entity-collection`, `delete-entity-collection`, `add-entity-item`, `remove-entity-item`, `reorder-entity-items`, `sync-entity-collection`. The dashboard's `/api/entities/*` routes call `runPythonCli('collection_writer.py', '<command>', {...})` — same pattern as `/api/collections/*`. Reads (list, detail, history) go through sql.js in `dashboard/src/lib/entity-collections.ts`.

**Why not call daas-mcp MCP tools directly from the dashboard**: the existing `/collections` write path deliberately uses the `collection_writer.py` sidecar (one process per write, no stdio MCP client lifecycle in the Next.js route). Reusing it keeps the write path identical and avoids a second write mechanism. The daas-mcp MCP tools remain the source of truth for non-dashboard clients (agents, cron).

### Decision: Models in `mcp/models/models.py`, service in `registry_service.py`

Add `EntityCollection`, `EntityCollectionItem`, `EntityCollectionChange` to `mcp/models/models.py`. Add `EntityCollectionService` methods to `registry_service.py` (it already owns entity + collection logic and shares one session). Tool wrappers in a new `entity_collection_tools.py` (mirrors `entity_tools.py`). `collection_writer.py` calls the same service methods.

## Risks / Trade-offs

- **[SQLite `REGEXP` not built-in]** → `name_regex` may fail on stock SQLite builds. Mitigation: register a Python-side `REGEXP` function on the engine via `event.listens_for(engine, "connect")` (SQLAlchemy supports this), or fall back to `LIKE('%'+substr+'%')` when `name_regex` is set and `REGEXP` is unavailable. Document the fallback in the rule spec. Low risk — `name_regex` is the least-used rule key.
- **[Audit log grows unbounded]** → `entity_collection_changes` is append-only and could grow large for frequently-synced collections. Mitigation: `list_entity_collection_changes` defaults to `limit=100` with `offset` pagination; a future cleanup task can prune changes older than N days. Out of scope here.
- **[Sync race with manual edits]** → a user adding an entity while a cron sync is running could see their add immediately removed by the rule diff. Mitigation: sync runs in one transaction; manual adds commit before sync reads `current`. The window is small (sync is sub-second for thousands of entities). Documented as expected behavior — a manual add to a rule-based collection that doesn't match the rule *will* be removed on the next sync; users who want manual members should use a manual (`rule_json=NULL`) collection or extend the rule.
- **[Re-adding after remove creates a second add_in]** → by design (append-only log). `list_entity_collection_changes` will show `add_in → remove_out → add_in` for a re-added entity. This is the correct audit semantic, not a bug.
- **[Entity deleted while in a collection]** → cascade removes the membership row AND its history rows (FK CASCADE on `entity_id`). The collection's other history is preserved. Trade-off: we lose the audit trail for deleted entities. Acceptable — deleted entities are themselves gone. If history retention is later required, soft-delete entities instead (out of scope).

## Migration Plan

1. Add the three models to `mcp/models/models.py`. `Base.metadata.create_all` creates the tables on the next daas-mcp start (and on dashboard read, which also calls `create_all`). No data migration — tables start empty.
2. Implement service methods + tool wrappers + `collection_writer.py` subcommands + CLI branch + `entity_collection_sync.py`.
3. Add `selfcheck_entity_collections.py` (temp DB, no network, no LLM) covering: create/list/get/update/delete, add/remove with change recording, re-add no-op, remove non-member no-op, reorder, history query + filters, rule-based sync (add/remove/idempotent), manual-collection sync no-op, CLI branch.
4. Dashboard routes + pages + nav + sql.js reads.
5. Update `construction/daas-storage.md` and `CLAUDE.md` daas-mcp section.
6. **Rollback**: drop the three tables (`DROP TABLE entity_collection_changes; DROP TABLE entity_collection_items; DROP TABLE entity_collections;`), remove the tools/routes/pages. No dependency from existing features on these tables, so rollback is clean.

## Open Questions

- **Default sync cadence**: daily (`0 7 * * *`-ish, off-minute) is the plan. Confirm or pick a different default. (Decision: daily off-minute, editable later via `/cron`.)
- **Should `--register-cron` register one schedule per collection, or one schedule that syncs *all* rule-based collections?** Plan: per-collection (one task/schedule per `--register-cron <name>`), so each collection can have its own cadence and can be unregistered independently. A `--register-cron-all` convenience can be added later.
