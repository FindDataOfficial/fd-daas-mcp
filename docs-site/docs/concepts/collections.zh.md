# 集合与指标

DAAS 把**你有什么数据**（原始获取序列）、**你计算什么**（指标）、**你怎么分组**（集合）分开。全部记录在 `daas.db`。

## 数据流

```
数据源 -> Python 库 -> scraw_<slug>  (原始获取行)
                          |
                          v
            indicator_rules -> observations  (计算序列)
                                    |
                                    v
                        集合 (实体 / 指标分组)
```

## 原始数据：`scraw_<slug>`

每次获取把行持久化到自动创建的 `scraw_<slug>` 表（`scripts/upsert.py` -- 自动 `CREATE` + `ALTER` + `INSERT OR REPLACE`，写入前备份 `daas.db`）。库中示例：`scraw_spy_daily`、`scraw_aapl_daily`、`scraw_massive_treasury_yields`。

```bash
sqlite3 daas.db "SELECT name FROM sqlite_master WHERE name LIKE 'scraw_%' LIMIT 10;"
```

## 指标规则：`indicator_rules`

一条指标规则把源表 + 列 + 数学算子 + 参数绑定到一个指标名。列：`name`、`datasource`、`source_table`、`date_column`、`value_column`、`op`、`params_json`、`indicator_name`、`enabled`、`score`。

```bash
sqlite3 daas.db "SELECT name, op, source_table, indicator_name FROM indicator_rules WHERE name LIKE 'SPY_%' LIMIT 5;"
```

用 `daas_create_indicator(...)` 或 `fd-daas-indicators-creator` 技能创建。用 `daas_run_indicator(name=...)` 或 `scripts/run_indicator.py <name>` 计算到 `observations`。

## 计算序列：`observations`

键为 `(source, function_name, indicator, date)`；`value` 是 `VARCHAR(64)`。这是每个看板和集合读取的表。

```bash
sqlite3 daas.db "SELECT indicator, date, value FROM observations WHERE indicator='SPY_ma5' ORDER BY date DESC LIMIT 5;"
```

## 实体集合

实体的命名分组（观察列表 / 组合），带**审计成员变动**。表：`entity_collections`、`entity_collection_items`、`entity_collection_changes`。

```bash
sqlite3 daas.db "SELECT name FROM entity_collections;"
sqlite3 daas.db "SELECT entity_id, action, source FROM entity_collection_changes LIMIT 5;"
```

- 手工：`daas_add_entity_to_collection` / `daas_remove_entity_from_collection`（记录 `add_in` / `remove_out` 事件，`source='manual'`）。
- 基于规则：附加一个 `rule_id`（json/script/position/llm），用 `daas_sync_entity_collection` 重新派生（`source='cron'`）。

## 指标集合

指标的可命名、可复用集合。表：`indicator_collections`、`indicator_collection_items`、`indicator_collection_changes`。审计模式同实体集合。

```bash
sqlite3 daas.db "SELECT name FROM indicator_collections;"
```

用 `daas_add_indicator_to_collection` 添加；基于规则的用 `daas_sync_indicator_collection` 同步。

## 分数

集合项带一个有效**分数**（优先级/质量权重），继承自指标/数据源默认值，可按集合覆盖（`daas_set_indicator_collection_item_score`）。当多个源/指标覆盖同一物时，分数用于排序。

## 规则：`rules`

统一规则存储（`rule_type` ∈ `json`/`script`/`position`/`llm`；`target` ∈ `entity_ids`/`indicator_names`/`rows`）。由 `RuleEngine` 求值，通过 `rule_id` 附加到集合。`llm` 规则类型（`target='rows'`)驱动从文本结构化抽取到 `process_results`。

## 下一步

- 编写规则：[fd-daas-rules-creator](../skills/index.md)。
- 把一切绑起来：[创建研究](../examples/create-research.md)。
