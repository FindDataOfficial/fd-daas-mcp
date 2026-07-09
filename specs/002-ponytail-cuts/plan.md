# Plan — ponytail-audit cuts (Phases 1–3)

## Context
Repo-wide audit found ~38 over-engineering findings. Phases 1–3 only (Phase 4 dropped: 4a vendored scrapling scripts — keep; 4b harness mirror — keep independent). Several audit findings reclassified after verification (see below). All work is within single components; each change gated by that component's selfcheck / pytest / tsc+build.

## Reclassifications (correcting the audit)
- **cron-mcp `tasks/__init__.py` is NOT dead** — `registry.py:6` imports `run_backup`/`run_news_summary`/`run_weekly_report` and registers them. KEEP. Only the shadowed `tasks.py` is dead.
- **cron-mcp DB-task CRUD tools** (`create_task`/`delete_task`/`list_db_tasks`/`update_task`) **are exposed MCP surface** — KEEP (out of scope).
- **composite-mcp `seed_example.py`** is documented (CLAUDE.md, openspec) — FIX hardcoded absolute paths, do not delete.
- **scrapling vendored `scripts/`** — KEEP per decision (Phase 4a dropped).
- **harness mirror dedup** — SKIP per decision (Phase 4b dropped). Only within-harness cuts remain.

## Verification gates
- Python MCP: `uv run --directory mcp/<name> python selfcheck*.py`
- Harness: `uv run --directory <harness> python -m pytest -v`
- Dashboard: `cd dashboard && npx tsc --noEmit && npx next build`
- Commit per finding-group; never batch across components.

---

## Phase 1 — safe deletes (~1100 lines)
Verified zero-caller (or zero-importer). One commit per component.

1. **leader-mcp dead files** (~795 lines). Delete `migrate_registry.py` (228), `leader_crew.py` (243), `database.py` (125), `registry_service.py` (129). Delete `import_harness_registry` + `_get_crewai_tools` from `leader_tools.py` (~90) — only callers were the dead `leader_crew.py`. Selfchecks don't import these (verified). **Verify:** `selfcheck_gateway.py` + `selfcheck_workflow.py`.
2. **cron-mcp dead bits** (~34 lines). Delete `tasks.py` (shadowed by `tasks/` pkg, 23), `main.py` (6), `register_task()` in `registry.py:18-22` (5). KEEP `tasks/__init__.py` + DB-task tools. **Verify:** server imports clean.
3. **composite-mcp** — fix `seed_example.py` hardcoded `/Users/chengsishi/...` paths → repo-relative via `Path(__file__).resolve().parents[N]`. **Verify:** `selfcheck.py`.
4. **dashboard dead files** (~65 lines). Delete `src/lib/seed.ts` (37, no importer) + `src/lib/sql.js.d.ts` (28, redundant with `@types/sql.js`). **Verify:** `tsc --noEmit && next build`.
5. **process tools** (~2 lines). Now in `mcp/daas-mcp/` (relocated from process-mcp). Delete unused `inspect` import in `process_database.py:17`, unused `_IDENT_RE` in `process_tools.py:26`. **Verify:** `selfcheck_process.py`.
6. **akshare harness** (~5 lines). Delete `get_registry()` in `cli_anything/akshare/core/registry.py:98-102`. **Verify:** `pytest -v`.
7. **daas harness** (~38 lines). Delete speculative try/except in `sources/cnstats_source.py:197-201` (returns a callable on error, never used); collapse `core/exceptions.py` 3-class hierarchy → single `DAASError` (CLI only catches generic; `ParameterError` never raised). **Verify:** `pytest -v`.
8. **root artifacts**. Delete `:memory:` (548KB, colon-name = `sqlite::memory:` misconfig artifact), `aapl_2026-06.csv`, `t.md`, empty `scripts/`. Add `:memory:` to `.gitignore`.

## Phase 2 — mechanical shrinks (~700 lines, local)
No call-site redesign. One commit per component.

9. **daas-mcp `server.py`** (~60 lines). Replace the 31-line import block + 31 `app.tool()` calls with a single loop `for fn in (tool_a, tool_b, ...): app.tool(fn)`. **Verify:** `selfcheck.py`.
10. **daas-mcp `collection_writer.py`** (~20 lines). 7-branch if/elif command dispatch → `{"create": svc.create, ...}[cmd](args)` dict. **Verify:** `selfcheck_collection_writer.py`.
11. **daas-mcp `server.py` CLI** (~30 lines). 4 `--X` branches → `_parse_id_arg(flag) -> Optional[int]` helper.
12. **leader-mcp `workflow_database.py`** (~6 lines). `_validate_ident` regex → `str.isidentifier()`.
13. **scrapling-uv `server.py`** (~12 lines). `_summary()` hand-rolled docstring extraction → `inspect.getdoc()`.
14. **dashboard ECharts** (~22 lines). Inline `EChartsWrapper` (4-line wrapper) into callers; merge `echarts-block.tsx` to use `ReactECharts` directly. **Verify:** tsc + build.
15. **dashboard `<ErrorBanner/>`** (~25 lines). Extract shared component for 6 near-identical error banners across collections + chat components.
16. **dashboard `lib/chat-utils.ts`** (~40 lines). Extract shared `streamText`/`getMCPTools`/`MissingApiKeyError`/`isRawConfig` from `api/chat/route.ts` + `api/collections/[name]/chat/route.ts`.
17. **dashboard `api/settings/route.ts`** (~20 lines). Hand-rolled prepare/bind/step upsert → `db.run` with `INSERT OR REPLACE`; dedupe `syncToEnv` with `settings/page.tsx`.
18. **daas harness `cli.py`** (~8 lines). Dedupe the k=v parse loop in `call_cmd` + `_cmd_call_repl`.
19. **worldbank** (~40 lines). `KEY_INDICATORS` defined twice (source `discover()` + `populate_daas.build_worldbank_functions()`) → build once from the tuple.
20. **gov-scraw** (~15 lines). `SCRIPT_NAMES` list in 3 places → define once in `__init__.py`.
21. **daas harness `proxy.py`** (~11 lines). Delete unused `__enter__`/`__exit__` context manager (CLI calls `apply()` directly).

