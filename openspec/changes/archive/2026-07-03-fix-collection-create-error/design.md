## Context

The dashboard's collection mutating routes (`/api/collections/*`) do not write to `mcp/daas.db` directly. They spawn `mcp/daas-mcp/collection_writer.py` as a one-shot subprocess via `uv run --directory mcp/daas-mcp python collection_writer.py <cmd> --json '{...}'` (see `dashboard/src/lib/py-cli.ts`). The writer uses SQLAlchemy against `DAAS_DATABASE_URL` (or an absolute default). Reads, by contrast, go through sql.js (WASM) in the Next.js process (`dashboard/src/lib/db.ts`), file-anchored to `mcp/daas.db`.

This split is the source of the bug. `uv run --directory` sets the writer's cwd to `mcp/daas-mcp/`, so a **relative** `DAAS_DATABASE_URL` (`sqlite:///mcp/daas.db`) resolved against the wrong directory and the writer opened a non-existent path → `sqlite3.OperationalError: unable to open database file`. Reads kept working (sql.js anchored to the file), so the failure appeared only on writes — i.e. when the user clicked "New collection".

A partial fix is on disk (uncommitted): `daas_database._resolve_url` anchors relative sqlite paths to the repo root, `_default_url()` returns an absolute default, and `db.ts.resolveDaasDbPath` mirrors that. The create flow now works in a fresh dev server. Two fragilities remain:

1. **Wrong `.env` loaded.** `collection_writer.py` and `server.py` compute `ROOT = Path(__file__).resolve().parent.parent` (= `mcp/`) and `load_dotenv(ROOT / '.env')`. But `mcp/.env` does not exist; the canonical `DAAS_DATABASE_URL` lives in the **repo-root** `.env` (`cli-anything/.env`). The writer only works because the absolute default saves it. A user who customizes `DAAS_DATABASE_URL` in the root `.env` is silently ignored — breaking the "single `.env`" convention in `construction/mcp.md`.
2. **`process.cwd()` dependency.** `py-cli.ts`'s `DAAS_MCP_DIR` and `db.ts`'s `REPO_ROOT` are both `path.resolve(process.cwd(), '..')` / `path.resolve(process.cwd(), '..', 'mcp', 'daas-mcp')`. Correct only when the dashboard is launched from `dashboard/`. Next.js's own startup warning ("We detected multiple lockfiles… selected /Users/chengsishi/package-lock.json as the root directory") shows cwd-based root detection is already fragile in this setup. Launched from elsewhere, reads and writes resolve to different wrong paths and the original error recurs.

## Goals / Non-Goals

**Goals:**
- The writer subprocess and the sql.js read path SHALL resolve to the **same** `mcp/daas.db` regardless of the directory from which the dashboard dev/build server is launched.
- The writer SHALL honor a customized `DAAS_DATABASE_URL` from the repo-root `.env` (the documented single source of truth).
- A regression check SHALL exist that fails if the writer and the read path ever diverge.

**Non-Goals:**
- Not changing the `/api/collections/*` HTTP contracts or the `collection_writer.py` CLI arg shape.
- Not replacing the spawn-per-write sidecar model with a long-lived process or an HTTP MCP call (latency is acceptable; writes are infrequent).
- Not migrating reads off sql.js, and not introducing a new MCP server.
- Not changing the `create_collection` / `update_collection` tool semantics (those are owned by `datasource-collections` and are unchanged).

## Decisions

### Decision 1: Resolve the repo root by walking up from `process.cwd()`, not by `process.cwd()` alone

The dashboard's Next.js server code is bundled into `.next/server/`, so `__dirname` points at a chunk directory and cannot be used to locate the source tree / `mcp/`. Instead, add a `findRepoRoot()` helper (in `db.ts`, re-exported) that walks up from `process.cwd()` until it finds a directory containing **both** `mcp/daas-mcp/collection_writer.py` and `dashboard/package.json`. That directory is the repo root. Derive `REPO_ROOT` and `DAAS_MCP_DIR` from it.

- **Why over `process.cwd() + '..'`**: self-correcting when the server is launched from `dashboard/`, the repo root, or a subdirectory. Matches the actual project layout rather than assuming a launch dir.
- **Why over `__dirname`**: `__dirname` is unreliable in bundled Next.js server code.
- **Why over an env var**: zero-config; the layout itself is the anchor.
- **Failure mode**: if no ancestor matches, throw a clear error ("could not locate repo root containing mcp/daas-mcp and dashboard/"). Better to fail loudly than to silently write to the wrong DB.

### Decision 2: Resolve the writer's `.env` from the repo root via `__file__`

