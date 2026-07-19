# fd-daas-dashboard（与 -creator）

两个技能覆盖看板：**`fd-daas-dashboard``*查找/使用*已有看板，**`fd-daas-dashboard-creator`**用于*构建*新看板。两者都是对 `dashboards` 注册表的读/写；都不用 MCP 工具（`sqlite3` + `register_dashboard.py` 脚本）。

## fd-daas-dashboard - 查找与检视（只读）

想**使用或查找**已建好的看板时用。

**触发：** "我们有哪些看板"、"打开之前那个看板"、"show me the BYD dashboard"、"leaders 看板里是什么数据"、"有没有关于比特币的看板"、"what data backs this dashboard" -- 任何"dashboard / 看板" + "open / find / list / show"。

**做什么：**

- 列出每个看板。
- 按关键词（名称 / 简介 / 源表）搜索。
- 显示看板的简介 + 数据血缘 + 实体/时间覆盖。
- 在浏览器打开。
- 查询支撑它的行。

它是 `dashboards` 注册表的**只读** -- 列出、描述、打开、查询底层数据，仅此。

## fd-daas-dashboard-creator - 构建（写）

想把 daas 数据**可视化**为看板时用。

**触发：** "给这些指标做一个看板"、"build a dashboard for these indicators"、"画一个图看看这个 scraw 表"、"visualize this series"、"做个图表" -- 任何 daas 数据 + "dashboard / chart / visualize / 看板 / 图表"。

**做什么：**

1. 提议名称 + 简介 + 结构。
2. 验证源数据。
3. 用 ECharts 和可交互的实体 + 时间过滤器构建一个**独立 HTML 文件**。
4. 提议打开、迭代修改。
5. 在 `dashboards` 表**注册**（重建看板索引 `dashboards/index.html` + `daas.md`）。
6. 在 `daas-doc/dashboard/<name>-dashboard.md` 写一份配套说明。

它**不**打开/查找已有看板（用 `fd-daas-dashboard`），也不创建指标（用 `fd-daas-indicators-creator`）。

## `dashboards` 表

```bash
sqlite3 daas.db "SELECT slug, name, file_url FROM dashboards LIMIT 5;"
```

列：`slug`、`name`、`intro`、`source_tables`、`entity_coverage`、`time_range`、`refresh_cadence`、`chart_config`、`file_path`、`file_url`。

## MCP 等价（dashboard 组）

```text
dashboard_register(slug=..., name=..., intro=..., source_tables=..., refresh_cadence=..., file_path=..., file_url=...)
dashboard_list()
dashboard_search(keyword="momentum")
dashboard_get(slug="my-momentum")
dashboard_update(slug="my-momentum", intro="...")
dashboard_delete(slug="my-momentum")
```

## 分享

建好后，通过 WiFi 或隧道 [分享看板](../examples/share-dashboard.md)。
