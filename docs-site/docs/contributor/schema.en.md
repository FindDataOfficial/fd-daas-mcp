# daas.db Schema

The canonical DB is the git-tracked repo-root `daas.db`
(`DAAS_DATABASE_URL=sqlite:///daas.db`; relative paths resolve against repo
root). Query from repo root: `sqlite3 daas.db "..."`; `PRAGMA foreign_keys=ON`
for FK cascade.

## Registry / catalog

| Table | Role |
| --- | --- |
| `sources` | Datasource catalog (akshare, yfinance, edgar, ...). |
| `daas_functions` / `daas_function_columns` | Function + column catalog per source. |
| `datasources` / `datasource_forms` / `datasource_sections` / `datasource_columns` | Managed datasource + forms/sections/columns. |
| `datasource_collections` / `datasource_collection_items` | Named datasource bundles. |
| `categories` | Datasource category tree. |
| `entities` | Stocks/countries (`entity_type` ∈ stock/country). |
| `entity_datasource_links` | Entity -> datasource identifier mapping (+ `coverage`). |

## Indicators & observations

| Table | Role |
| --- | --- |
| `indicator_rules` | Indicator bindings (`name`, `datasource`, `source_table`, `date_column`, `value_column`, `op`, `params_json`, `indicator_name`, `enabled`, `score`). |
| `observations` | Computed series, keyed on `(source, function_name, indicator, date)`, `value` VARCHAR(64). |

## Collections & rules

| Table | Role |
| --- | --- |
| `entity_collections` / `entity_collection_items` / `entity_collection_changes` | Named entity groups + audit log. |
| `indicator_collections` / `indicator_collection_items` / `indicator_collection_changes` | Named indicator groups + audit log. |
| `rules` | Unified rule store (`rule_type` ∈ json/script/position/llm; `target` ∈ entity_ids/indicator_names/rows). |
| `process_results` | LLM extraction output (FK -> `rules.id`). |

## Fetched data

| Table | Role |
| --- | --- |
| `scraw_<slug>` | Scraped/fetched source-data tables (auto-created by `scripts/upsert.py`). |
| `pipeline_collections` / `pipeline_collection_items` | Pipeline items (cron-backed fetches). |

## Dashboards & research

| Table | Role |
| --- | --- |
| `dashboards` | Standalone-HTML dashboard registry. |
| `researches` | Persisted research bundle (entity/indicator/pipeline collections, dashboard slug, report md/path). |

## PDF vector search (optional, sqlite-vec)

| Table | Role |
| --- | --- |
| `pdf_documents` / `pdf_meta` / `pdf_chunks` | Ingested docs + chunks. |
| `pdf_chunks_vec` | `vec0` vector index (sqlite-vec). |

## MCP infrastructure

| Table | Role |
| --- | --- |
| `alert_rules` / `alert_events` | Alert rules + fired events. |
| `schedules` / `tasks` / `executions` | Cron tasks + schedules + history. |
| `composites` / `composite_chains` / `composite_tools` / `composite_upstreams` | Composite MCP server definitions. |
| `leader_upstreams` / `specialist_agents` / `workflows` / `workflow_steps` / `workflow_runs` / `workflow_step_results` | Leader (CrewAI) layer. |
| `data_snapshots` | Saved function-call snapshots. |
| `settings` | Key/value settings. |

## Useful queries

```bash
sqlite3 daas.db "SELECT entity_type, count(*) FROM entities GROUP BY entity_type;"
sqlite3 daas.db "SELECT count(*) FROM indicator_rules;"
sqlite3 daas.db "SELECT name FROM sqlite_master WHERE name LIKE 'scraw_%' ORDER BY name;"
sqlite3 daas.db "SELECT slug, name FROM dashboards;"
sqlite3 daas.db "SELECT name, status FROM researches;"
```

## Backups

`scripts/upsert.py` and `scripts/db.py` back up `daas.db` before writes. For a
full reset, use the `fd-coding-daas-reset-project` skill (3 guarded levels:
test-artifacts / data-only / full-baseline, with backup + dry-run + `--yes`).
