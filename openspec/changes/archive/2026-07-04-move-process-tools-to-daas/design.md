## Context

`process-mcp` and `daas-mcp` are already tightly coupled:

- Both read/write the same `mcp/daas.db` via `DAAS_DATABASE_URL`, resolved against the repo root by an identical `_resolve_url()` helper.
- Both import ORM classes from the shared `mcp/models` package (`Base.metadata.create_all` runs in both — idempotent because the tables are the same).
- Both set `PRAGMA foreign_keys=ON` per-connection and validate dynamic identifiers against `^[A-Za-z_][A-Za-z0-9_]*$` before interpolating them into SQL `text()`.
- Both expose cron-driven CLI branches that run a path in-process and exit (`process-mcp --run-rule`/`--run-indicator` vs `daas-mcp --fetch-item`/`--register-cron`/`--unregister-cron`/`--sync-cron`), invoked by `cron-mcp` via `uv run --directory mcp/<mcp> python server.py …`.
- `daas-mcp` already mirrors `process-mcp`'s patterns in comments (`# Mirror process-mcp's --run-rule pattern.` at `server.py:140`; `# Mirrors process-mcp/process_database.py` at `daas_database.py:26`).

`process-mcp` owns 19 tools (11 LLM extraction + 8 indicators) and 3 tables (`process_rules`, `process_results`, `indicator_rules`). The LLM path is currently under a "daas-traceability exemption": it is forbidden from touching daas registry tables, while the indicator path is explicitly exempted so it can write `observations`. Once both live inside `daas-mcp`, that exemption is meaningless — `observations` writes become native, and the LLM path's soft reference to `sources.name` is just another internal read.

The dashboard at `dashboard/` calls `process-mcp` by name in 12 places (6 API routes + `server-data.ts`) and already calls `daas-mcp` for chat (it is the configured `MCP_SERVER`). Both MCPs are stdio subprocesses spawned by the dashboard's `mcp-client`.

## Goals / Non-Goals

**Goals:**
- Relocate all 19 process-mcp tools, the `--run-rule`/`--run-indicator` CLI branches, and the supporting DB code into `mcp/daas-mcp/` with no behavioral change to tool signatures or result shapes.
- Delete `mcp/process-mcp/` and its `.mcp.json` entry.
- Repoint every dashboard caller from `'process-mcp'` to `'daas-mcp'` with no UI/route-path change.
- Migrate existing `cron-mcp` task rows whose `command` references `mcp/process-mcp` so scheduled jobs keep firing.
- Preserve all existing data (`process_rules`, `process_results`, `indicator_rules`, `observations` rows) with zero schema change.
- Keep the moved selfcheck offline (no network, no LLM key required for the indicator path).

**Non-Goals:**
- Renaming the owned tables (`process_rules`/`process_results`/`indicator_rules`). They keep their names as legacy labels.
- Renaming `PROCESS_MODELS` to `DAAS_MODELS`. Existing `.env` files keep working.
- Consolidating the two DB singletons (`daas_database.Database` and the moved `ProcessDatabase`) onto one SQLAlchemy engine. Both creating engines on the same SQLite file is supported; engine consolidation is a future cleanup.
- Renaming the dashboard `/process/rules` and `/process/indicators` route paths. Only the proxied MCP server name changes.
- Changing any tool signature, return shape, or `observations` upsert key.
- Moving cnreport-mcp's `ai_extract` (a separate, cnreport-specific tool that reuses the same LLM-call pattern).

## Decisions

### Decision 1: Delete `process-mcp` entirely; do not leave a shim

**Chosen**: Remove the directory, the `.mcp.json` entry, and the two specs' requirements outright.

**Rationale**: A shim would mean keeping a second stdio process alive purely to forward tool calls, doubling connection overhead and creating a stale-name landmine. The user asked to move *all* tools; nothing remains to host. Deleting is the clean cut.

**Alternative considered**: Keep `process-mcp/server.py` as a thin re-export that imports daas-mcp's tools. Rejected — it preserves a name clients should be migrating off, and FastMCP tool registration does not cleanly re-export across processes.

### Decision 2: Move `process_database.py`, `process_tools.py`, `indicator_tools.py` verbatim; keep `ProcessDatabase` as a sibling singleton

