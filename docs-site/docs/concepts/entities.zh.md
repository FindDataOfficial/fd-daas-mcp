# 实体

**实体**是 DAAS 可以*获取数据关于其*的任何东西 -- 目前是**股票**或**国家**。实体记录在 `entities` 表，通过 `entity_datasource_links` 关联到一个或多个**数据源**。

## `entities` 表

```bash
sqlite3 daas.db "SELECT id, code, name, entity_type, exchange, country_code FROM entities LIMIT 5;"
```

| 列 | 含义 |
| --- | --- |
| `id` | 内部实体 id（MCP 工具使用）。 |
| `code` | 规范代码（如 `AAPL`、`CN`）。 |
| `name` | 显示名。 |
| `entity_type` | `stock` 或 `country`。 |
| `exchange` | 交易所（股票）-- 如 `NASDAQ`、`SSE`。 |
| `country_code` | ISO 3166-1 alpha-2（如 `US`、`CN`）。 |

开箱即用：**5,575 只股票 + 60 个国家**。

## 实体 -> 数据源关联

每个实体关联到覆盖它的每个数据源，存储*要填入该源的标识符*（如 AAPL -> yfinance: `AAPL`；某中国股票 -> akshare: 其数字代码）。这就是 `entity_datasource_links` 表。

```bash
sqlite3 daas.db """
SELECT s.name, l.identifier_in_source, l.coverage
FROM entity_datasource_links l JOIN sources s ON s.name = l.source_name
WHERE l.entity_id = 1;
"""
```

- `identifier_in_source` -- 传给源查询的值。
- `coverage` -- `full` / `partial` / `none`。

用 `daas_link_entity_datasource(entity_id, source_name, identifier_in_source)` 关联实体。

## 搜索实体

```text
daas_search_entities(query="Apple")
daas_search_entities(query="China", entity_type="country")
```

匹配名称、ticker、代码、别名。返回用于覆盖/获取的 `entity_id`。

## 实体覆盖

`daas_get_entity_coverage(entity_id)` 按关联数据源返回：要用的标识符、可用 section（路由说明）、列数。它回答*"哪些源覆盖 X、怎么获取？"*

## 工作流中的实体类型

- **公司** -- 单只股票实体（`AAPL`）。
- **行业** -- 股票实体的一个*集合*（半导体、银行）。
- **城市** -- 区域实体 + 其经济序列（常来自 `cnstats`）。
- **国家** -- 国家实体（`CN`、`US`）+ 宏观指标（CPI、GDP）。

## 下一步

把实体分组为观察列表：[集合与指标](collections.md)。
