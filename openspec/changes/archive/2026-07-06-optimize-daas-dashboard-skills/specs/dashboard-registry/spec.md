## ADDED Requirements

### Requirement: Dashboard metadata persisted in the shared database

The system SHALL store standalone-dashboard metadata in a `dashboards` table in `mcp/daas.db`, defined in the shared schema package `mcp/models/` and created via `Base.metadata.create_all` (additive — no Alembic, no migration of existing tables). The table SHALL hold, per dashboard: a unique `slug` (kebab-case, matches `^[A-Za-z0-9_-]+$`), a human-readable `name`, an `intro` (Text description), `source_tables` (JSON list of `scraw_*` / `observations` tables backing the charts), `entity_coverage` (JSON — the entities/codes the dashboard covers, or null for unscoped), `time_range` (JSON — `{start, end}` of the data shown, or null), `refresh_cadence` (String — static snapshot vs cron name), `chart_config` (JSON — the ECharts spec(s) or a description of the charts), `file_path` (relative path to the HTML), `file_url` (the `file://` URL), and `created_at` / `updated_at` timestamps. The DB table is the single source of truth for dashboard metadata.

#### Scenario: Table auto-created on first connect

- **WHEN** `dashboard-mcp` (or any consumer importing `mcp/models`) starts against `mcp/daas.db` for the first time after this change
- **THEN** the `dashboards` table exists with all the columns above, created by `Base.metadata.create_all` without a manual migration step

#### Scenario: Slug is unique

- **WHEN** `register_dashboard` is called with a `slug` that already exists in the `dashboards` table
- **THEN** the call upserts (updates the existing row) instead of inserting a duplicate, and `list_dashboards` returns exactly one row for that slug

### Requirement: dashboard-mcp exposes CRUD tools over the dashboards table

`dashboard-mcp` SHALL expose six tools backed by the `dashboards` table: `register_dashboard` (upsert by slug), `list_dashboards` (return every row's name + slug + intro + file_url), `get_dashboard` (return one row by slug, including source_tables / entity_coverage / time_range / refresh_cadence / chart_config), `search_dashboards` (keyword match against name + intro + source_tables, return matching name + slug + intro), `update_dashboard` (patch fields by slug), and `delete_dashboard` (remove a row by slug). All six tools SHALL resolve a relative `sqlite:///` `DAAS_DATABASE_URL` against the repo root so they read/write the canonical `mcp/daas.db`, not dashboard-mcp's stale local copy.

#### Scenario: Register then get

- **WHEN** `register_dashboard` is called with `{slug, name, intro, source_tables, file_path, file_url, ...}` and then `get_dashboard` is called with that `slug`
- **THEN** `get_dashboard` returns the exact name, intro, source_tables, file_path, and file_url that were registered

#### Scenario: Search by keyword matches name, intro, or source

- **WHEN** `search_dashboards` is called with a keyword that appears in a dashboard's `name`, `intro`, or one of its `source_tables`
- **THEN** the matching dashboard's name + slug + intro are returned, and dashboards with no match are excluded

#### Scenario: Delete removes the row

- **WHEN** `delete_dashboard` is called with an existing `slug`
- **THEN** the row is removed from `dashboards` and a subsequent `get_dashboard` for that slug returns not-found

#### Scenario: Relative DAAS_DATABASE_URL resolves to the repo-root DB

- **WHEN** `DAAS_DATABASE_URL` is the relative `sqlite:///mcp/daas.db` (the shipped default)
- **THEN** the six tools read/write `<repo-root>/mcp/daas.db`, not `mcp/dashboard-mcp/daas.db`

### Requirement: Charts index and markdown list regenerated from the database

On every `register_dashboard`, `update_dashboard`, and `delete_dashboard` call, `dashboard-mcp` SHALL regenerate `dashboard/my-charts-dashboard/index.html` (an HTML page linking to every `<slug>.html` by its human-readable `name`) and `dashboard/my-charts-dashboard/daas.md` (a markdown table of all dashboards) from the current `dashboards` table rows. The regeneration SHALL be idempotent — the two files are fully derived from the DB, never hand-appended, so re-registering an existing dashboard does not produce duplicate entries.

#### Scenario: Register then index lists it

- **WHEN** a new dashboard is registered via `register_dashboard`
- **THEN** `dashboard/my-charts-dashboard/index.html` contains exactly one link to its `<slug>.html` labeled with its `name`, and `daas.md` contains exactly one row for it

#### Scenario: Delete then index no longer lists it

- **WHEN** a dashboard is deleted via `delete_dashboard`
- **THEN** both `index.html` and `daas.md` no longer contain any reference to that dashboard's slug, with no leftover entries

#### Scenario: Re-register does not duplicate

- **WHEN** `register_dashboard` is called twice with the same `slug` (an update)
- **THEN** `index.html` and `daas.md` each contain exactly one entry for that slug after the second call
