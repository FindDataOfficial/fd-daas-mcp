# daas storage model — how datasources, columns & indicators are stored

A self-contained reference for how the daas layer persists **datasources**, their
**columns**, and **indicators** in the shared `mcp/daas.db`. Written so the model
can be reused outside this repo. Companion to `construction/mcp.md`.

All tables live in the single shared database `mcp/daas.db` and are defined in
the one SQLAlchemy `Base` at [`mcp/models/models.py`](../mcp/models/models.py).
Every MCP reads/writes here; schema changes go in `models.py` first.

---

## 1. The two "datasource" tables — do not confuse them

There are **two unrelated tables** whose names suggest "datasource". This is the
single most common source of bugs.

| table | owner | what it actually holds | key columns |
|---|---|---|---|
| **`sources`** | daas-mcp | the managed data sources (akshare, ckan, worldbank, edgar, edinet, yfinance, cnreport, hkex, + `scraw_*` archives). This is what `create_datasource` / `search_datasources` read/write. | `id`, `name` (unique), `label`, `description`, `url`, `enabled`, `config` (JSON), `category_id` |
| **`datasources`** | dashboard / combine-mcp (legacy) | MCP-server registry entries (cron, daas, dashboard, leader_mcp, …) — a *different concept* that happens to share the word. | `id`, `name`, `db_type`, `connection_string`, `is_readonly` |

**Rule of thumb:** when you hear "daas datasource", think `sources`. The
`datasources` table is not part of the daas data model.

`daas-mcp`'s `create_datasource` tool writes to **`sources`**, not `datasources`.

---

## 2. `sources` — the daas datasource registry

```
sources
  id            INTEGER PRIMARY KEY
  name          VARCHAR(64)  UNIQUE NOT NULL   -- 'akshare', 'ckan', 'edgar', ...
  label         VARCHAR(128) NOT NULL
  description   TEXT
  url           VARCHAR(512)
  enabled       BOOLEAN NOT NULL DEFAULT TRUE   -- Python-side default; raw INSERT must set it
  config        JSON                           -- {scraw_config: <slug>, ...}
  category_id   INTEGER  → categories.id (ON DELETE SET NULL)
  created_at, updated_at
```

- `name` is the stable handle everything else references **as a soft string**
  (no FK from indicator/process rules — see §5).
- `config.scraw_config` holds the slug of the scraped-data table
  (`scraw_<slug>`) that backs a scraw-type source, linking the source to its
  raw data table and to `scraw_configs.name`.
- `enabled` is `NOT NULL` with a **Python-side** default (`default=True` in the
  ORM), **not** a SQL `DEFAULT`. Raw `INSERT INTO sources (name, label)` will
  fail with `NOT NULL constraint failed: sources.enabled` — set `enabled`
  explicitly in raw SQL, or use the ORM / `create_datasource` tool.

### `categories` — hierarchical grouping

Self-referencing tree (`parent_id → categories.id`, `ON DELETE CASCADE`). Each
source optionally belongs to one category. `search_datasources` can filter by
category with subtree inclusion.

---

## 3. Per-source function + output-column registry

Two tables describe **what a source can return** (its function catalog and the
columns each function outputs). These are the daas equivalent of a schema
registry.

```
daas_functions                          daas_function_columns
  id            PK                        id            PK
  source_id  → sources.id (CASCADE)       function_id → daas_functions.id (CASCADE)
  name          UNIQUE per source          name          UNIQUE per function
  label                                    label
  description                              type          -- 'REAL','TEXT',...
  category                                 description
  parameters   JSON                         nullable
  output_type  -- default 'DataFrame'
```

- `daas_functions(source_id, name)` is unique → one `stock_zh_a_hist` per source.
- `daas_function_columns(function_id, name)` is unique → one `close` per function.
- This pair is what `search_functions` / `get_function_detail` return.

