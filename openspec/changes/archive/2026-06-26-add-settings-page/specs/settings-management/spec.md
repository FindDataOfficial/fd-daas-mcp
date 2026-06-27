# Settings Management

Centralized configuration management for all MCP environment variables, accessible through a dashboard UI and consumed by MCP servers at runtime.

## Overview

Configuration variables are stored in a `settings` table in `daas.db`. The dashboard provides a `/settings` page to view and edit all variables. MCP servers load runtime variables from the DB on each tool invocation via a shared `settings_helper.py` module. Bootstrap variables are synced back to `.env` files and require a service restart.

## User Stories

### US1: View All Settings (P1)

As a developer, I want to see all configuration variables in one page, grouped by category (bootstrap vs runtime) and scope (global vs per-MCP), so I understand the current system configuration at a glance.

**Acceptance**:
- Settings page accessible at `/settings`
- Variables grouped into sections: Bootstrap (restart required) and Runtime (immediate effect)
- Each variable shows: key, current value, scope badge (global / per-MCP name), description
- Runtime variables show a green "Live" indicator
- Bootstrap variables show an amber "Restart Required" indicator

### US2: Edit Runtime Settings (P1)

As a developer, I want to edit proxy and API URL settings and have them take effect immediately for subsequent MCP tool calls, without restarting any service.

**Acceptance**:
- Click edit on any runtime variable → inline edit form or modal
- Save → written to `settings` table immediately
- Next MCP tool call reads updated value (via `settings_helper.py`)
- Change visible in the page immediately after save
- Supported runtime keys: `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, `CKAN_URL`

### US3: Edit Bootstrap Settings (P2)

As a developer, I want to edit database URL settings through the dashboard and get clear guidance on which services need restarting.

**Acceptance**:
- Click edit on any bootstrap variable → inline edit form
- Save → written to `settings` table AND synced to root `.env` file
- Warning toast/banner: "Restart required: [list of affected MCPs + dashboard]"
- Bootstrap keys: `DAAS_DATABASE_URL`, `DASHBOARD_PORT`

### US4: Per-MCP Proxy Override (P2)

As a developer, I want each MCP to have its own proxy configuration, falling back to the global default when not explicitly set.

**Acceptance**:
- Per-MCP section lists all known MCP servers
- Each MCP shows: current `HTTP_PROXY` value (global inherited OR per-MCP override)
- Edit button opens a form scoped to that MCP
- Save with scope=`<mcp-name>` → creates/updates a row in `settings` table
- Clear override → deletes the per-MCP row, MCP falls back to `global` scope
- Overridden values show a "Custom" badge; inherited values show "(inherited from global)"

### US5: Initial Seed from .env (P2)

As a first-time user, I want the settings table to be automatically populated from my existing `.env` files so I don't lose my current configuration.

**Acceptance**:
- First time the `/settings` page loads with an empty `settings` table, values are seeded from root `.env` and per-MCP `.env` files
- `DAAS_DATABASE_URL` → scope=`global`, category=`bootstrap`
- `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` from root `.env` → scope=`global`, category=`runtime`
- `CKAN_PORTAL_URL` → scope=`global`, key=`CKAN_URL`, category=`runtime`
- Per-MCP `.env` variables become per-MCP scope rows
- Seed happens exactly once (table has rows → skip)

## Non-Functional Requirements

- **Performance**: Settings page loads within 500ms; MCP runtime settings lookup under 5ms (in-process cache)
- **Consistency**: Bootstrap variable edits must succeed in BOTH `settings` table AND `.env` file, or fail atomically (roll back DB if file write fails)
- **Concurrency**: No concurrent write conflicts expected (single-user dashboard); if they occur, last-write-wins

## Out of Scope (v1)

- Adding new MCPs through the settings UI
- Environment variable encryption for sensitive values
- Multi-user auth/audit logging for settings changes
- Import/export of settings profiles
- Validation of proxy URL format (free-text input)
