# Collections & Indicators

DAAS separates **what data you have** (raw fetched series) from **what you
compute** (indicators) and **how you group them** (collections). All of it lives
in `daas.db`.

## The data flow

```
datasource -> Python lib -> scraw_<slug>  (raw fetched rows)
                              |
                              v
              indicator_rules -> observations  (computed series)
                                      |
                                      v
                          collections (entity / indicator groups)
```

## Raw data: `scraw_<slug>`

Every fetch persists rows to an auto-created `scraw_<slug>` table
(`scripts/upsert.py` - auto `CREATE` + `ALTER` + `INSERT OR REPLACE`, backs up
`daas.db` first). Examples in the live DB: `scraw_spy_daily`, `scraw_aapl_daily`,
`scraw_massive_treasury_yields`.

```bash
sqlite3 daas.db "SELECT name FROM sqlite_master WHERE name LIKE 'scraw_%' LIMIT 10;"
```

## Indicator rules: `indicator_rules`

An indicator rule binds a source table + column + math op + params to an
indicator name. Columns: `name`, `datasource`, `source_table`, `date_column`,
`value_column`, `op`, `params_json`, `indicator_name`, `enabled`, `score`.

```bash
sqlite3 daas.db "SELECT name, op, source_table, indicator_name FROM indicator_rules WHERE name LIKE 'SPY_%' LIMIT 5;"
```

Create one with `daas_create_indicator(...)` or the `fd-daas-indicators-creator`
skill. Compute it into `observations` with `daas_run_indicator(name=...)` or
`scripts/run_indicator.py <name>`.

## Computed series: `observations`

Keyed on `(source, function_name, indicator, date)`; `value` is `VARCHAR(64)`.
This is the table every dashboard and collection reads from.

```bash
sqlite3 daas.db "SELECT indicator, date, value FROM observations WHERE indicator='SPY_ma5' ORDER BY date DESC LIMIT 5;"
```

## Entity collections

A named group of entities (a watchlist / portfolio) with **audit-tracked
membership**. Tables: `entity_collections`, `entity_collection_items`,
`entity_collection_changes`.

```bash
sqlite3 daas.db "SELECT name FROM entity_collections;"
sqlite3 daas.db "SELECT entity_id, action, source FROM entity_collection_changes LIMIT 5;"
```

- Manual: `daas_add_entity_to_collection` / `daas_remove_entity_from_collection`
  (records `add_in` / `remove_out` events, `source='manual'`).
- Rule-based: attach a `rule_id` (json/script/position/llm) and re-derive with
  `daas_sync_entity_collection` (`source='cron'`).

## Indicator collections

A named, reusable bundle of indicators. Tables: `indicator_collections`,
`indicator_collection_items`, `indicator_collection_changes`. Same audit pattern
as entity collections.

```bash
sqlite3 daas.db "SELECT name FROM indicator_collections;"
```

Add with `daas_add_indicator_to_collection`; sync rule-based ones with
`daas_sync_indicator_collection`.

## Scores

Collection items carry an effective **score** (priority/quality weight) that
inherits from the indicator/datasource default and can be overridden
per-collection (`daas_set_indicator_collection_item_score`). Scores feed ranking
when multiple sources/indicators cover the same thing.

## Rules: `rules`

The unified rule store (`rule_type` ∈ `json`/`script`/`position`/`llm`;
`target` ∈ `entity_ids`/`indicator_names`/`rows`). Evaluated by the `RuleEngine`
and attached to collections via `rule_id`. The `llm` rule type (`target='rows'`)
powers structured extraction from text into `process_results`.

## Next

- Author a rule: [fd-daas-rules-creator](../skills/index.md).
- Bundle everything: [Create a Research](../examples/create-research.md).
