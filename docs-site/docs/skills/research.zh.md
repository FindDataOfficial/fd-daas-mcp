# fd-daas-research

**编排完整的 DAAS 研究工作流。** 这是旗舰技能 -- 把一个自然语言需求变成一份带指标、看板、Markdown 报告的持久化研究。

## 何时触发

如：

- "帮我研究一下比亚迪，做指标和看板"
- "research TSLA - build indicators and a dashboard"
- "研究一下沪深300成分股做个看板"
- "research SSE banks - set up indicators and a dashboard"
- "分析这只股票并做个可视化"

……或任何实体 + "research / 分析 / 研究 / full pipeline"。

## 流程

```
分析需求 -> [实体集合] -> 指标 -> 看板
        -> 持久化为 `research` 研究包 -> 生成 Markdown 报告
```

1. **分析** 需求为计划（用 `sqlite3` 获取计划上下文）。
2. 通过 `fd-daas-*` 创建技能**构建组件**：
   - 若需求点名一个组（观察列表、一条如"SSE banks"的规则、明确的代码列表），它先委托 `fd-daas-entities-collection-creator` 持久化该组。
   - 在成员上构建指标。
   - 构建看板。
3. 用 `research_*` MCP 工具（`research_create`）把整个研究**持久化**为一行 `researches`。
4. **生成 Markdown 报告**（`research_generate_report`），写到 `researches/<name>.md`。
5. 输出一个 `skill-run-notification` 块。

## 刷新 vs. 重建

对已存在研究的重复需求，本技能会**刷新**（`research_refresh` -- 重算指标、重同步基于规则的集合）并重新生成报告，而非从零重建。它会自动探测已有研究。

## 不做什么

- 只指标？用 `fd-daas-indicators-creator`。
- 只看板？用 `fd-daas-dashboard-creator`。
- 一次性获取？用 `fd-daas-fetch-data`。
- 只实体集合？用 `fd-daas-entities-collection-creator`。

本技能编排**完整**的 分析 -> [集合] -> 指标 -> 看板 -> 研究包 流程。

## 示例

> 研究比亚迪的趋势：构建实体 + 指标集合，计算指标，做个看板，并作为研究包持久化、生成 Markdown 报告。

结果：

```text
researches/byd-trend.md          # 生成的报告
daas.db 中的 researches 行        # 持久化研究包
dashboards/<slug>/index.html     # 看板
```

## MCP 等价

```text
research_create(name="byd-trend", entity_collection_name=..., indicator_collection_name=..., dashboard_slug=..., pipeline_collection_name=...)
research_generate_report(name="byd-trend")
research_refresh(name="byd-trend")        # 之后刷新数据
research_get(name="byd-trend")            # 检视
```

## 适用于任何范围

公司、行业（一组股票）、城市、国家 -- 你构建的集合定义范围。见 [创建研究](../examples/create-research.md)。