> **Note:** for the seeded external MCPs (edgar, edinet, yfinance, cnreport,
> hkex) this column registry is currently unpopulated — those MCPs expose a
> live object/functional API rather than a flat function catalog, so the
> registry pattern does not apply to them (see each MCP's CLAUDE.md section).
> akshare/cnstats/worldbank populate it via their harness migrators.

---

## 4. `datasource_columns` — the dashboard legacy (and its stale FK)

```
datasource_columns
  id            PK
  datasource_id → datasources.id (ON DELETE CASCADE)   -- ⚠ stale/wrong FK (see below)
  table_name
  column_name   UNIQUE per (datasource_id, table_name)
  column_type, is_primary_key, is_nullable, description, source_field, unit, semantic_type
```

This table belongs to the **dashboard** domain and describes columns of the
external databases registered in `datasources` (the legacy MCP-server table),
**not** daas `sources`. It is unrelated to `daas_function_columns`.

### ⚠ The stale-FK gotcha

`datasource_columns.datasource_id` declares `ForeignKey("datasources.id")` —
pointing at the **wrong** table for daas-mcp sources. Real daas source rows live
in `sources` with their own id sequence. Existing rows only survive because
ids 1–4 happen to coincide in both tables; for `sources.id >= 5` the FK rejects
the insert unless `PRAGMA foreign_keys=OFF`.

**If you need to attach column metadata to a daas source,** prefer
`daas_function_columns` (the daas-native column registry). If you must write
`datasource_columns`, target `sources.id` as `datasource_id` and disable FK
checks for the insert.

---

## 5. `observations` — the indicator store

This is the project's **indicator store**: one row per `(source, function,
indicator, date)` point. Already in production use (e.g. `cnstats_cpi`/`今值`,
5300+ rows).

```
observations
  id            PK
  source        VARCHAR(64)  NOT NULL   -- sources.name (soft string, no FK)
  function_name VARCHAR(255) NOT NULL
  indicator     VARCHAR(255) NOT NULL   -- '今值', 'sma5_close', ...
  date          VARCHAR(64)  NOT NULL   -- stored as TEXT
  value         VARCHAR(64)             -- stored as STRING (numeric value stringified)
  metadata      JSON                     -- free-form {rule_name, op, params, ...}
  UNIQUE (source, function_name, indicator, date)   -- uq_observation → idempotent upsert
```

Key properties:

- **Soft references.** `source` is `sources.name` as a plain string — **no FK**.
  A daas source can be renamed/recreated without breaking indicator rows.
- **`value` is a string.** `observations.value` is `String(64)`, so numeric
  indicator values are stringified on write (`str(7.1) → "7.1"`) and parsed back
  on read. The full float is recoverable from the string.
- **Unique on the 4-tuple.** Upserts are idempotent: re-running a computation
  over the same `(source, function, indicator, date)` updates the value rather
  than duplicating.
- **`metadata` carries provenance.** For process-mcp indicators it holds
  `{rule_name, op, params, value_column}` so a row is traceable back to the rule
  that produced it.

### Who writes here

- **daas-mcp** writes native indicators (e.g. `cnstats_cpi`) via its source
  adapters.
- **process-mcp** writes *computed* indicators (moving averages, returns, RSI,
  …) via `run_indicator` — see §6. Both upsert on the same unique constraint, so
  the only consequence of two writers targeting the same 4-tuple is
  last-write-wins (never duplication). Namespace indicator names (e.g.
  `sma5_close`) to avoid stomping daas-native indicators.

---

## 6. How process-mcp indicators write to `observations`

process-mcp adds a deterministic math path alongside its LLM-extraction path.
An **indicator rule** (`indicator_rules` table) binds:

- a daas `datasource` (soft ref to `sources.name`)
- a source data table + `date_column` + `value_column` (any table in `daas.db`,
  validated via `PRAGMA table_info`; the `scraw_<slug>` convention is reused for
  discovery but not required)
- a math `op` + `params` (from a fixed catalog: `sma`, `ema`, `rsi`,
  `pct_change`, `log_return`, `diff`, `rolling_std`, `rolling_min`,
  `rolling_max`, `zscore`, `ratio`, `level`)
- an output `indicator_name`

`run_indicator(name)` does a **full recompute** over the source table (no
incremental cursor — windowed ops need lookback) and upserts every
`(date, value)` into `observations` with:

```
source         = rule.datasource            (→ sources.name, soft)
function_name  = rule.function_name         (defaults to source_table)
indicator      = rule.indicator_name        (defaults to rule name)
date           = str(<date_column value>)
value          = str(<computed float>)       -- NaN / non-numeric rows skipped
metadata       = {rule_name, op, params, value_column}
```

The LLM-extraction path (`run_rule` / `extract_*`) is **forbidden** from touching
daas tables — only the indicator path writes `observations`. Deleting an
indicator rule does **not** cascade to its `observations` rows (soft reference);
the rows survive and remain identifiable via `metadata.rule_name`.

### Reusing this model elsewhere

If you replicate this pattern in another project:

1. Keep a single `sources` table as the datasource registry; reference it by
   **name as a soft string** from indicator/observation rows (no FK) so renames
   don't break history.
2. Use one `observations`-style table keyed on
   `(source, function, indicator, date)` with a unique constraint — this makes
   every computation idempotent and re-runnable.
3. Store numeric values as strings if your store is string-typed; keep the float
   in `metadata` if you need full precision.
4. Full-recompute per run for windowed ops; add an incremental cursor + warmup
   window only when row counts make full recompute expensive.
5. Separate the **computation** (deterministic, replayable) from the
   **extraction** (LLM, non-deterministic) — they share storage but not logic.

---

## 7. Entity registry + datasource coverage (`entities`, `entity_datasource_links`)

The daas layer models *datasources* and their *functions/columns*, but not the
**entities** those datasources describe (a stock, a country). Two tables add
that layer and link it to `sources` so an agent can answer *"I have company X
— which datasources cover it, how many columns can I get, and how do I fetch
it?"* in one call (`get_entity_coverage`).

```
entities
  id            PK
  entity_type   VARCHAR(32) NOT NULL INDEX   -- 'stock' | 'country'
  code          VARCHAR(64) NOT NULL INDEX   -- canonical: 6-digit A-share / 5-digit HK / US ticker / ISO alpha-2
  name          VARCHAR(255) NOT NULL
  ticker        VARCHAR(64) INDEX            -- display/lookup ticker (yfinance/edgar form)
  exchange      VARCHAR(32)                  -- 'SSE','SZSE','NASDAQ','HKEX', ...
  country_code  VARCHAR(8) INDEX             -- ISO 3166-1 alpha-2
  isin          VARCHAR(16)
  aliases       JSON                         -- ["贵州茅台", "Kweichow Moutai", ...]
  status        VARCHAR(16) NOT NULL DEFAULT 'active'   -- 'active' | 'delisted'
  metadata      JSON
  UNIQUE (entity_type, code)                 -- uq_entity_type_code → idempotent upsert