## Phase 3 — local refactors with call-site changes (~1300 lines)
Gated by selfcheck + harness pytest after each item.

22. **daas_tools.py + entity_tools.py** (~100 lines). `@_svc_call` decorator replacing 29 `try: return _ok(svc.method()) except: return _err(e)` wrappers; drop `_ok()` identity. **Verify:** `selfcheck.py` + `selfcheck_collection_writer.py` + `selfcheck_pipeline.py`.
23. **daas-mcp `seed_external_mcps.py`** (~80 lines). 6 `goc_*` get-or-create fns → one `_goc(model, filter_kwargs, create_kwargs, counts, dry_run)`.
24. **daas-mcp `seed_external_mcps.py` + `entity_sync.py`** (~40 lines). Unify duplicated `Counts` class → shared module or plain dict.
25. **daas-mcp `registry_service.py`** (~30 lines). 3 parallel tree-walks (`_ancestor_ids`/`_descendant_ids`/`_category_path`) → shared `_walk_ancestors`/`_walk_descendants` generators.
26. **leader-mcp database layer** (~155 lines). Shared `init_sqlite_engine(url)` for `init_db()` in Leader/Gateway/Workflow databases (~75); shared `_singleton_db` helper for triple `_db`/`get_*_db`/`reset_*_db` boilerplate (~50); shared `_resolve_database_url` (dup in gateway+workflow, ~30). **Verify:** both selfchecks.
27. **leader-mcp `gateway_tools.py`** (~65 lines). `_ensure_jsonable` + `_extract_result_data` (pandas/pydantic branches for plain-dict results) → `json.dumps(result, default=str)`.
28. **leader-mcp router dedup** (~60 lines). `_KW_*` tuples + `_ask_direct`/`_direct_fetch` duplicated between `data_crew.py` + `specialist_agents.py` → shared module.
29. **leader-mcp single-caller helpers** (~44 lines). Inline `get_workflow_steps` (0 callers), `list_step_results` (0 callers), `get_step_result` (1 caller), `set_enabled` (selfcheck only → fold into `upsert_upstream`); inline trivial `seed_upstreams.py`/`seed_specialist_agents.py` helpers.
30. **process tools** (~16 lines). Now in `mcp/daas-mcp/process_database.py` (relocated from process-mcp). Merge `get_rule`/`get_rule_row` + `get_indicator`/`get_indicator_row` (dict-vs-ORM of same query).
31. **trading-mcp** (~90 lines). Drop `_register_in_registry()` + `TRADING_TOOLS` + `_startup_msg` (import-time side effect writing rows nobody reads; `@app.tool` is source of truth). **Verify carefully:** server starts, tools still exposed.
32. **trading-mcp agents** (~91 lines). 17 one-line factory wrappers across 5 files → `AGENTS` dict + `create_agent(name, llm)`. Delete `agents/__init__.py` re-exports (zero callers). Reduce `test_personas.py` (207 lines) to ~5 integration checks.
33. **trading-mcp schemas** (~30 lines). Flatten `TraderProposal`/`PortfolioDecision` unused structured fields (always HOLD/default) → string fields.
34. **composite-mcp** (~33 lines). Drop `_validate_steps()` speculative `if`/`branch`/`switch`/`loop` guards (features don't exist); inline `build_client()` (3-line wrapper, 2 callers). **Verify:** `selfcheck.py`.
35. **cron-mcp** (~50 lines). Inline `pause_schedule`/`resume_schedule`/`run_now` tool bodies; drop the `scheduler.py` `pause_job`/`resume_job`/`execute_task` wrapper layer.
36. **daas-mcp `pipeline_tools.py`** (~23 lines). Drop redundant `_validate_source_mcp` (re-resolved in `fetch_to_store`); factor `_load_item(item_id)` helper for 3 CLI entrypoints.
37. **daas-mcp `daas_database.py`** (~8 lines). Flatten triple singleton (`_instance` + `get_instance` + `get_database`) → module-level cached var.

## Out of scope (per decisions + reclassification)
- Phase 4a (vendored scrapling scripts) — KEEP.
- Phase 4b (harness mirror → shared cli_anything.core) — SKIP.
- cron-mcp DB-task CRUD tools + `tasks/__init__.py` placeholders — KEEP (exposed MCP surface).
- `message-bubble.tsx` regex → react-markdown — SKIP (adds a dep).
- composite-mcp `seed_example.py` deletion — FIX paths instead (item 3).

## Execution order
Phase 1 → verify all gates → Phase 2 → verify → Phase 3 → verify. Within each phase, item order is flexible; I'll batch by component (one commit per component per phase) to keep diffs reviewable. I'll stop and report if any selfcheck/test regresses.
