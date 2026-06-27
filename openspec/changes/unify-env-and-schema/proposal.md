# Proposal: Unify Env and Schema

**Change**: `unify-env-and-schema` | **Status**: proposed | **Date**: 2025-06-26

## Problem

Six `.db` files, five different env var names, three separate SQLAlchemy `Base` instances, and duplicated `CREATE TABLE` statements between Python and TypeScript. Changing a column means updating it in 2-3 places.

## Solution

1. **Single env file** — root `.env` holds all shared config (`DAAS_DATABASE_URL`, proxy, CKAN portal). Each MCP's `.env` only contains overrides.
2. **Single schema package** — `mcp/models/` as an installable `pyproject.toml` package with the one `declarative_base()`. All MCPs depend on it.
3. **Dashboard reads schema from MCP models** — no more `CREATE TABLE` in TypeScript.
4. **Cleanup** — 4 zombie databases deleted, 2 orphan `models.py` files deleted.

## Impact

| What | Action |
|------|--------|
| `mcp/leader_mcp.db` | Delete |
| `mcp/daas_registry.db` | Delete |
| `mcp/cron.db` | Delete |
| `mcp/custom_path.db` | Delete |
| `mcp/dashboard.db` | Migrate tables to `daas.db`, then delete |
| `mcp/cron-mcp/models.py` | Delete (moved to `mcp/models`) |
| `mcp/daas-mcp/models.py` | Delete (moved to `mcp/models`) |
| `mcp/models/` | **New** — installable package |
| `mcp/leader-mcp/unified_models.py` | Retain but re-export from `mcp.models` |
| Root `.env` | Expand with all shared config |
| Per-MCP `.env` | Simplify to override-only |
| `.mcp.json` `env` blocks | Remove (servers read `.env` directly) |
| `dashboard/src/lib/db.ts` | Remove `CREATE TABLE`; use `DAAS_DATABASE_URL` |
| `dashboard/src/lib/schema.ts` | Add comment: mirror of `mcp/models/models.py` |