**Chosen**: Copy the three modules into `mcp/daas-mcp/` with their internal logic intact. `ProcessDatabase` keeps its own `get_db()` singleton and its own engine on `DAAS_DATABASE_URL`. The 19 tool functions keep calling `get_db()` (process) and the daas tools keep calling `get_database()` (daas). Both call `Base.metadata.create_all` on the shared file — idempotent.

**Rationale**: Smallest diff, lowest regression risk. The two singletons already coexist on the same SQLite file in tests; production just adds the case where they live in one process. Two engines on one SQLite WAL-mode file is well-supported.

**Alternative considered**: Fold `ProcessDatabase`'s methods into `daas_database.Database`. Rejected for this change — it is a large refactor (rule CRUD, indicator CRUD, `run_indicator`, `observations` upsert, source-table discovery, injection guard) that risks breaking the selfcheck's invariants. Tracked as a future cleanup.

### Decision 3: Convert the moved tools to daas-mcp's `app.tool(fn)` registration style

**Chosen**: daas-mcp registers tools by importing plain functions and calling `app.tool(fn)` in `server.py` (no `@app.tool` decorators). Strip the `@app.tool` decorators from the moved functions and register them alongside the existing 37 in `server.py`'s registration block.

**Rationale**: Consistency with the host MCP. The decorator style would also work, but mixing styles inside one `server.py` is confusing. Stripping decorators is mechanical and keeps the functions importable for tests.

### Decision 4: Keep table names and `PROCESS_MODELS` env var unchanged

**Chosen**: `process_rules`, `process_results`, `indicator_rules` keep their names. `PROCESS_MODELS` keeps its name.

**Rationale**: Renaming tables is a data migration with rollback risk for zero functional gain. Renaming the env var breaks every deployed `.env`. The names are now legacy labels, which is acceptable; the spec and docs note the ownership change.

**Alternative considered**: Rename to `daas_extract_rules` / `daas_extract_results` / `daas_indicator_rules` and `DAAS_MODELS`. Rejected — breaking data and config for cosmetics.

### Decision 5: Add `--run-rule` and `--run-indicator` to daas-mcp's existing `sys.argv` parser

**Chosen**: Extend the `if __name__ == "__main__":` block in `mcp/daas-mcp/server.py` to recognize `--run-rule <name>` and `--run-indicator <name>` before `app.run(...)`. Each calls the same implementation function the MCP tool uses, prints a JSON summary, and exits 0/1 — exactly the pattern `--fetch-item` already follows.

**Rationale**: One process, one arg parser, one cron invocation shape. `cron-mcp` task commands change only in the `--directory` path (`mcp/process-mcp` → `mcp/daas-mcp`); the flag and argument shape are identical.

### Decision 6: Cron task migration via a one-shot idempotent script

**Chosen**: Ship `mcp/daas-mcp/migrate_process_cron.py` that rewrites `tasks.command` rows containing `mcp/process-mcp` to `mcp/daas-mcp` (preserving the rest of the command and the `--run-rule`/`--run-indicator` flag). Idempotent on re-run; `--dry-run` plans; `--revert` restores the original `process-mcp` path for rollback.

**Rationale**: `cron-mcp` stores shell commands as data; without rewriting, scheduled `--run-rule`/`--run-indicator` jobs would spawn a server.py that no longer exists. A guarded, reversible script is safer than a blind `UPDATE`.

**Alternative considered**: Document the manual `sqlite3` `UPDATE`. Rejected — error-prone and irreversible.

### Decision 7: Selfcheck moves as `selfcheck_process.py`, scope unchanged

**Chosen**: Copy `mcp/process-mcp/selfcheck.py` to `mcp/daas-mcp/selfcheck_process.py`. Keep its temp-DB, monkeypatched-LLM, indicator-round-trip scope. Do not merge into the existing daas selfcheck.

**Rationale**: The existing daas selfchecks cover collections/pipeline/registry — different surface. Keeping a dedicated process selfcheck preserves the injection-guard and `run_rule` incremental-cursor invariants without entangling them with daas concerns.

### Decision 8: Specs — two new capabilities, two emptied old specs

