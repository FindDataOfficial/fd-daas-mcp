# daas.db 表结构

规范 DB 是仓库根目录的 git 跟踪 `daas.db`（`DAAS_DATABASE_URL=sqlite:///daas.db`；相对路径按仓库根解析）。从仓库根查询：`sqlite3 daas.db "..."`；`PRAGMA foreign_keys=ON` 做 FK 级联。

## 注册表 / 目录

| 表 | 角色 |
| --- | --- |
| `sources` | 数据源目录（akshare、yfinance、edgar……）。 |
| `daas_functions` / `daas_function_columns` | 每源函数 + 列目录。 |
| `datasources` / `datasource_forms` / `datasource_sections` / `datasource_columns` | 托管数据源 + forms/sections/columns。 |
| `datasource_collections` / `datasource_collection_items` | 命名数据源集合。 |
| `categories` | 数据源分类树。 |
| `entities` | 股票/国家（`entity_type` ∈ stock/country）。 |
| `entity_datasource_links` | 实体 -> 数据源标识符映射（+ `coverage`）。 |

## 指标与观测

| 表 | 角色 |
| --- | --- |
| `indicator_rules` | 指标绑定（`name`、`datasource`、`source_table`、`date_column`、`value_column`、`op`、`params_json`、`indicator_name`、`enabled`、`score`）。 |
| `observations` | 计算序列，键为 `(source, function_name, indicator, date)`，`value` VARCHAR(64)。 |

## 集合与规则

| 表 | 角色 |
| --- | --- |
| `entity_collections` / `entity_collection_items` / `entity_collection_changes` | 命名实体组 + 审计日志。 |
| `indicator_collections` / `indicator_collection_items` / `indicator_collection_changes` | 命名指标组 + 审计日志。 |
| `rules` | 统一规则存储（`rule_type` ∈ json/script/position/llm；`target` ∈ entity_ids/indicator_names/rows）。 |
| `process_results` | LLM 抽取输出（FK -> `rules.id`）。 |

## 获取的数据

| 表 | 角色 |
| --- | --- |
| `scraw_<slug>` | 抓取/获取的源数据表（由 `scripts/upsert.py` 自动创建）。 |
| `pipeline_collections` / `pipeline_collection_items` | 流水线项（cron 支撑的获取）。 |

## 看板与研究

| 表 | 角色 |
| --- | --- |
| `dashboards` | 独立 HTML 看板注册表。 |
| `researches` | 持久化研究包（实体/指标/流水线集合、看板 slug、报告 md/path）。 |

## PDF 向量搜索（可选，sqlite-vec）

| 表 | 角色 |
| --- | --- |
| `pdf_documents` / `pdf_meta` / `pdf_chunks` | 导入的文档 + 分块。 |
| `pdf_chunks_vec` | `vec0` 向量索引（sqlite-vec）。 |

## MCP 基础设施

| 表 | 角色 |
| --- | --- |
| `alert_rules` / `alert_events` | 告警规则 + 触发事件。 |
| `schedules` / `tasks` / `executions` | cron 任务 + 调度 + 历史。 |
| `composites` / `composite_chains` / `composite_tools` / `composite_upstreams` | 组合 MCP 服务器定义。 |
| `gateway_upstreams` / `workflows` / `workflow_steps` / `workflow_runs` / `workflow_step_results` | Gateway + workflow 层。 |
| `settings` | 键值设置。 |

## 实用查询

```bash
sqlite3 daas.db "SELECT entity_type, count(*) FROM entities GROUP BY entity_type;"
sqlite3 daas.db "SELECT count(*) FROM indicator_rules;"
sqlite3 daas.db "SELECT name FROM sqlite_master WHERE name LIKE 'scraw_%' ORDER BY name;"
sqlite3 daas.db "SELECT slug, name FROM dashboards;"
sqlite3 daas.db "SELECT name, status FROM researches;"
```

## 备份

`scripts/upsert.py` 和 `scripts/db.py` 写入前备份 `daas.db`。完整重置用 `fd-coding-daas-reset-project` 技能（3 个受保护级别：test-artifacts / data-only / full-baseline，带备份 + 干跑 + `--yes`）。
