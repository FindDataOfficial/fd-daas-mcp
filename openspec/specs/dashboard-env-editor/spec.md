# dashboard-env-editor Specification

## Purpose
TBD - created by archiving change add-rules-indicators-env-dashboard. Update Purpose after archive.
## Requirements
### Requirement: Settings page writes through to .env files

The `/settings` page SHALL write every managed env key through to the real `.env` file(s) on save: global-scope keys (bootstrap + runtime categories) to the repo-root `.env`, and per-MCP-scope keys to `mcp/<mcp>/.env` (created on first write, holding only the override `KEY=value` lines). The `PUT /api/settings` route SHALL extend its existing `syncToEnv` line-patch (replace the line if the key exists, else append) from `bootstrap`-only to all categories, SHALL write per-MCP keys to the corresponding `mcp/<mcp>/.env`, and SHALL remove the matching `KEY=...` line from the relevant `.env` file when a `settings` row is deleted. The sync SHALL preserve unmanaged lines (comments, blanks, and keys not present in the `settings` table) in both root and per-MCP `.env` files. Every `.env` write SHALL return `restartRequired: true`.

#### Scenario: Runtime key written to root .env

- **WHEN** the user sets `LLM_API_KEY` (a runtime key) via the `/settings` form
- **THEN** the `PUT /api/settings` route writes `LLM_API_KEY=<value>` into the repo-root `.env` (replacing an existing line or appending)
- **AND** the response includes `restartRequired: true`

#### Scenario: Per-MCP override written to mcp .env

- **WHEN** the user sets an `HTTP_PROXY` override scoped to `akshare-mcp`
- **THEN** the route writes `HTTP_PROXY=<value>` into `mcp/akshare-mcp/.env` (creating the file on first write)
- **AND** the repo-root `.env` is unchanged for that key

#### Scenario: Delete removes the .env line

- **WHEN** the user deletes a `settings` row for a key that was synced to `.env`
- **THEN** the matching `KEY=...` line is removed from the relevant `.env` file
- **AND** unmanaged lines (comments, other keys) are preserved

#### Scenario: Comments and unmanaged keys preserved

- **WHEN** the root `.env` contains comments and a hand-edited key not in the `settings` table, and the user saves a runtime key via `/settings`
- **THEN** the sync updates only the managed key's line and leaves the comments and the unmanaged key intact

### Requirement: Raw .env editor on the settings page

The `/settings` page SHALL include a raw `.env` editor section that renders the live contents of the repo-root `.env` in a textarea. A `GET /api/settings/env` route SHALL return the root `.env` file text; a `PUT /api/settings/env` route SHALL replace the root `.env` file contents wholesale from the request body. The section SHALL provide a "Save" action (PUT) and a "Reset from disk" action (re-read via GET). The section SHALL display a banner warning that saving overwrites dashboard-managed lines and that the structured settings table re-syncs managed lines on its next save. The raw editor SHALL cover only the root `.env` (per-MCP `.env` files are edited via the structured per-MCP table).

#### Scenario: View raw .env contents

- **WHEN** the user opens the raw `.env` editor section on `/settings`
- **THEN** the textarea shows the current contents of the repo-root `.env`

#### Scenario: Save raw .env

- **WHEN** the user edits the textarea and clicks "Save"
- **THEN** the dashboard PUTs the full text to `/api/settings/env`, the root `.env` is replaced wholesale, and a `restartRequired` banner is shown

#### Scenario: Reset from disk

- **WHEN** the user clicks "Reset from disk"
- **THEN** the textarea is repopulated from the current root `.env` contents, discarding unsaved edits

#### Scenario: Raw save warning banner

- **WHEN** the raw editor renders
- **THEN** a banner warns that saving overwrites dashboard-managed lines and that the structured table re-syncs on its next save

### Requirement: Restart-required hint on .env writes

Every `PUT /api/settings` or `PUT /api/settings/env` that modifies a `.env` file SHALL return `restartRequired: true`, and the settings form SHALL surface a "Restart MCPs for changes to take effect" message when that flag is set. This reflects that MCPs load `.env` only at startup (root first, then `mcp/<mcp>/.env` with `override=True`).

#### Scenario: Restart hint shown after a runtime key save

- **WHEN** the user saves a runtime key and the route returns `restartRequired: true`
- **THEN** the settings form shows a "Restart MCPs for changes to take effect" message and keeps the modal open so the user sees the warning

#### Scenario: No hint when nothing touches .env

- **WHEN** a future settings write does not modify any `.env` file (no such write exists in v1, but the contract holds)
- **THEN** the route returns `restartRequired: false` and no hint is shown

