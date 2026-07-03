## ADDED Requirements

### Requirement: Mutating writes resolve to the same database as reads, independent of process cwd

The dashboard's mutating routes (`/api/collections/*`) SHALL spawn `collection_writer.py` such that the writer connects to the **same** `mcp/daas.db` file the dashboard's sql.js read path uses, regardless of the directory from which the Next.js dev or build server was launched. The dashboard SHALL derive the repo root by walking upward from `process.cwd()` until it finds a directory containing both `mcp/daas-mcp/collection_writer.py` and `dashboard/package.json`, and SHALL resolve both `DAAS_MCP_DIR` (the writer's launch directory) and the sql.js read DB path from that repo root — not from `process.cwd()` alone. If no ancestor directory satisfies both markers, the dashboard SHALL fail with a clear error rather than silently resolving to a wrong database path.

#### Scenario: Launched from the dashboard directory

- **WHEN** the Next.js server is launched from `dashboard/` (the conventional launch directory) and a user creates a collection
- **THEN** the spawned writer writes a row to `mcp/daas.db` and the subsequent sql.js read of `datasource_collections` returns that row

#### Scenario: Launched from the repository root

- **WHEN** the Next.js server is launched from the repository root (a directory containing both `dashboard/` and `mcp/`) and a user creates a collection
- **THEN** the spawned writer writes to the same `mcp/daas.db` and the subsequent sql.js read returns that row (no "unable to open database file" error, no path divergence)

#### Scenario: Launched from a directory with no repo-root ancestor

- **WHEN** the Next.js server is launched from a directory whose ancestor chain contains no directory with both `mcp/daas-mcp/collection_writer.py` and `dashboard/package.json`
- **THEN** the mutating route returns an error indicating the repo root could not be located, rather than silently writing to or reading from a wrong database path

### Requirement: The writer loads environment files in repo-root-first order

The `collection_writer.py` sidecar SHALL load the repository-root `.env` (the directory containing `mcp/` and `dashboard/`) before its own per-MCP `.env` (loaded with `override=True`), matching the documented "single `.env`" convention so a standalone run of the writer (or of `daas-mcp`'s `server.py`, which shares this load order and is spawned by the MCP host without the dashboard's env) honors a `DAAS_DATABASE_URL` configured in the repo-root `.env`. The repo-root load SHALL use `override=False` (the `dotenv` default), so when the dashboard spawns the writer and `DAAS_DATABASE_URL` is already present in the inherited process env, the inherited value takes precedence and the writer stays in sync with the dashboard. The writer SHALL still resolve any relative `DAAS_DATABASE_URL` against the repo root (its cwd is `mcp/daas-mcp/` under `uv run --directory`), and SHALL fall back to an absolute default `mcp/daas.db` when `DAAS_DATABASE_URL` is unset.

#### Scenario: Standalone writer run uses the repo-root .env

- **WHEN** `collection_writer.py` is run without `DAAS_DATABASE_URL` in the inherited process env and the repo-root `.env` defines `DAAS_DATABASE_URL=sqlite:///mcp/custom.db`
- **THEN** the writer connects to `mcp/custom.db` (resolved against the repo root) and the create succeeds there

#### Scenario: Inherited env var takes precedence over the repo-root .env

- **WHEN** the dashboard spawns the writer and `DAAS_DATABASE_URL` is present in the inherited process env (loaded by Next.js from `dashboard/.env.local`)
- **THEN** the writer uses the inherited value and does NOT override it with the repo-root `.env`'s value (load order is repo-root first with `override=False`, per-MCP last with `override=True`)

#### Scenario: Unset DAAS_DATABASE_URL falls back to the absolute default

- **WHEN** `DAAS_DATABASE_URL` is not present in the inherited process env, not in the repo-root `.env`, and not in the per-MCP `.env`
- **THEN** the writer connects to the absolute default `mcp/daas.db` (resolved via the writer's own file location) and the create succeeds

#### Scenario: Per-MCP .env override still wins

- **WHEN** the repo-root `.env` sets `DAAS_DATABASE_URL=sqlite:///mcp/daas.db` and `mcp/daas-mcp/.env` sets `DAAS_DATABASE_URL=sqlite:///:memory:` with override enabled
- **THEN** the writer uses `:memory:` (the per-MCP override wins) — confirming the load order is repo-root first, per-MCP last with override
