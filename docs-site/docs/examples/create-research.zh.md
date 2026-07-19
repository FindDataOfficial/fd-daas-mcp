# 创建研究

**研究**是 DAAS 的顶层产物：一份持久化研究包，把实体集合、指标集合、看板、数据流水线与一份生成的 Markdown 报告绑在一起。可用于一家公司、一个行业、一个城市或一个国家。

## 流程

```
目标 -> brainstorm（可选） -> [实体集合] + [指标集合]
     -> 计算指标 -> 看板 -> 研究包 -> Markdown 报告
```

## 1.（可选）梳理目标

若目标还模糊，先用 `fd-daas-brainstorm`。它通过对话澄清目标，写一份计划到 `daas-doc/research/<plan-slug>.md` -- 不写 `daas.db` 状态。见 [fd-daas-brainstorm](../skills/brainstorm.md)。

## 2. 运行研究技能

`fd-daas-research` 技能编排整个流程。在 Claude Code 里：

> 研究比亚迪的趋势：构建实体 + 指标集合，计算指标，做个看板，并作为研究包持久化、生成 Markdown 报告。

技能会：

1. 自动探测已有研究，决定刷新还是重建。
2. 构建（或复用）实体 + 指标集合。
3. 计算每个指标（`daas_run_indicator`）并同步基于规则的集合。
4. 创建/更新看板。
5. 持久化一行 `researches` + 写 `researches/<name>.md`。
6. 输出一个 `skill-run-notification` 块。

## 3. 通过 MCP 运行

若偏好直接调工具：

```text
research_create(name="byd-trend",
                entity_collection_name="byd-watchlist",
                indicator_collection_name="byd-momentum",
                dashboard_slug="byd-trend",
                pipeline_collection_name="byd-pipeline")
research_generate_report(name="byd-trend")
```

之后**刷新**数据（重算指标、重同步集合）：

```text
research_refresh(name="byd-trend")
```

## 4. 检视

```bash
sqlite3 daas.db "SELECT name, status, report_path FROM researches;"
cat researches/byd-trend.md
```

或通过 MCP：`research_get(name="byd-trend")` / `research_list()`。

## 适用于任何实体类型

同一流程适用于**公司**（比亚迪、AAPL）、**行业**（一组股票）、**城市**（一个区域实体 + 其指标）、**国家**（CN/US 宏观序列）。你构建的集合定义了范围。

## 下一步

- 看刚生成的看板：[分享看板](share-dashboard.md)。
- 理解研究包：[fd-daas-research](../skills/research.md)。
