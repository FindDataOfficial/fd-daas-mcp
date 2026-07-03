## ADDED Requirements

### Requirement: Entity sync script populates stocks and countries
The system SHALL provide an `entity_sync.py` script under `mcp/daas-mcp/` that upserts stock entities (A-shares, HK, US, and other markets akshare covers) by calling akshare's market-list functions, and upserts a curated set of country entities from a hard-coded list. The script SHALL be idempotent (re-runnable on the live `daas.db`) and SHALL upsert on `(entity_type, code)`.

#### Scenario: Sync all
- **WHEN** `uv run --directory mcp/daas-mcp python entity_sync.py --sync-all` is run
- **THEN** the script upserts stock entities for each akshare market and upserts the curated country list, and prints a summary of inserted/updated counts per type

#### Scenario: Sync stocks only
- **WHEN** `--sync-stocks` is passed
- **THEN** only stock entities are upserted (countries untouched)

#### Scenario: Sync countries only
- **WHEN** `--sync-countries` is passed
- **THEN** only the curated country entities are upserted (stocks untouched)

#### Scenario: Per-market failure isolation
- **WHEN** one akshare market-list call raises an exception
- **THEN** the script logs the error for that market and continues with the remaining markets

#### Scenario: Missing akshare dependency
- **WHEN** `--sync-stocks` is run and `akshare` is not installed
- **THEN** the script prints a clear error naming the missing dependency and exits non-zero, without touching the database

### Requirement: Sync auto-derives datasource links
The system SHALL, after upserting an entity, derive `entity_datasource_links` rows from the entity's market/country using a deterministic rule table (US stock → edgar + yfinance; A-share → cnreport + akshare + yfinance; HK stock → hkex + akshare + yfinance; Japan stock → edinet; country → worldbank, plus cnstats for CN), storing the per-source identifier the datasource's lookup tool accepts. Existing manual links SHALL be preserved (auto-derivation upserts only the rule-defined pairs).

#### Scenario: US stock auto-link
- **WHEN** the sync upserts Apple (US stock, ticker AAPL)
- **THEN** `entity_datasource_links` rows are created for `edgar` (identifier `AAPL`) and `yfinance` (identifier `AAPL`)

#### Scenario: A-share auto-link
- **WHEN** the sync upserts 600519 (A-share)
- **THEN** link rows are created for `cnreport` (identifier `600519`), `akshare` (identifier `600519`), and `yfinance` (identifier `600519.SH` or `.SS` form per the rule)

#### Scenario: Manual link preserved
- **WHEN** a user has manually linked an entity to a source not in the rule table, and the sync re-runs
- **THEN** the manual link row is not deleted by the sync

### Requirement: Sync marks delisted stocks
The system SHALL set `status='delisted'` (without deleting the row) for stock entities whose code was present in a prior sync but is absent from the current akshare list for that market, so link history is preserved.

#### Scenario: Delisting detected
- **WHEN** a stock code present in `entities` is missing from the current akshare A-share list
- **THEN** the entity's `status` is set to `delisted` and the row is retained

### Requirement: Cron auto-registration
The system SHALL support an `--register-cron` flag on `entity_sync.py` that idempotently registers a cron-mcp `Task` (name `entity-sync-stocks`, command `uv run --directory mcp/daas-mcp python entity_sync.py --sync-stocks`) and a `Schedule` (name `entity-sync-weekly`, weekly cron expression, timezone from env) by inserting into the shared `tasks`/`schedules` tables, deduplicating on the task/schedule name. The flag SHALL print a note that the schedule takes effect on the next cron-mcp start.

#### Scenario: Register cron
- **WHEN** `entity_sync.py --register-cron` is run for the first time
- **THEN** a `tasks` row named `entity-sync-stocks` and a `schedules` row named `entity-sync-weekly` are created, and the script prints a reminder to restart cron-mcp

#### Scenario: Idempotent re-registration
- **WHEN** `entity_sync.py --register-cron` is run again
- **THEN** no duplicate rows are created (existing task/schedule are left unchanged) and the script reports the schedule already exists

### Requirement: Dry-run support
The system SHALL support a `--dry-run` flag on `entity_sync.py` that prints the planned upserts and link derivations without writing to the database.

#### Scenario: Dry-run
- **WHEN** `entity_sync.py --sync-all --dry-run` is run
- **THEN** the script prints the planned entity and link counts per market/country and writes nothing to `daas.db`
