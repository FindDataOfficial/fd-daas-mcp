# Create Collections

Collections are named, audit-tracked groups of **entities** (a watchlist) or
**indicators** (a reusable bundle). This example builds one of each.

## 1. Create an entity collection

A collection of stocks you want to track together.

**Skill:**

> Create an entity collection named `my_watchlist` and add AAPL, MSFT, and NVDA.

The `fd-daas-entities-collection-creator` skill (or `fd-daas-entities-collection`)
creates the collection and adds members, recording an `add_in` audit event for
each.

**MCP:**

```text
daas_create_entity_collection(name="my_watchlist", description="My watchlist")
daas_add_entity_to_collection(collection_name="my_watchlist", entity_type="stock", code="AAPL")
daas_add_entity_to_collection(collection_name="my_watchlist", entity_type="stock", code="MSFT")
daas_add_entity_to_collection(collection_name="my_watchlist", entity_type="stock", code="NVDA")
```

**SQL (verify):**

```bash
sqlite3 daas.db "SELECT name FROM entity_collections;"
sqlite3 daas.db "SELECT entity_id, action, source FROM entity_collection_changes WHERE collection_name='my_watchlist' LIMIT 5;"
```

!!! note "Rule-based collections"
    A collection can carry a `rule_id` (json/script/position/llm) so membership
    is re-derived by `daas_sync_entity_collection` instead of manual adds. See
    [fd-daas-rules-creator](../skills/index.md).

## 2. Create an indicator collection

A reusable bundle of indicators - e.g. "all my momentum signals".

**Skill:**

> Create an indicator collection named `momentum` and add SPY_ma5, SPY_rsi14, and QQQ_ma20.

The `fd-daas-indicators-collection-creator` skill creates the collection, adds
the indicators, and can export it to CSV/markdown under `daas-doc/indicators/`.

**MCP:**

```text
daas_create_indicator_collection(name="momentum", description="Momentum signals")
daas_add_indicator_to_collection(collection_name="momentum", indicator_name="SPY_ma5")
daas_add_indicator_to_collection(collection_name="momentum", indicator_name="SPY_rsi14")
daas_add_indicator_to_collection(collection_name="momentum", indicator_name="QQQ_ma20")
```

**SQL (verify):**

```bash
sqlite3 daas.db "SELECT name FROM indicator_collections;"
sqlite3 daas.db "SELECT indicator_name FROM indicator_collection_items WHERE collection_name='momentum';"
```

## 3. Scores

Both entity-collection items and indicator-collection items carry an effective
*score* (priority/quality weight). Override per-collection with
`daas_set_indicator_collection_item_score` /
`daas_set_collection_item_score`, or clear it to inherit the source/indicator
default.

## Next

Turn these collections into a full study: [Create a Research](create-research.md).
