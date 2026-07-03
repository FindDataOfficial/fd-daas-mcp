## 1. Dashboard path resolution (cwd-independent)

- [x] 1.1 In `dashboard/src/lib/db.ts`, add a `findRepoRoot()` helper that walks up from `process.cwd()` until it finds a directory containing both `mcp/daas-mcp/collection_writer.py` and `dashboard/package.json`; throws a clear error if none found. Cache the result in a module-level constant.
- [x] 1.2 Replace `REPO_ROOT = path.resolve(process.cwd(), '..')` with `findRepoRoot()`; keep `resolveDaasDbPath()` and `DAAS_DB_PATH` deriving from it.
- [x] 1.3 In `dashboard/src/lib/py-cli.ts`, replace `DAAS_MCP_DIR = path.resolve(process.cwd(), '..', 'mcp', 'daas-mcp')` with a value derived from the shared `findRepoRoot()` (import from `db.ts` or a small shared module) joined with `mcp/daas-mcp`.
- [x] 1.4 Verify no other call site recomputes the repo root / `DAAS_MCP_DIR` from `process.cwd()` (search `dashboard/src`); update any stragglers to reuse the helper.

## 2. Writer + server .env loading (repo-root first)

- [x] 2.1 In `mcp/daas-mcp/collection_writer.py`, change `ROOT = Path(__file__).resolve().parent.parent` to `REPO_ROOT = Path(__file__).resolve().parents[2]` and `load_dotenv(ROOT / ".env")` to `load_dotenv(REPO_ROOT / ".env")` (repo-root `.env` first, per-MCP `.env` with `override=True` unchanged).
- [x] 2.2 Apply the identical correction to `mcp/daas-mcp/server.py` (`ROOT` → `REPO_ROOT = parents[2]`).
- [x] 2.3 Confirm `daas_database._resolve_url` and `_default_url()` are unchanged (they are the defense-in-depth layer) and still anchor relative paths to `_REPO_ROOT`.

## 3. Regression self-check

- [x] 3.1 Add `mcp/daas-mcp/selfcheck_collection_writer.py` mirroring the existing `selfcheck_pipeline.py` pattern: temp DB, no network.
- [x] 3.2 In the self-check, run the writer `create` subcommand against a temp DB (set `DAAS_DATABASE_URL` to a temp path), then read `datasource_collections` via SQLAlchemy and assert the created row exists.
- [x] 3.3 In the self-check, assert `Path(__file__).resolve().parents[2]` (writer REPO_ROOT) equals the directory containing `mcp/` and `dashboard/` (sanity-check the `__file__` anchor).
- [x] 3.4 Add a TS-side assertion (in the self-check or a small `dashboard` test) that `findRepoRoot()` returns the same absolute path as the Python `parents[2]` anchor, when run from a non-`dashboard/` cwd (e.g. repo root).
- [x] 3.5 Document the run command in the change README / `CLAUDE.md` daas-mcp section: `uv run --directory mcp/daas-mcp python selfcheck_collection_writer.py`.

## 4. Verification

- [x] 4.1 Run `uv run --directory mcp/daas-mcp python selfcheck_collection_writer.py` — passes.
- [x] 4.2 Start the dashboard from `dashboard/` (`npm run dev`), create a collection via the UI at `/collections/manage`, confirm it appears in the list and the workspace opens at `/collections/<name>`.
- [x] 4.3 Confirm the path-resolution logic is cwd-independent: the self-check's node `check-repo-root.mjs` (run from the repo root, a non-`dashboard/` cwd) returns the same repo root as the Python `parents[2]` anchor — already asserted in self-check test 5. (Next.js itself requires launching from `dashboard/`, so the live server cannot be started from the repo root; the walk-up logic is what's verified.)
- [x] 4.4 Temporarily set `DAAS_DATABASE_URL=sqlite:///mcp/__custom.db` in the repo-root `.env`, run the writer **standalone** with no inherited env (`env -u DAAS_DATABASE_URL uv run --directory mcp/daas-mcp python collection_writer.py create --json '{"name":"__customprobe__"}'`), confirm it writes to `mcp/__custom.db` (proving the writer honors the repo-root `.env` on a standalone run, since the inherited env no longer shadows it); then revert the `.env` and remove `mcp/__custom.db`. (Note: when the dashboard spawns the writer, the inherited env var from `dashboard/.env.local` takes precedence — this standalone run is what exercises the repo-root `.env` load.)
- [x] 4.5 Run `openspec archive` checklist: proposal/design/specs/tasks all `done`; no stray `process.cwd()` repo-root derivations remain in `dashboard/src`.

## 5. Commit

- [ ] 5.1 Stage the modified `daas_database.py`, `db.ts`, `py-cli.ts`, `collection_writer.py`, `server.py`, the new self-check, and the openspec change artifacts.
- [ ] 5.2 Commit with a message describing the hardening (the existing uncommitted `_resolve_url` fix is bundled into this change).

> **Deferred (2026-07-03):** the hardening is left in the working tree uncommitted, per user decision. The fix depends on the broader uncommitted daas-mcp/dashboard-collections feature (`registry_service.create_collection`, the `datasource_collections` table, `collection_writer.py`, `db.ts.resolveDaasDbPath`, `_resolve_url` — none in HEAD), so it can't be isolated into a self-consistent commit on its own branch. When the broader feature is committed, this hardening goes with it. The openspec change artifacts (`proposal.md` / `design.md` / `specs/` / `tasks.md`) document the change in the meantime.
