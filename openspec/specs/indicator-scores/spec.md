# indicator-scores Specification

## Purpose
TBD - created by archiving change add-indicator-scores. Update Purpose after archive.
## Requirements
### Requirement: Indicator default score column

The system SHALL add a nullable `score` column (REAL / Float) to the `indicator_rules` table. A NULL value means "inherit the datasource's default `sources.score`". The column SHALL default to NULL on existing rows (additive, guarded `ALTER TABLE` migration `_migrate_indicator_rules_score` in `daas_database.py`, mirroring `_migrate_sources_score`; no Alembic, no data loss). `IndicatorRule.to_dict()` SHALL include the `score` field.

#### Scenario: Existing indicator rules get a NULL score after migration

- **WHEN** the `indicator_rules` table is migrated on an existing `daas.db`
- **THEN** a `score` REAL column exists on `indicator_rules` and every pre-existing rule has `score = NULL`

#### Scenario: Create an indicator with a score

- **WHEN** `create_indicator(name="rsi_5", datasource="akshare", score=0.8, ...)` is called
- **THEN** the new `indicator_rules` row has `score = 0.8` and the returned dict includes `"score": 0.8`

#### Scenario: Create an indicator without a score

- **WHEN** `create_indicator(name="sma_20", datasource="akshare", ...)` is called with no `score`
- **THEN** the new row has `score = NULL` and the returned dict includes `"score": null`

### Requirement: Indicator score on create and update

`create_indicator` SHALL accept an optional `score` (float). `update_indicator` SHALL accept an optional `score` (float) and a `clear_score` (bool, default false) flag — `clear_score=True` SHALL clear the indicator's score to NULL (inherit the datasource default), mirroring `update_datasource(clear_score=True)`. (JSON cannot distinguish "omitted" from "null", so a dedicated flag is the clearing channel.) `get_indicator` and `list_indicators` SHALL return both the raw `score` and an `effective_default_score` resolved as `COALESCE(indicator_rules.score, sources.score)` via a LEFT JOIN on `sources.name = indicator_rules.datasource` (NULL when the join misses or both are NULL).

#### Scenario: update_indicator sets a score

- **WHEN** `update_indicator(name="rsi_5", score=0.9)` is called
- **THEN** the rule's `score` becomes `0.9` and `get_indicator("rsi_5")` returns `"score": 0.9`

#### Scenario: update_indicator clears a score

- **WHEN** `update_indicator(name="rsi_5", clear_score=True)` is called
- **THEN** the rule's `score` becomes NULL and `get_indicator("rsi_5")` returns `"score": null`

#### Scenario: effective_default_score inherits the datasource default

- **WHEN** an indicator rule has `score = NULL` and its datasource `sources.score = 0.6`
- **THEN** `list_indicators` returns that rule with `"score": null` and `"effective_default_score": 0.6`

#### Scenario: effective_default_score is NULL when both are NULL

- **WHEN** an indicator rule has `score = NULL` and its datasource `sources.score = NULL`
- **THEN** `list_indicators` returns `"score": null` and `"effective_default_score": null`

### Requirement: Set indicator score tool

The system SHALL expose a `set_indicator_score(name, score)` tool that sets the indicator's default `score` when `score` is a float, and clears it (sets to NULL → inherits the datasource default) when `score` is `null`. The tool SHALL return the updated indicator dict (including `effective_default_score`). The tool SHALL reject unknown indicator names with `{"error": "indicator not found"}` and SHALL reject non-numeric, non-null `score` values with `{"error": "score must be a number or null"}`.

#### Scenario: Set an indicator default score

- **WHEN** `set_indicator_score(name="rsi_5", score=0.8)` is called
- **THEN** the `indicator_rules.score` for rsi_5 is set to `0.8` and the returned dict includes `"score": 0.8`

#### Scenario: Clear an indicator default score

- **WHEN** `set_indicator_score(name="rsi_5", score=null)` is called
- **THEN** the `indicator_rules.score` for rsi_5 is set to NULL and the returned dict includes `"score": null`

#### Scenario: Unknown indicator

- **WHEN** `set_indicator_score(name="nope", score=0.5)` is called and the indicator does not exist
- **THEN** the tool returns `{"error": "indicator not found"}` and no row is changed

### Requirement: Indicator score migration is idempotent and offline-safe

The `_migrate_indicator_rules_score` migration SHALL check `PRAGMA table_info(indicator_rules)` for a `score` column before altering, SHALL be safe to run on every daas-mcp start, and SHALL be a no-op when the column already exists. The migration SHALL NOT run while other writers hold the table (it is run at server start with the standard daas-mcp connect listener).

#### Scenario: Migration is a no-op when the column exists

- **WHEN** daas-mcp starts against a `daas.db` whose `indicator_rules` already has a `score` column
- **THEN** no `ALTER TABLE` is issued and existing scores are preserved

