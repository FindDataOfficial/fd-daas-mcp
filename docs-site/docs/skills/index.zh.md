# 技能

DAAS 技能位于 `.claude/skills/`，由 Claude Code 调用。它们直接调用 Python 数据库并通过 `sqlite3` 读写 `daas.db` -- 无 MCP 往返。分两个家族。

## `fd-daas-*` -- 数据技能

获取、指标、集合、研究、看板等技能。

| 技能 | 做什么 |
| --- | --- |
| [`fd-daas-brainstorm`](brainstorm.md) | 把模糊的研究目标澄清成一份计划文档。 |
| [`fd-daas-research`](research.md) | 全流程：分析 -> 集合 -> 指标 -> 看板 -> 研究包 + 报告。 |
| `fd-daas-based-data-fetch` | 核心解析 -> 获取 -> 持久化。 |
| `fd-daas-fetch-data` | 实体 -> 覆盖 -> 指标工作流。 |
| `fd-daas-dashboard` / [`-creator`](dashboard.md) | 浏览 / 构建独立 HTML 看板。 |
| `fd-daas-entities-collection` / `-creator` | 实体集合 + 规则。 |
| `fd-daas-indicators-collection-creator` | 指标集合 + 导出。 |
| `fd-daas-indicators-creator` | 把序列持久化到 `scraw_<slug>`。 |
| `fd-daas-rules-creator` | 编写统一规则（json/script/position/llm）。 |
| `fd-daas-pdf` | 本地 PDF/文本语义向量搜索。 |
| `fd-daas-scrapling-official` | 带反爬绕过的网页抓取（Scrapling 库）。 |
| `fd-datasource-akshare` | 通过外部 `scraw-akshare` Scrapy 项目获取 A 股 OHLCV/基本面。 |
| `fd-daas-skill-creator` / `fd-daas-skill-review` | 创建/检视 + 审查 daas 技能。 |

## `fd-coding-*` -- 基础设施与构建技能

| 技能 | 做什么 |
| --- | --- |
| [`fd-coding-bore-tunnel`](sharing.md) / [`fd-coding-cloudflare-tunnel`](sharing.md) | 把本地服务（看板/文档）暴露到公网。 |
| `fd-coding-skill-creator` | 通用技能创建循环（草稿 -> 评测 -> 迭代）。 |
| `fd-coding-daas-datasource-builder`（+ `-workspace`） | 搭建数据源构建项目。 |
| `fd-coding-daas-scraw-builder` | 搭建 `scraw-*` Scrapy 项目。 |
| `fd-coding-daas-reset-project` | 把 `daas.db` 在 3 个受保护级别上重置。 |
| `fd-coding-documents-builder` | 搭建 MkDocs Material 文档站（如本站）。 |
| `fd-coding-documents-add` | 给已有文档站加一页。 |

## 重点技能

若只学四个技能，学这些 -- 它们覆盖最常见的端到端旅程：

1. [**fd-daas-brainstorm**](brainstorm.md) -- 把模糊想法变成计划。
2. [**fd-daas-research**](research.md) -- 跑完整研究。
3. [**fd-daas-dashboard**](dashboard.md) -- 查看与构建看板。
4. [**分享看板**](sharing.md) -- 通过 WiFi/隧道发布。

!!! tip "技能 vs. MCP"
    技能是更简单、离线友好的路径。同样能力也作为 MCP 工具（`<group>_<tool>`）在统一 `fd-daas-mcp` 服务器上提供 -- 见 [MCP 工具](../mcp/index.md)。
