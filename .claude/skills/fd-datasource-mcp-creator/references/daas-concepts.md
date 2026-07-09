# daas concepts — condensed reference

Condensed from `construction/daas-storage.md` for use inside the
`fd-datasource-mcp-creator` skill. Read this once before your first onboarding.
Everything lives in the single shared `mcp/daas.db`; the model classes live in
`mcp/models/models.py` (the installable `mcp-models` package — schema changes
go there first).

## 1. The two "datasource" tables — do not confuse them

| table | owner | holds | key columns |
|---|---|---|---|
| **`sources`** | daas-mcp | the managed data sources (akshare, edgar, your new one). This is what `create_datasource` writes. | `id`, `name` (unique), `label`, `description`, `url`, `enabled`, `config` (JSON), `category_id` |
| `datasources` | dashboard / composite-mcp (legacy) | MCP-server registry entries — a *different concept* that shares the word. | `id`, `name`, `db_type`, `connection_string` |

**Rule of thumb:** "daas datasource" = `sources`. The other table is not part of
the daas data model. `create_datasource` writes to **`sources`**.

`enabled` is `NOT NULL` with a **Python-side** default — raw `INSERT INTO sources
(name, label)` will fail with `NOT NULL constraint failed: sources.enabled`. Set
`enabled` explicitly in raw SQL, or use the ORM / `create_datasource` tool.

## 2. Function + output-column registry

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
- This pair is what `search_functions` / `get_function_detail` return, and what
  the column→indicator matcher reads.
- **No `semantic_type` column** on `daas_function_columns` (that's on the
  dashboard's `datasource_columns` only). The matcher therefore matches by
  name / alias / fuzzy, not semantic_type.

> For the seeded external MCPs (edgar/edinet/yfinance/cnreport/hkex) this column
> registry is currently sparse — those MCPs expose a live object API, not a flat
> catalog. When onboarding a purpose-built MCP, register the "logical functions"
> + their columns from your Step-1 analysis so the matcher has something to read.

## 3. Routing — `datasource_forms` + `datasource_sections`

A tiny grammar so an agent can dispatch to the source with zero extra lookups:

```
mcp=<mcp-name> tool=<tool-name> [param=<key>=<value>]*
```

For params the agent must supply, the value is the literal `<ask-agent>`.
Example: `mcp=edgartools-mcp tool=get_financials param=ticker=<ask-agent> param=statement=income`.

`entity_datasource_links.identifier_in_source` lets `get_entity_coverage`
prefill the identifier-keyed params (`ticker`, `symbol`, `code`, …) and hand the
agent a ready-to-run instruction. Other `<ask-agent>` params (date, selector)
are left for the agent.

## 4. `observations` — the indicator store (existing, for computed indicators)

One row per `(source, function_name, indicator, date)`. Written by daas-mcp's
native adapters and by `run_indicator` (computed math: sma/ema/rsi/pct_change/…).
`source` is a soft string (no FK). `value` is stored as a string.

**This is distinct from the new `canonical_indicators` vocabulary.** `observations`
holds *computed* time-series points; `canonical_indicators` holds the *names*
that raw columns map to. The new tables do not write `observations` — they are a
metadata/mapping layer on top of `daas_function_columns`.

## 5. Entities + coverage

```
entities                         entity_datasource_links
  entity_type  ('stock'|'country')   entity_id  → entities.id (CASCADE)
  code        (canonical)             source_id  → sources.id (CASCADE)
  name                                identifier_in_source   -- value to plug in
  ticker                              coverage  ('full'|'partial'|'none')
  exchange
  country_code
  UNIQUE (entity_type, code)
```

`get_entity_coverage(entity)` walks links → sources and returns, per source: the
`identifier_in_source`, the routing `sections` (with identifier prefilled), and
`column_count`/`columns` from `daas_function_columns`. The same entity is
identified differently per source (AAPL → yfinance `AAPL`; → cnreport `600519`
for an A-share) — store the resolved identifier at link time.

`entity_sync.py` is the bulk writer (stocks from akshare market-list functions +
a curated country seed, auto-derived links by market/country rules). Mirror it
for a new source with a "list all" call.

## 6. The new tables — canonical indicator vocabulary + column mapping

Added once by Step 0 of the skill. Additive (`Base.metadata.create_all`, no
Alembic). Soft string refs everywhere — a source/indicator can be renamed without
breaking mappings.

### Model classes (paste into `mcp/models/models.py`)

```python
class CanonicalIndicator(Base):
    """Canonical indicator name that datasource columns map TO.

    Distinct from `indicator_rules` (computed math ops) and `observations`
    (computed time-series points). This is the *vocabulary* layer over
    `daas_function_columns`: it lets the same indicator (e.g. `close`) be
    queried uniformly across sources (yfinance.close, akshare.收盘, …).
    """
    __tablename__ = "canonical_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(128), nullable=False)
    description = Column(String, nullable=True)
    unit = Column(String(32), nullable=True)              # 'USD','CNY','%','ratio','count'
    semantic_type = Column(String(32), nullable=True)     # 'price','volume','ratio','index','rate'
    category = Column(String(64), nullable=True)          # 'market-data','fundamentals','macro','alternative'
    aliases = Column(JSON, nullable=True)                 # ["收盘","收盘价","Close*","Last"]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ColumnIndicatorMapping(Base):
    """Maps a daas datasource column to a canonical indicator name.

    Soft string refs (no FK to daas_function_columns) — mirrors
    observations.source / indicator_rules.datasource. Survives renames.
    """
    __tablename__ = "column_indicator_mappings"
    __table_args__ = (
        UniqueConstraint("source", "function_name", "column_name",
                         name="uq_column_indicator_mapping"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False, index=True)        # → sources.name (soft)
    function_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    indicator_name = Column(String(64), nullable=False, index=True)  # → canonical_indicators.name (soft)
    match_method = Column(String(16), nullable=True)   # 'exact'|'alias'|'fuzzy'|'manual'
    confidence = Column(Float, nullable=True)           # 0.0–1.0
    confirmed = Column(Boolean, default=False, nullable=False)  # False = proposed, True = human-confirmed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
```

> Keep these class definitions in sync with the inline copies in
> `scripts/setup_indicator_vocabulary.py` (the script re-declares them on the
> same `Base.metadata` so it can create the tables without a models.py edit).
> `Base.metadata.create_all` is idempotent, so re-running after pasting into
> models.py is a no-op.

### How the mapping is used

- **Auto-match** (`scripts/match_columns_to_indicators.py`): for each
  `daas_function_columns` row under a source, match against `canonical_indicators`
  by exact name → alias → fuzzy (≥0.85). `exact`/`alias` auto-confirm;
  `fuzzy` lands as a proposal (`confirmed=0`).
- **Human review**: the skill surfaces proposals to the user; confirm/edit.
- **Manual override**: insert a row with `match_method='manual'`, `confirmed=1`.
- **Cross-source query**: `SELECT source, function_name, column_name FROM
  column_indicator_mappings WHERE indicator_name='close'` → every source that
  exposes a closing price, with the per-source column name.