Python is not bundled, so `__file__` is reliable. In `collection_writer.py`, change `ROOT = Path(__file__).resolve().parent.parent` (= `mcp/`) to `REPO_ROOT = Path(__file__).resolve().parents[2]` (= `cli-anything/`), and `load_dotenv(REPO_ROOT / '.env')` first, then `load_dotenv(Path(__file__).parent / '.env', override=True)`. Apply the identical one-line correction to `server.py`.

- **Why**: the repo-root `.env` is where `DAAS_DATABASE_URL` is defined; loading it makes a **standalone** run of the writer (or `server.py`, which the MCP host spawns without the dashboard's env) honor a customized URL instead of silently falling back to the default.
- **Why `parents[2]`**: `collection_writer.py` is at `mcp/daas-mcp/collection_writer.py`; `parents[0]=mcp/daas-mcp`, `parents[1]=mcp/`, `parents[2]=cli-anything/`. Same index for `server.py` (same directory).
- **Precedence note**: the repo-root load uses `override=False` (the `dotenv` default). When the **dashboard** spawns the writer, `DAAS_DATABASE_URL` is already in the inherited process env (Next.js loaded it from `dashboard/.env.local`), so the inherited value wins and the repo-root `.env` does not override it — keeping writer and dashboard on the same DB. The repo-root `.env` load is therefore primarily for `server.py` (spawned by the MCP host, no dashboard env) and for standalone/debugging writer runs. Per-MCP `.env` (`override=True`) still wins over both.
- **Alternative considered**: keep relying on the absolute default. Rejected — it silently ignores the user's `.env`, which is exactly the kind of silent divergence that caused the original bug.

### Decision 3: Keep `_resolve_url` + absolute default as defense-in-depth

Even with the `.env` fix, the writer's cwd is `mcp/daas-mcp/` (set by `uv run --directory`), so a relative `DAAS_DATABASE_URL` must still be anchored to the repo root before SQLAlchemy opens it. Keep `_resolve_url` (anchoring relative sqlite paths to `_REPO_ROOT`) and the absolute `_default_url()` as they are. They are the second layer of defense; the `.env` fix is the first.

### Decision 4: Regression self-check that asserts writer + reader hit the same file

Add `mcp/daas-mcp/selfcheck_collection_writer.py` (mirrors the existing `selfcheck_pipeline.py` / `selfcheck.py` pattern): with a temp DB, run the writer `create` subcommand, then read `datasource_collections` via SQLAlchemy, asserting the row exists; and separately assert that `findRepoRoot()` (TS) and `REPO_ROOT` (Python) resolve to the same absolute path when run from a non-`dashboard/` cwd. Keep it offline (temp DB, no akshare, no network).

- **Why**: the bug was silent (reads green, writes red). A round-trip check that exercises both paths is the only guard against silent divergence.
- **Why a Python self-check**: the writer is Python and the existing self-checks live alongside it; it can also assert the `.env`-load path.

## Risks / Trade-offs

- **`findRepoRoot()` walks the filesystem on every cold start.** → Cheap (a handful of `existsSync` calls up a short chain) and only on cold start / module load. Cache the result in a module-level constant after first resolution.
- **A directory layout change (relocating `dashboard/` or `mcp/`) would break the marker check.** → Acceptable; the layout is stable and documented in `CLAUDE.md`. The marker check fails loudly, not silently.
- **Loading the repo-root `.env` in the writer could change behavior for someone relying on `mcp/daas-mcp/.env` shadowing.** → `mcp/daas-mcp/.env` is still loaded with `override=True` after the root, so per-MCP overrides still win. The shipped file only has a commented-out `:memory:` line, so no behavior change for the shipped config.
- **`process.cwd()` is still the walk start.** → If the server is launched from a directory entirely outside the repo (no ancestor contains the markers), `findRepoRoot()` throws. This is an improvement over the current behavior (silently wrong path) and surfaces immediately.

## Migration Plan

No data migration, no config change. Steps:

1. Apply the code changes (Decision 1–2). The shipped `.env` (`DAAS_DATABASE_URL=sqlite:///mcp/daas.db`) and the unset-env default both continue to resolve to `/…/mcp/daas.db`, so behavior is preserved.
2. Run the new self-check (Decision 4) plus a live manual create-through-the-dashboard smoke.
3. Rollback, if ever needed: revert `py-cli.ts`/`db.ts` path-resolution lines and the writer/server `.env` lines. No schema or data impact.

## Open Questions

- None blocking. (If the user wants to additionally commit the existing uncommitted `_resolve_url` fix as a separate prior commit vs. bundling it into this change, that's a packaging choice — this proposal bundles it since the hardening and the fix are the same concern.)
