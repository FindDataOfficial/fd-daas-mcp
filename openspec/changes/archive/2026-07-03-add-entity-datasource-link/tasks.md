## 1. Schema (shared models)

- [x] 1.1 Add `Entity` model to `mcp/models/models.py` — table `entities`, columns: `id`, `entity_type` (index), `code`, `name`, `ticker` (nullable, index), `exchange` (nullable), `country_code` (nullable, index), `isin` (nullable), `aliases` (JSON), `status` (default `active`), `metadata_` (JSON), `created_at`, `updated_at`; `UNIQUE(entity_type, code)`; `to_dict()`.
- [x] 1.2 Add `EntityDatasourceLink` model to `mcp/models/models.py` — table `entity_datasource_links`, columns: `id`, `entity_id` (FK `entities.id` CASCADE, index), `source_id` (FK `sources.id` CASCADE, index), `identifier_in_source` (nullable), `coverage` (default `full`), `metadata_` (JSON), `last_fetched_at` (nullable), `created_at`; `UNIQUE(entity_id, source_id)`; relationships to `Entity` and `DaasSource`; `to_dict()`.
- [x] 1.3 Bump the table-count comment at the top of `mcp/models/models.py` and add an `# entity domain` section header. Verify `pip install -e mcp/models` still installs.
- [x] 1.4 Confirm `Base.metadata.create_all` creates both new tables on a temp DB (no Alembic); verify `PRAGMA foreign_keys=ON` behavior with the cascade.

## 2. Entity tools (daas-mcp)

- [x] 2.1 Create `mcp/daas-mcp/entity_tools.py` with a shared `_get_session()` helper (mirror `daas_tools.py`'s `RegistryService` usage).
- [x] 2.2 Implement `search_entities(query, entity_type=None, limit=20)` — case-insensitive substring on `name`, `ticker`, `code`, and `aliases` JSON; returns `{entities, count}`.
- [x] 2.3 Implement `get_entity(entity_id)` — full detail incl. aliases/metadata; `{"success": false, "error": ...}` when missing.
- [x] 2.4 Implement `list_entities(entity_type=None, exchange=None, country_code=None, limit=100, offset=0)` — filtered + paginated, with total count.
- [x] 2.5 Implement `get_entity_coverage(entity_id)` — for each link: `source` name, `identifier_in_source`, sections (form_type, section_name, instruction with `<ask-agent>` substituted by `identifier_in_source`), `column_count` + `columns` from `daas_function_columns` joined to `daas_functions` for that `source_id`; when `column_count == 0`, parse the section instruction and return `column_hint` = `{mcp, tool}`.
- [x] 2.6 Implement `link_entity_datasource(entity_id, source_name, identifier_in_source, coverage="full", metadata=None)` — resolve `source_name` → `sources.id`, upsert link; error if source unknown.
- [x] 2.7 Implement `unlink_entity_datasource(entity_id, source_name)` — delete link; error if not linked.
- [x] 2.8 Register all six tools in `mcp/daas-mcp/server.py` (import + `app.tool(...)`).
- [x] 2.9 Run `uv run --directory mcp/daas-mcp python selfcheck.py` and extend it with entity-tool smoke cases (search/list/coverage on a temp DB) so the existing selfcheck still passes.

## 3. Sync script (daas-mcp)

- [x] 3.1 Create `mcp/daas-mcp/entity_sync.py` — argparse with `--sync-all`, `--sync-stocks`, `--sync-countries`, `--register-cron`, `--dry-run`, `--db-url`; load root `.env` + per-MCP `.env` (mirror `seed_external_mcps.py`).
- [x] 3.2 Implement country seed — hard-coded `COUNTRIES` list (~30 markets: ISO alpha-2 + name); upsert as `entity_type='country'`.
- [x] 3.3 Implement stock sync — lazily `import akshare`; call `stock_info_a_code_name` (A-shares), `stock_hk_spot_em` (HK), `stock_us_spot_em` (US), plus TW/SG markets akshare covers; map each market's columns to `entities` fields; upsert on `(entity_type='stock', code)`; per-market try/except isolation.
- [x] 3.4 Implement delisting detection — for each synced market, set `status='delisted'` on entity codes absent from the current list (do not delete rows).
- [x] 3.5 Implement auto-link derivation — rule table mapping market/country → list of `(source_name, identifier_in_source)`; upsert `entity_datasource_links`; skip pairs the user manually added that aren't in the rules (never delete).
- [x] 3.6 Implement `--dry-run` — print planned upsert/link counts per market/country, write nothing.
- [x] 3.7 Implement the missing-akshare guard — print a clear dependency error and exit non-zero if `akshare` is not installed when `--sync-stocks`/`--sync-all` is used.

## 4. Cron registration

- [x] 4.1 Implement `--register-cron` in `entity_sync.py` — insert cron-mcp `Task` (name `entity-sync-stocks`, command `uv run --directory mcp/daas-mcp python entity_sync.py --sync-stocks`) and `Schedule` (name `entity-sync-weekly`, cron `17 3 * * 1`, timezone from env or `UTC`) using `models.Task`/`Schedule`; idempotent on the `name` unique key (no duplicates, no overwrite).
- [x] 4.2 Print a reminder that the schedule takes effect on the next cron-mcp start.
- [x] 4.3 Verify the registered task command runs standalone (`uv run --directory mcp/daas-mcp python entity_sync.py --sync-stocks --dry-run`).

## 5. Verification & docs

- [x] 5.1 Run the full sync against `daas.db`: `uv run --directory mcp/daas-mcp python entity_sync.py --sync-all`; confirm entity + link counts in the summary.
- [x] 5.2 Exercise the example query end-to-end: `search_entities("茅台")` → `get_entity` → `get_entity_coverage`; confirm the coverage result shows `cnreport` + `akshare` + `yfinance` with substituted routing instructions and column hints.
- [x] 5.3 Repeat for a US stock (`AAPL`) and a HK stock (`00700`); confirm `edgar`+`yfinance` and `hkex`+`akshare`+`yfinance` coverage respectively.
- [x] 5.4 `uv run --directory mcp/daas-mcp python entity_sync.py --register-cron`; confirm one `entity-sync-stocks` task + one `entity-sync-weekly` schedule; re-run to confirm idempotency.
- [x] 5.5 Update `CLAUDE.md` `mcp/daas-mcp/` section: document the 6 new entity tools, the `entity_sync.py` script + its flags, and the cron wiring.
- [x] 5.6 Update `construction/daas-storage.md` with the `entities` + `entity_datasource_links` tables and the entity→source→columns coverage flow.
- [x] 5.7 Run `openspec validate add-entity-datasource-link --strict` and fix any reported issues.