entity_datasource_links
  id            PK
  entity_id  → entities.id (ON DELETE CASCADE)
  source_id  → sources.id (ON DELETE CASCADE)
  identifier_in_source  VARCHAR(128)         -- value to plug into this source's lookup tool
  coverage     VARCHAR(16) NOT NULL DEFAULT 'full'   -- 'full' | 'partial' | 'none'
  metadata     JSON
  last_fetched_at, created_at
  UNIQUE (entity_id, source_id)              -- uq_entity_source → upsert per pair
```

Key properties:

- **Natural key `(entity_type, code)`.** `code` is the canonical market code per
  type (6-digit A-share, 5-digit HK, US ticker, ISO alpha-2 country). `ticker`
  is stored separately for sources that expect the ticker form. Upserts are
  idempotent on this key.
- **`identifier_in_source` is the link's payload.** The same entity is
  identified differently per datasource (AAPL → yfinance: `AAPL`; → edgar:
  `AAPL` since `get_company` accepts a ticker; 600519 → cnreport: `600519`;
  → yfinance: `600519.SS`). Storing the resolved identifier at link time means
  the coverage tool can hand the agent a ready-to-run routing instruction with
  zero extra lookups.
- **Cascade both ways.** Deleting an entity cascades to its links; deleting a
  `sources` row cascades to any links referencing it (requires
  `PRAGMA foreign_keys=ON`, which daas-mcp sets per-connection).

### The coverage flow (`get_entity_coverage`)

For a given entity, the tool walks `entity_datasource_links` → `sources`, and
for each linked source returns:

1. **`identifier_in_source`** + `coverage` — the value to plug in.
2. **`sections`** — every `(form_type, section_name, instruction)` under that
   source, plus a `prefilled_instruction` where `<ask-agent>` is replaced by
   `identifier_in_source` **only in identifier-keyed params**
   (`ticker_or_cik`, `ticker_or_name`, `ticker_or_code`, `ticker`, `symbol`,
   `code`). Other `<ask-agent>` params (e.g. `params_json`, `selector`,
   `date`) are left — the agent must still supply them. This is "how to get
   the data".
3. **`column_count` + `columns`** aggregated from `daas_function_columns`
   joined to `daas_functions` for that `source_id` (the daas-native column
   registry, §3). This is "how many columns". When the source has no
   registered `daas_functions` (the external-MCP sources — edgar/edinet/
   yfinance/cnreport/hkex), the tool instead returns a `column_hint`
   `{mcp, tool}` parsed from the section's routing instruction so the caller
   can fetch columns from the sibling MCP's `get_function_info`.

### Who writes here

- **`entity_sync.py`** (daas-mcp) is the sole writer of entity + link rows.
  It upserts stocks from akshare's market-list functions (`stock_info_a_code_name`
  for A-shares, `stock_hk_spot_em` for HK, `stock_us_spot_em` for US) plus a
  curated ~30-country seed, and auto-derives links by market/country rules
  (US→edgar+yfinance; A-share→cnreport+yfinance; HK→hkex+yfinance; country→
  worldbank, +cnstats for CN). Manual links are never deleted by the sync;
  stale stock codes are marked `status='delisted'` (rows retained). Run with
  `uv run --with akshare --directory mcp/daas-mcp python entity_sync.py --sync-all`;
  `--register-cron` installs a weekly cron-mcp refresh task+schedule
  (idempotent on names). akshare is imported lazily — the daas-mcp server
  doesn't need it.
- **Manual override** via the `link_entity_datasource` / `unlink_entity_datasource`
  tools (e.g. to add an ADR or dual-listing the rules don't cover).

