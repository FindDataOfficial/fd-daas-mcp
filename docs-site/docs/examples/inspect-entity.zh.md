# 检视实体

"检视"指：给定一个公司/行业/城市/国家，查看它被哪些数据源覆盖、如何获取、有哪些指标。这是任何获取或研究前的第一步。

## 查找实体

**MCP：**

```text
daas_search_entities(query="AAPL")
daas_search_entities(query="China")
```

`daas_search_entities` 匹配名称、ticker、代码、别名。返回下一步要用的 `entity_id`。

**SQL：**

```bash
sqlite3 daas.db "SELECT id, code, name, entity_type, exchange, country_code FROM entities WHERE name LIKE '%Apple%' LIMIT 5;"
```

## 查看覆盖

`daas_get_entity_coverage` 是关键工具 -- 给定 `entity_id`，它按关联数据源返回：要用的标识符、可用 section（路由说明）、列数。

```text
daas_get_entity_coverage(entity_id=123)
```

它回答：*"我有公司 X -- 哪些数据源覆盖它、能拿多少列、怎么获取？"*

## 查看实体的关联

实体通过 `entity_datasource_links`（每个源要填入的标识符）关联到数据源。检视：

**MCP：** `daas_get_entity(entity_id=123)`

**SQL：**

```bash
sqlite3 daas.db """
SELECT s.name, l.identifier_in_source, l.coverage
FROM entity_datasource_links l JOIN sources s ON s.name = l.source_name
WHERE l.entity_id = 123;
"""
```

## 查看实体的指标

知道实体的源表后，找基于它们的指标规则：

```bash
sqlite3 daas.db "SELECT name, op, indicator_name FROM indicator_rules WHERE source_table LIKE 'scraw_aapl_%';"
```

以及最新计算值：

```bash
sqlite3 daas.db "SELECT indicator, date, value FROM observations WHERE indicator LIKE 'AAPL_%' ORDER BY date DESC LIMIT 10;"
```

## 行业 / 城市 / 国家

- **行业** -- 检视每个成员股票（一个集合），再聚合。
- **城市** -- 区域实体及其指标（如某城市的经济序列，来自 `cnstats`）。
- **国家** -- `daas_search_entities(query="CN")` -> 国家实体 -> 其宏观指标（CPI、GDP、国债收益率）。

## 下一步

在其上获取并计算：[提取财报](extract-financials.md)，或变成一个 [研究](create-research.md)。
