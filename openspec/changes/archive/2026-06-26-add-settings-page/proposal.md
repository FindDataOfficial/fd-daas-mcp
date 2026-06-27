## Why

Environment configuration (database path, proxy, API URLs) is scattered across `.env` files and requires manual editing plus service restarts to take effect. A centralized settings page in the dashboard lets users manage all configuration in one place, with runtime variables taking effect immediately and bootstrap variables providing clear restart guidance.

## What Changes

- New `settings` table in `daas.db` (via `mcp/models/models.py`) — key/value store with `scope` field for per-MCP overrides
- New `/settings` dashboard page — manage all env variables in one UI
- New `mcp/settings_helper.py` — shared module MCPs use to load runtime settings from DB on each tool invocation
- Modified `mcp/ckan-mcp/server.py` — calls `load_runtime_settings()` before making HTTP requests (the only MCP that does direct HTTP calls today)
- Bootstrap variables (`DAAS_DATABASE_URL`, etc.) synced back to `.env` files on save, with a clear "restart required" warning
- Runtime variables (`HTTP_PROXY`, `HTTPS_PROXY`, `CKAN_URL`) take effect immediately — no restart needed
- Per-MCP proxy: each MCP can override `HTTP_PROXY`/`HTTPS_PROXY`; falls back to `global` scope default
- Initial seed: existing `.env` values auto-populate the `settings` table on first access

## Capabilities

### New Capabilities

- `settings-management`: Centralized configuration management for all MCP environment variables, with runtime vs bootstrap classification, per-MCP scope overrides, and automatic .env sync for bootstrap vars.

### Modified Capabilities

<!-- None — existing capabilities are implementation-only, no spec-level requirement changes -->

## Impact

- **New files**: `mcp/settings_helper.py`, `dashboard/src/app/settings/page.tsx`, `dashboard/src/app/api/settings/route.ts`
- **Modified files**: `mcp/models/models.py` (add `Setting` table), `mcp/ckan-mcp/server.py` (load runtime settings), `dashboard/src/components/nav.tsx` (add Settings link), root `.env` (comments updated)
- **No breaking changes**: Existing `.env` loading still works; settings table is additive
- **No new dependencies**: uses existing `sql.js` (dashboard) and `sqlalchemy` (MCP)
