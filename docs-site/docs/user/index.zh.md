# 用户指南

本指南面向**普通用户** -- 想获取数据、计算指标、构建集合、做研究、分享看板的人。你不需要写代码或修改项目。

## DAAS 提供什么

DAAS 是一个本地数据平台。开箱即用：

- **约 5,600 个实体** -- 5,575 只股票 + 60 个国家，每个都可关联到其数据源标识符。
- **数百条预置指标规则**（随着你接入数据源可扩展到上千条）-- 均线、RSI、滚动波动率、涨跌幅、z-score 以及宏观/经济序列。
- **8 个 MCP 工具组**（alerts、cron、composite、daas、dashboard、leader、pdf、research），用于浏览、调度、告警和编排。
- **40+ 技能**，封装常见工作流（获取、研究、看板、集合、PDF 搜索、网页抓取）。

## 如何与 DAAS 交互

有两条一等公民路径，按场景选用：

1. **技能**（推荐新手）-- 在 Claude Code 里，直接描述你要什么（"获取 AAPL 日线并加一条 20 日均线"）。对应技能会解析实体、调用 Python 库、持久化到 `daas.db`。见 [5 分钟首次获取](first-fetch.md)。
2. **MCP 服务器** -- 如果你的客户端支持 MCP，把它指向 `fd-daas-mcp`（`.mcp.json` 的唯一条目），直接调用 `<group>_<tool>` 工具。见 [MCP 工具](../mcp/index.md)。

两条路径共享同一个 `daas.db`，所以一条路径的产出对另一条立即可见。

## 推荐阅读顺序

1. [安装与部署](install.md) -- 把项目跑起来。
2. [5 分钟首次获取](first-fetch.md) -- 你的第一次真实获取 + 指标。
3. [示例](../examples/index.md) -- 七个典型工作流。
4. [概念](../concepts/entities.md) -- 理解实体、集合、指标。
5. [技能](../skills/index.md) -- 官方技能家族。

## 你会遇到的概念

- **实体（Entity）** -- 一只股票或一个国家（如 AAPL、CN）。见 [实体](../concepts/entities.md)。
- **数据源（Datasource）** -- 数据来源（akshare、yfinance、edgar……）。
- **指标规则（Indicator rule）** -- 一个把序列计算出来写入 `observations` 表的绑定（如 `SPY_ma5` = SPY 收盘价的 5 日均线）。
- **集合（Collection）** -- 实体或指标的命名分组。见 [集合与指标](../concepts/collections.md)。
- **研究（Research）** -- 一份持久化研究包，把实体集合、指标集合、看板、流水线与一份 Markdown 报告绑在一起。

!!! note "无需写代码"
    只要你能用自然语言描述需求，技能就能完成。示例里用了真实命令，方便你直接复制。
