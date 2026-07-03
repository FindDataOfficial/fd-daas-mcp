## Why

Clicking "New collection" in the dashboard (`/collections` or `/collections/manage`) previously failed with an error. The root cause was environmental: the dashboard's mutating routes spawn `mcp/daas-mcp/collection_writer.py` via `uv run --directory mcp/daas-mcp`, which sets the writer's cwd to `mcp/daas-mcp/`. A **relative** `DAAS_DATABASE_URL` (the shipped `sqlite:///mcp/daas.db`) was resolved against that cwd, so the writer opened the wrong path and raised `sqlite3.OperationalError: unable to open database file`. Reads (sql.js, file-anchored) kept working, so the failure surfaced only on writes — exactly when the user clicked "create".

A partial fix was applied today (`daas_database._resolve_url` + an absolute default; `db.ts.resolveDaasDbPath`), and the create flow now works in a fresh dev server. But the fix is **uncommitted** and rests on fragile assumptions that can silently regress:

1. `collection_writer.py` (and `server.py`) load `mcp/.env` (nonexistent) instead of the repo-root `.env` where `DAAS_DATABASE_URL` is actually defined — they only work because of the absolute-default fallback. A customized `DAAS_DATABASE_URL` in the root `.env` is ignored, breaking the documented "single `.env`" convention.
2. The dashboard's `DAAS_MCP_DIR` (`py-cli.ts`) and `REPO_ROOT` (`db.ts`) are derived from `process.cwd()`, so they are correct only when the dev server is started from `dashboard/`. Started from elsewhere (e.g. the repo root, or an editor that doesn't set cwd), both reads and writes resolve to the wrong paths and the error recurs.

This change hardens the write path so the create error cannot recur, and commits the existing fix.

## What Changes

- Anchor `dashboard/src/lib/py-cli.ts`'s `DAAS_MCP_DIR` to the file's own location (`__dirname`-equivalent) instead of `process.cwd()`, so the writer is found regardless of where the dashboard is launched.
- Anchor `dashboard/src/lib/db.ts`'s `REPO_ROOT` to the file's own location instead of `process.cwd()`, so sql.js reads resolve to the same `mcp/daas.db` regardless of launch directory.
- Fix `mcp/daas-mcp/collection_writer.py` env loading to load the **repo-root** `.env` first (then `mcp/daas-mcp/.env` with `override=True`), matching the documented convention so a customized `DAAS_DATABASE_URL` is honored. Apply the same one-line correction to `mcp/daas-mcp/server.py`.
- Add a regression self-check that exercises the create → list round-trip through the writer + the read path, asserting both resolve the same `mcp/daas.db`.
- Commit the existing (currently uncommitted) `_resolve_url` / `resolveDaasDbPath` fix as part of this change.

## Capabilities

### New Capabilities

(None — this hardens existing behavior; no new capability is introduced.)

### Modified Capabilities

- `collection-dashboard-ui`: strengthen the "Read directly, write through API routes" contract — the spawned writer SHALL connect to the same `mcp/daas.db` the dashboard reads, independent of the dashboard process's cwd and independent of `DAAS_DATABASE_URL` being present in the inherited env. The writer SHALL load the repo-root `.env` so a customized `DAAS_DATABASE_URL` there is honored.

## Impact

- **Code**: `dashboard/src/lib/py-cli.ts`, `dashboard/src/lib/db.ts`, `mcp/daas-mcp/collection_writer.py`, `mcp/daas-mcp/server.py` (env-loading line only), plus a new self-check script and/or test.
- **APIs**: no API shape changes. `/api/collections` POST and `/api/collections/[name]` PATCH/DELETE keep their current contracts; only the underlying writer invocation becomes cwd-independent.
- **Dependencies**: none added.
- **Risk**: low. Path resolution becomes more robust; the shipped `DAAS_DATABASE_URL=sqlite:///mcp/daas.db` and the unset-env default both continue to resolve to `/…/mcp/daas.db`. Existing read/write behavior is preserved.
- **Verification**: live reproduction already confirmed (POST `/api/collections` → 200, page render → 200, list → 200). The new self-check will guard against regression.
