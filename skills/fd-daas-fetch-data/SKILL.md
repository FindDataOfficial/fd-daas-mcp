---
name: fd-daas-fetch-data
description: End-to-end daas data-fetching workflow - look up an entity in the daas registry, resolve which datasource covers it, and define indicators over its source data. Use this skill whenever the user names a stock/company/country/index and wants to fetch data or compute indicators for it - phrases like "查一下比亚迪在 daas 里的数据源", "find which datasource covers AAPL", "给这只股票算个 SMA 指标", "look up entity BYD and create an indicator", "这只股票有哪些数据列", or any entity + "fetch data / get coverage / create indicator". Do NOT use this skill when the user wants to scrape a brand-new website into the database or build a full dashboard (use fd-daas-dashboard-creator) or persist data to a table (use fd-daas-indicators-creator); this skill stops at indicator creation. This skill uses sqlite3 on daas.db + the fd-daas-based-data-fetch scripts - NO MCP tools.
---

# fd-daas-fetch-data

Drive the entity -> datasource-coverage -> create-indicator workflow via **sqlite3 on `daas.db`** and the **`fd-daas-based-data-fetch`** scripts. No `mcp__*` tools, no `fd-*` CLIs. This is the foundation skill - `fd-daas-indicators-creator` (table + save) and `fd-daas-research` build on top of it.

## Mental model

Three things must end up true when this skill finishes:

1. **The entity is resolved** - a `sqlite3` query on the `entities` table confirmed the entity exists, and you surfaced its `identifier_in_source` per linked datasource.
2. **The covering datasource is known** - a `sqlite3` join across `entity_datasource_links` -> `sources` -> `daas_functions` -> `daas_function_columns` listed which sources cover the entity, with column counts, and `fd-daas-based-data-fetch/scripts/dispatch.py` told you how to fetch.
3. **At least one indicator is defined** - a `sqlite3` INSERT into `indicator_rules` (persists a binding) + `run_indicator.py` (computes + upserts), OR `run_indicator.py --calc` (ad-hoc, no persist), over a validated `source_table` + `value_column`.

If the user only wants steps 1-2 (no indicator), stop after step 2 and say so - do not invent an indicator.

## daas.db location

`DAAS_DATABASE_URL` in the repo-root `.env` points at the DB (currently `sqlite:///daas.db`). From the repo root, `sqlite3 daas.db "..."` works. The `fd-daas-based-data-fetch` scripts read `.env` automatically.

## Step 1 - Check the entities

Goal: confirm the entity exists in the daas registry and surface its linked datasources.

```bash
sqlite3 daas.db "SELECT id, entity_type, code, name, ticker, exchange, country_code FROM entities WHERE name LIKE '%比亚迪%' OR ticker LIKE '%BYD%' OR code LIKE '%002594%' OR aliases LIKE '%比亚迪%'"
```

1. Match case-insensitively against `name`, `ticker`, `code`, `aliases` (the `aliases` JSON column). Note the `id` for step 2.
2. If ambiguous (multiple matches), list them and ask the user to pick.
3. For the resolved entity, see its linked datasources directly:

```bash
sqlite3 daas.db "SELECT s.name AS source, l.identifier_in_source, l.coverage FROM entity_datasource_links l JOIN sources s ON s.id = l.source_id WHERE l.entity_id = <id>"
```

**Not found**: if the query returns nothing, tell the user "entity not found in the daas registry", suggest a looser `LIKE` query (e.g. a prefix), and STOP. Do not proceed to step 2. The entity may need to be added via `entity_sync.py --sync-all` (run by the user) or a manual INSERT once a datasource exists.

## Step 2 - Find the related datasource

Goal: resolve which datasource covers the entity, and how to fetch from it.

```bash
sqlite3 daas.db "SELECT s.name AS source, l.identifier_in_source, f.name AS function, fc.name AS column_name, fc.type
  FROM entity_datasource_links l
  JOIN sources s ON s.id = l.source_id
  JOIN daas_functions f ON f.source_id = s.id
  LEFT JOIN daas_function_columns fc ON fc.function_id = f.id
  WHERE l.entity_id = <id>"
```

1. This returns, per linked datasource: `identifier_in_source` (the value to plug into the source's lookup, e.g. `AAPL` for yfinance, `002594` for an A-share) + the available functions + their columns (from `daas_function_columns`).
2. To learn **how to fetch**, resolve the source's dispatch entry:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve <source>_<function>
```

   This returns the Python import + call shape + example snippet (e.g. akshare -> `ak.stock_zh_a_hist(...)`, worldbank -> REST `requests.get(...)`, cnstats -> `ak.macro_china_cpi_yearly()`). See `fd-daas-based-data-fetch/SKILL.md` for the full fetch+persist flow.

3. Surface to the user: "Datasource X covers <entity> via identifier <Y>; here are its N columns: ...". Ask which series they want an indicator over.

**No covering datasource**: if the entity has zero rows in `entity_datasource_links`, tell the user "no datasource covers this entity yet", suggest an `INSERT INTO entity_datasource_links` (if a matching datasource exists) or the scrape skill (if a new scrape is needed), and STOP.

## Step 3 - Create indicators

Goal: define one or more indicators over the source data.

1. Confirm the `source_table` + `value_column` exist (indicator rules accept **any table in `daas.db`**, not only `scraw_*`):

```bash
sqlite3 daas.db "SELECT name FROM sqlite_master WHERE type='table' AND name='scraw_spy_daily'"
sqlite3 daas.db "PRAGMA table_info(scraw_spy_daily)"
```

2. Pick the op from the catalog + its params (e.g. `{"window": 5}` for sma/rsi/zscore):

```bash
uv run --with pandas --with numpy python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --list-ops
```

3. **To persist** (replayable, writes the `observations` table): INSERT a rule, then compute it. Validate `datasource` exists in `sources`, `source_table` + columns exist, `op` is in the catalog before inserting:

```bash
sqlite3 daas.db "INSERT INTO indicator_rules (name, datasource, function_name, source_table, date_column, value_column, op, params_json, indicator_name, enabled) VALUES ('spy_ma5','yfinance','scraw_spy_daily','scraw_spy_daily','date','Close','sma','{\"window\":5}','spy_ma5',1)"
uv run --with pandas --with numpy python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py spy_ma5
```

4. **Ad-hoc** (no persist): `--calc` returns `{indicator, dates, values, count}` and writes nothing:

```bash
uv run --with pandas --with numpy python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py --calc scraw_spy_daily date Close sma window=5
```

Confirm to the user: "Indicator `<name>` created over `<source_table>.<value_column>` (op=<op>, params=<params>); run_indicator wrote N observations." or "calculate returned N values (not persisted)."

## Gotchas

- **Indicator rules accept any table in `daas.db`, not only `scraw_*`.** Don't reject a user's indicator over an `observations` or `process_results` table.
- **Identifier + table/column names are validated against `^[A-Za-z_][A-Za-z0-9_]*$`** before any SQL (the `run_indicator.py` script enforces this; do it for ad-hoc queries too). If the user gives a weird name, rename it to a valid slug.
- **`run_indicator.py` does a full recompute** (no cursor - windowed ops need lookback), then upserts into `observations` keyed on `(source, function_name, indicator, date)`. Idempotent on re-run. Backs up `daas.db` to `.bak` before writing.
- **`sqlite3` missing**: if `sqlite3` is not on PATH, report it and STOP. Do not silently fall back.
- This skill stops at indicator creation. To persist raw source data into a `scraw_<slug>` table, hand off to `fd-daas-indicators-creator`.
