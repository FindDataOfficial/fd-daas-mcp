# 创建集合

集合是**实体**（一个观察列表）或**指标**（一个可复用集合）的命名、带审计的分组。本示例各建一个。

## 1. 创建实体集合

把你想一起跟踪的股票放一组。

**技能：**

> 创建一个名为 `my_watchlist` 的实体集合，加入 AAPL、MSFT、NVDA。

`fd-daas-entities-collection-creator` 技能（或 `fd-daas-entities-collection`）会创建集合并添加成员，为每次添加记录 `add_in` 审计事件。

**MCP：**

```text
daas_create_entity_collection(name="my_watchlist", description="My watchlist")
daas_add_entity_to_collection(collection_name="my_watchlist", entity_type="stock", code="AAPL")
daas_add_entity_to_collection(collection_name="my_watchlist", entity_type="stock", code="MSFT")
daas_add_entity_to_collection(collection_name="my_watchlist", entity_type="stock", code="NVDA")
```

**SQL（验证）：**

```bash
sqlite3 daas.db "SELECT name FROM entity_collections;"
sqlite3 daas.db "SELECT entity_id, action, source FROM entity_collection_changes WHERE collection_name='my_watchlist' LIMIT 5;"
```

!!! note "基于规则的集合"
    集合可带一个 `rule_id`（json/script/position/llm），成员由 `daas_sync_entity_collection` 重新派生，而非手工添加。见 [fd-daas-rules-creator](../skills/index.md)。

## 2. 创建指标集合

一个可复用的指标集合 -- 如"我所有的动量信号"。

**技能：**

> 创建一个名为 `momentum` 的指标集合，加入 SPY_ma5、SPY_rsi14、QQQ_ma20。

`fd-daas-indicators-collection-creator` 技能会创建集合、加入指标，并可导出为 CSV/markdown 到 `daas-doc/indicators/`。

**MCP：**

```text
daas_create_indicator_collection(name="momentum", description="Momentum signals")
daas_add_indicator_to_collection(collection_name="momentum", indicator_name="SPY_ma5")
daas_add_indicator_to_collection(collection_name="momentum", indicator_name="SPY_rsi14")
daas_add_indicator_to_collection(collection_name="momentum", indicator_name="QQQ_ma20")
```

**SQL（验证）：**

```bash
sqlite3 daas.db "SELECT name FROM indicator_collections;"
sqlite3 daas.db "SELECT indicator_name FROM indicator_collection_items WHERE collection_name='momentum';"
```

## 3. 分数

实体集合项和指标集合项都带一个有效*分数*（优先级/质量权重），继承自指标/数据源默认值，可按集合覆盖（`daas_set_indicator_collection_item_score` / `daas_set_collection_item_score`），或清空以继承默认。

## 下一步

把这些集合变成完整研究：[创建研究](create-research.md)。