**Chosen**: Create `specs/daas-llm-extraction/spec.md` and `specs/daas-indicators/spec.md` containing the relocated requirements (attributed to `daas-mcp`, with the "daas-traceability exemption" language dropped). Empty `process-mcp-server` and `process-mcp-indicators` via REMOVED-requirement deltas. Update `process-dashboard-ui` (server-name delta) and `leader-mcp-data-gateway` (list-membership delta).

**Rationale**: Each daas-mcp capability is its own spec (existing pattern: `datasource-management`, `pipeline-collections`, …). Relocating requirements into new specs under that naming is consistent. Emptying the old specs (rather than deleting the directories) keeps the openspec history navigable.

## Risks / Trade-offs

- **Silent cron breakage** — scheduled `--run-rule`/`--run-indicator` jobs spawn a missing server.py until migrated. → Mitigation: ship `migrate_process_cron.py`; run it before deleting `mcp/process-mcp/`; `--dry-run` lists every affected row.
- **Dashboard caller assumes `process-mcp` result shapes** — but the moved code is byte-identical, so shapes are unchanged. → Mitigation: the moved `selfcheck_process.py` asserts the shapes; dashboard smoke after repoint.
- **daas-mcp install footprint grows** — gains `httpx`, `jsonschema`, `pypdf` (LLM path only). → Mitigation: acceptable; these are already project deps via cnreport-mcp; no new transitive risk.
- **Two engines on one SQLite file** — slight connection-pool overhead, no correctness issue. → Mitigation: noted as future cleanup (consolidate onto daas `Database.engine`); not blocking.
- **Forgetting a `callTool('process-mcp', …)`** — a missed dashboard caller fails at runtime, not build time. → Mitigation: `grep -rn "process-mcp" dashboard/src` is an explicit task; the migration script's `--dry-run` also surfaces stray references if cron rows are the canary.
- **`PROCESS_MODELS` name confusion** — the env var still says "PROCESS" but the MCP is daas. → Mitigation: docs note the legacy name; rename is a non-goal.
- **Rollback** — the change is code-only (no schema migration); `git revert` restores the directory and `.mcp.json`. The only persistent side-effect is the cron task-row rewrite. → Mitigation: `migrate_process_cron.py --revert` restores original commands; run it before `git revert`.

## Migration Plan

1. **Move code** — copy `process_tools.py`, `indicator_tools.py`, `process_database.py`, `selfcheck.py` into `mcp/daas-mcp/` (selfcheck → `selfcheck_process.py`); strip `@app.tool` decorators; register 19 tools in `server.py`; add `--run-rule`/`--run-indicator` branches; merge deps into `pyproject.toml`.
2. **Verify in isolation** — run `uv run --directory mcp/daas-mcp python selfcheck_process.py` (offline, temp DB). Run the existing daas selfchecks to confirm no regression.
3. **Migrate cron task rows** — `uv run --directory mcp/daas-mcp python migrate_process_cron.py --dry-run`, then run for real. Confirm 0 rows still reference `mcp/process-mcp`.
4. **Repoint dashboard** — update the 12 `callTool('process-mcp', …)` calls, 2 UI strings, and comments. Run `grep -rn "process-mcp" dashboard/src` and resolve every hit.
5. **Remove process-mcp** — delete `mcp/process-mcp/`; remove the `.mcp.json` entry.
6. **Update docs & specs** — CLAUDE.md section rewrite; `construction/daas-storage.md` §6 + `construction/mcp.md`; `mcp/models/` comments; leader-mcp "mirrors" comments; write the 4 spec deltas.
7. **Smoke** — restart daas-mcp; load `/process/rules` and `/process/indicators` in the dashboard; create + run a rule and an indicator; confirm `observations` rows land.

**Rollback**: `migrate_process_cron.py --revert`, then `git revert` the change commit. No DB schema to undo.

## Open Questions

- Consolidate `ProcessDatabase` onto the daas `Database` engine now or later? — **Recommend later** (non-goal; risks the selfcheck invariants).
- Rename `PROCESS_MODELS` → `DAAS_MODELS`? — **Recommend no** (breaks `.env`).
- Rename dashboard `/process/*` routes to `/daas-process/*`? — **Recommend no** (out of scope; breaks bookmarks).
