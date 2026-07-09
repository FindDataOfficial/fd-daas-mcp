## 1. Schema (mcp/models)

- [x] 1.1 Add `score = Column(Float, nullable=True, default=None)` to `DaasSource` in `mcp/models/models.py`; add `"score": self.score` to `DaasSource.to_dict()`
- [x] 1.2 Add `score = Column(Float, nullable=True, default=None)` to `DatasourceCollectionItem` in `mcp/models/models.py`; add `"score": self.score` to `DatasourceCollectionItem.to_dict()`
- [x] 1.3 Reinstall `mcp-models` (`pip install -e mcp/models`) so dependents pick up the new columns

## 2. Migrations (daas_database.py)

- [x] 2.1 Add `_migrate_sources_score()` to `mcp/daas-mcp/daas_database.py` — guard on `PRAGMA table_info("sources")`, `ALTER TABLE sources ADD COLUMN score REAL` when absent; call it from `__init__` after `_migrate_collection_items_sort_order`
- [x] 2.2 Add `_migrate_collection_items_score()` — same guard on `datasource_collection_items`, `ALTER TABLE datasource_collection_items ADD COLUMN score REAL`; call it from `__init__`
- [x] 2.3 Start daas-mcp against the existing `mcp/daas.db` and verify both columns exist (`sqlite3 mcp/daas.db "PRAGMA table_info(sources); PRAGMA table_info(datasource_collection_items);"`); verify re-running init is a no-op

## 3. Service layer (registry_service.py)

- [x] 3.1 Thread `score: Optional[float] = None` through `create_datasource`; set it on the new `DaasSource`
- [x] 3.2 Thread `score: Optional[float] = None` + `clear_score: bool = False` through `update_datasource`; when `clear_score` set `src.score = None`, elif `score is not None` set `src.score = score`; ensure `to_dict` surfaces it
- [x] 3.3 Thread `score: Optional[float] = None` through `add_to_collection`; set it on the new `DatasourceCollectionItem`
- [x] 3.4 Add `set_collection_item_score(collection_name, source_name, section_name=None, score=None)` — resolve the item like `remove_from_collection` does, set/clear `item.score`, commit, return the updated item dict (include resolved effective score + source default)
- [x] 3.5 Update `list_collection` to add `score` (resolved), `item_score` (raw override), `source_default_score` (raw default) to each resolved item; resolve by reading `it.score` then falling back to the joined source's `score`
- [x] 3.6 Add a small `_resolve_effective_score(item_score, source_default_score)` helper (or inline) used by both `list_collection` and `set_collection_item_score`'s return

## 4. MCP tools (daas_tools.py + server.py)

- [x] 4.1 Add `score: Optional[float] = None` param to `create_datasource` in `daas_tools.py`; pass through to service
- [x] 4.2 Add `score: Optional[float] = None` + `clear_score: bool = False` params to `update_datasource`; pass through
- [x] 4.3 Add `score: Optional[float] = None` param to `add_to_collection`; pass through
- [x] 4.4 Add new `set_collection_item_score(collection_name, source_name, section_name=None, score=None)` tool function with a clear docstring (note `score=None` clears the override); wrap service call with `_ok`/`_err`
- [x] 4.5 Register `set_collection_item_score` in `server.py` via `app.tool(...)`
- [x] 4.6 Restart daas-mcp; verify `list_sources`, `list_collection`, and `set_collection_item_score` are exposed and `update_datasource` accepts `score`/`clear_score`

## 5. Writer sidecar (collection_writer.py)

