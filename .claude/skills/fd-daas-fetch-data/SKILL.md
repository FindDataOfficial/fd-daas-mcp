---
name: fd-daas-fetch-data
description: End-to-end daas data-fetching workflow — look up an entity in the daas registry, resolve which datasource covers it, and define indicators over its source data. Use this skill whenever the user names a stock/company/country/index and wants to fetch data or compute indicators for it through the daas MCP — phrases like "查一下比亚迪在 daas 里的数据源", "find which datasource covers AAPL", "给这只股票算个 SMA 指标", "look up entity BYD and create an indicator", "这只股票有哪些数据列", or any entity + "fetch data / get coverage / create indicator". Do NOT use this skill when the user wants to scrape a brand-new website into the database (use fd-daas-scrapling-scraw-creator) or build a full dashboard (use fd-daas-dashboard-creator) or persist data to a table + cron (use fd-daas-indicators-creator); this skill stops at indicator creation.
---

# fd-daas-fetch-data

Drive the entity → datasource-coverage → create-indicator workflow via the daas MCP. This is the foundation skill — `fd-daas-indicators-creator` (table + save + cron) and `fd-daas-research` build on top of it.

## Mental model

Three things must end up true when this skill finishes:

1. **The entity is resolved** — `mcp__daas-mcp__search_entities` confirmed the entity exists, and you surfaced its `identifier_in_source` per linked datasource.
2. **The covering datasource is known** — `mcp__daas-mcp__get_entity_coverage` listed which sources cover the entity, with column counts and routing instructions.
3. **At least one indicator is defined** — `mcp__daas-mcp__create_indicator` (persists a binding) or `mcp__daas-mcp__calculate` (ad-hoc, no persist) over a validated `source_table` + `value_column`.

If the user only wants steps 1–2 (no indicator), stop after step 2 and say so — do not invent an indicator.

## Step 1 — Check the entities

Goal: confirm the entity exists in the daas registry and surface its linked datasources.

1. Call `mcp__daas-mcp__search_entities` with the user's name/ticker/code. It matches case-insensitively against name, ticker, code, and aliases, and returns name/ticker/code + `entity_type` (`stock` or `country`) + the `entity_id` you'll need in step 2.
2. If the user gave a 6-digit A-share code, a US ticker, or a Chinese/English name, one call usually resolves it. If ambiguous (multiple matches), list them and ask the user to pick.
3. For the resolved entity, call `mcp__daas-mcp__get_entity` with the `entity_id` to see its aliases + the datasources already linked to it (the `links` list).

**Not found**: if `search_entities` returns nothing, tell the user "entity not found in the daas registry", suggest a looser `search_entities` query (e.g. a prefix or alias), and STOP. Do not proceed to step 2. The entity may need to be added via `mcp/daas-mcp/entity_sync.py --sync-all` (run by the user) or `link_entity_datasource` once a datasource exists.

## Step 2 — Find the related datasource

Goal: resolve which datasource covers the entity, and how to fetch from it.

1. Call `mcp__daas-mcp__get_entity_coverage` with the `entity_id` from step 1.
2. It returns, per linked datasource: `identifier_in_source` (the value to plug into the source's lookup, e.g. `AAPL` for yfinance, `002594` for cnreport), the available `sections` (routing instructions = how to get the data, with an identifier-prefilled variant), and `column_count` / `columns` aggregated from `daas_function_columns`.
3. For **daas-internal sources** (akshare, cnstats, worldbank, ckan), `columns` is the real column list. For **external-MCP sources** (edgar, edinet, yfinance, cnreport, hkex), you get a `column_hint` naming the sibling MCP + tool — call `mcp__leader-mcp__get_function_detail` (or the sibling MCP's `get_function_info`) to expand the columns.
4. Surface to the user: "Datasource X covers <entity> via identifier <Y>; here are its N columns: …". Ask which series they want an indicator over.

**No covering datasource**: if the entity has zero linked datasources, tell the user "no datasource covers this entity yet", suggest `mcp__daas-mcp__link_entity_datasource` (if a matching datasource exists) or the `fd-daas-scrapling-scraw-creator` skill (if a new scrape is needed), and STOP.

## Step 3 — Create indicators

Goal: define one or more indicators over the source data.

1. First confirm the `source_table` and `value_column` exist. Call `mcp__daas-mcp__list_source_tables` (introspects `sqlite_master` for `scraw_*` and returns each with row count + columns) OR, for a non-scraw table, query via `mcp__dashboard-mcp__query_table`. Indicator rules accept **any table in `daas.db`**, not only `scraw_*` — so an `observations` row or a `process_results` table works too.
2. Pick the op from `mcp__daas-mcp__list_indicator_ops` (`sma`, `ema`, `rsi`, `pct_change`, `log_return`, `diff`, `rolling_std`, `rolling_min`, `rolling_max`, `zscore`, `ratio`, `level`) + its params (e.g. `{"window": 5}` for sma/rsi/zscore).
3. **To persist** (replayable, writes the `observations` table): call `mcp__daas-mcp__create_indicator` with `name`, `datasource` (soft-ref to `sources.name`), `source_table`, `date_column`, `value_column`, `op`, `params`, and optional `indicator_name` / `function_name`. Then `mcp__daas-mcp__run_indicator` to compute + upsert.
4. **Ad-hoc** (no persist): call `mcp__daas-mcp__calculate` with the same fields — returns `{indicator, dates, values, count}` and writes nothing.

Confirm to the user: "Indicator `<name>` created over `<source_table>.<value_column>` (op=<op>, params=<params>); run_indicator wrote N observations." or "calculate returned N values (not persisted)."

## Gotchas

- **`create_indicator` accepts any table in `daas.db`, not only `scraw_*`.** The `scraw_*`-only restriction belongs to `create_rule` (the LLM extraction path). Don't reject a user's indicator over an `observations` or `process_results` table.
- **Identifier + table/column names are validated against `^[A-Za-z_][A-Za-z0-9_]*$`** before any SQL (guard against injection on dynamic table/column names — they cannot be bind params). If the user gives a weird name, rename it to a valid slug.
- **`run_indicator` does a full recompute** (no cursor — windowed ops need lookback), then upserts into `observations` keyed on `(source, function_name, indicator, date)`. Idempotent on re-run.
- **Tool missing / unavailable**: if a required `mcp__daas-mcp__*` tool is not present at run time, report which tool is missing and STOP. Do not silently fall back.
- This skill stops at indicator creation. To persist raw source data into a `scraw_<slug>` table + schedule a refresh cron, hand off to `fd-daas-indicators-creator`.
