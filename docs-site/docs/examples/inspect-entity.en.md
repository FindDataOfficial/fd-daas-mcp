# Inspect an Entity

"Inspect" means: given a company / industry / city / country, see which
datasources cover it, how to fetch them, and what indicators exist. This is the
first step before any fetch or research.

## Find the entity

**MCP:**

```text
daas_search_entities(query="AAPL")
daas_search_entities(query="China")
```

`daas_search_entities` matches name, ticker, code, and aliases. It returns the
`entity_id` you use in the next step.

**SQL:**

```bash
sqlite3 daas.db "SELECT id, code, name, entity_type, exchange, country_code FROM entities WHERE name LIKE '%Apple%' LIMIT 5;"
```

## See coverage

`daas_get_entity_coverage` is the key tool - for a given `entity_id` it returns,
per linked datasource: the identifier to use, the available sections (routing
instructions), and the column count.

```text
daas_get_entity_coverage(entity_id=123)
```

This answers: *"I have company X - which datasources cover it, how many columns
can I get, and how do I fetch it?"*

## See the entity's links

An entity is linked to datasources via `entity_datasource_links` (the identifier
to plug into each source). Inspect them:

**MCP:** `daas_get_entity(entity_id=123)`

**SQL:**

```bash
sqlite3 daas.db """
SELECT s.name, l.identifier_in_source, l.coverage
FROM entity_datasource_links l JOIN sources s ON s.name = l.source_name
WHERE l.entity_id = 123;
"""
```

## See the entity's indicators

Once you know the entity's source tables, find indicator rules built on them:

```bash
sqlite3 daas.db "SELECT name, op, indicator_name FROM indicator_rules WHERE source_table LIKE 'scraw_aapl_%';"
```

And the latest computed values:

```bash
sqlite3 daas.db "SELECT indicator, date, value FROM observations WHERE indicator LIKE 'AAPL_%' ORDER BY date DESC LIMIT 10;"
```

## Industry / city / country

- **Industry** - inspect each member stock (a collection), then aggregate.
- **City** - regional entities and their indicators (e.g. a city's economic
  series via `cnstats`).
- **Country** - `daas_search_entities(query="CN")` -> the country entity -> its
  macro indicators (CPI, GDP, treasury yields).

## Next

Fetch + compute on top: [Extract Financial Reports](extract-financials.md), or
turn it into a [Research](create-research.md).
