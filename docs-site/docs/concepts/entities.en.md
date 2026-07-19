# Entities

An **entity** is anything DAAS can fetch data *about* - currently a **stock** or
a **country**. Entities live in the `entities` table and are linked to one or
more **datasources** via `entity_datasource_links`.

## The `entities` table

```bash
sqlite3 daas.db "SELECT id, code, name, entity_type, exchange, country_code FROM entities LIMIT 5;"
```

| Column | Meaning |
| --- | --- |
| `id` | Internal entity id (used by MCP tools). |
| `code` | Canonical code (e.g. `AAPL`, `CN`). |
| `name` | Display name. |
| `entity_type` | `stock` or `country`. |
| `exchange` | Exchange (stocks) - e.g. `NASDAQ`, `SSE`. |
| `country_code` | ISO 3166-1 alpha-2 (e.g. `US`, `CN`). |

Out of the box: **5,575 stocks + 60 countries**.

## Entity -> datasource links

An entity is linked to each datasource that covers it, storing the *identifier
to plug into that source* (e.g. AAPL -> yfinance: `AAPL`; a China stock ->
akshare: its numeric code). This is the `entity_datasource_links` table.

```bash
sqlite3 daas.db """
SELECT s.name, l.identifier_in_source, l.coverage
FROM entity_datasource_links l JOIN sources s ON s.name = l.source_name
WHERE l.entity_id = 1;
"""
```

- `identifier_in_source` - the value to pass to the source's lookup.
- `coverage` - `full` / `partial` / `none`.

Link an entity with `daas_link_entity_datasource(entity_id, source_name,
identifier_in_source)`.

## Searching entities

```text
daas_search_entities(query="Apple")
daas_search_entities(query="China", entity_type="country")
```

Matches name, ticker, code, and aliases. Returns the `entity_id` you use for
coverage/fetch.

## Entity coverage

`daas_get_entity_coverage(entity_id)` returns, per linked datasource: the
identifier to use, the available sections (routing instructions), and the
column count. It answers *"which sources cover X, and how do I fetch them?"*

## Entity types in workflows

- **Company** - a single stock entity (`AAPL`).
- **Industry** - a *collection* of stock entities (semiconductors, banks).
- **City** - a regional entity + its economic series (often via `cnstats`).
- **Country** - a country entity (`CN`, `US`) + macro indicators (CPI, GDP).

## Next

Group entities into a watchlist: [Collections & Indicators](collections.md).