- [x] 5.1 Add `set-source-score` and `set-item-score` to the `choices` in `collection_writer.py`'s argparse parser
- [x] 5.2 Implement `set-source-score` branch → `svc.update_datasource(name=args["name"], score=args.get("score"), clear_score=(args.get("score") is None))`
- [x] 5.3 Implement `set-item-score` branch → `svc.set_collection_item_score(collection_name=…, source_name=…, section_name=args.get("section_name"), score=args.get("score"))`
- [x] 5.4 Smoke-test both subcommands against the existing `mcp/daas.db`: `uv run --directory mcp/daas-mcp python collection_writer.py set-source-score --json '{"name":"edgar","score":0.9}'` and `set-item-score --json '{"collection_name":"…","source_name":"edgar","score":0.8}'`; verify JSON output and that `score=null` clears

## 6. Dashboard read path (lib/)

- [x] 6.1 Add `SourceScoreRow` and `CollectionScoreItem` types to `dashboard/src/lib/schema.ts` (name, label, score, etc.)
- [x] 6.2 Add `loadSourceScores()` to `dashboard/src/lib/collections.ts` (or a new `lib/scores.ts`) — `SELECT id, name, label, score FROM sources ORDER BY name` via `getDb('daas.db')`
- [x] 6.3 Add `loadCollectionScores(name)` — join `datasource_collection_items` to `sources` returning each item's `item_id, source_name, section_name, item_score, source_default_score, resolved_score` ordered by `sort_order`
- [x] 6.4 Update the existing `CollectionItem` type and `loadCollection` query to carry `item_score` / `source_default_score` / resolved `score` (so the collections workspace can show scores later if desired)

## 7. Dashboard API routes

- [x] 7.1 Create `dashboard/src/app/api/scores/source/route.ts` — `POST { name, score }` → `runPythonCli('collection_writer.py', 'set-source-score', { name, score })`; map `not found` → 404; on success `invalidateDb('daas')` and return the updated datasource dict
- [x] 7.2 Create `dashboard/src/app/api/scores/item/route.ts` — `POST { collection_name, source_name, section_name?, score }` → `runPythonCli('collection_writer.py', 'set-item-score', …)`; map `not found` → 404; on success `invalidateDb('daas')` and return the updated item dict
- [x] 7.3 Validate inputs (non-empty `name`/`collection_name`/`source_name`; `score` is number or null) and return 400 on bad input

## 8. Dashboard UI (/scores)

- [x] 8.1 Create `dashboard/src/app/scores/page.tsx` (server component) — load `loadSourceScores()` + `loadCollections()` and render a `<ScoresManager>` client component
- [x] 8.2 Create `dashboard/src/components/scores/scores-manager.tsx` (client) with two sections: **Default scores** (table of all datasources with inline number input + Save) and **Collection scores** (collection `<select>` + the selected collection's items table with inline score + read-only default column + resolved score)
- [x] 8.3 Implement Save handlers: `POST /api/scores/source` for default-score edits, `POST /api/scores/item` for per-item edits; treat empty input as `null` (clear) and explicit `0` as `0`; refresh read state from the response
- [x] 8.4 Show resolved effective score in the collection table (override if set, else default, else "—"); show a subtle hint when an override is active
- [x] 8.5 Add a "Scores" entry to `dashboard/src/components/nav.tsx` (after "Datasources")
- [x] 8.6 Visit `/scores` end-to-end: set a default score on a datasource, pick a collection, set an item override, verify resolved score flips from default to override, clear the override, verify it falls back

## 9. Self-check + docs

- [x] 9.1 Add a score round-trip to `mcp/daas-mcp/selfcheck_collection_writer.py` (or a new `selfcheck_scores.py`): set-source-score + set-item-score land rows, `list_collection` resolves correctly, `score=null` clears — temp DB, no network
- [x] 9.2 Run `uv run --directory mcp/daas-mcp python selfcheck.py` (and the collection-writer self-check) to verify no regressions
- [x] 9.3 Update `CLAUDE.md` daas-mcp section: note the `score` columns, the `set_collection_item_score` tool, the `score`/`clear_score` params on create/update datasource, and the `/scores` dashboard page
- [x] 9.4 Run `openspec validate add-datasource-score --strict` to confirm the change artifacts are well-formed
