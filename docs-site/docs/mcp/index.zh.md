# MCP 工具

DAAS 提供一个统一的 MCP 服务器 -- **`fd-daas-mcp`** -- 作为仓库根 `.mcp.json` 的唯一条目。它在一个 stdio 服务器和一个 `fd-daas-mcp` Click CLI 背后托管 **8 个工具组**。工具注册为 **`<group>_<tool>`**（如 `daas_search_entities`、`research_create`、`pdf_ingest_document`）。

## 为什么是一个服务器

服务器和 CLI 都消费 `daas/fd_daas_mcp/registry.py`（`registry.build()`），所以两个表面不会漂移。每个组的工具代码位于 `fd-daas-mcp/<group>-mcp/`；薄薄一层合并层是 `fd-daas-mcp/daas/fd_daas_mcp/`（`server.py` / `registry.py` / `cli.py` / `selfcheck.py`）。

## 启动

`.mcp.json` 把 `command` 指向 `fd-daas-mcp/bin/fd-daas-mcp-server`，一个自定位 POSIX shell 脚本，设置 `PYTHONPATH` 并 exec `.venv/bin/python -m daas.fd_daas_mcp.server`。

```bash
fd-daas-mcp/bin/fd-daas-mcp-server             # 启动服务器
fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck   # 离线不变量
```

## 8 个组

| 组 | 前缀 | 覆盖 |
| --- | --- | --- |
| `daas` | `daas_*` | 实体/数据源/指标/目录浏览、集合、规则、计算。 |
| `research` | `research_*` | 研究包 创建/获取/列表/更新/删除/刷新/报告 + 组件。 |
| `dashboard` | `dashboard_*` | 独立 HTML 看板注册 CRUD + 索引重建。 |
| `cron` | `cron_*` | 库存任务 + 调度 + 执行历史。 |
| `alerts` | `alerts_*` | `observations`/`scraw_*` 上的告警规则、渠道、序列、事件。 |
| `leader` | `leader_*` | CrewAI DataCrew + 专家 agent + 工作流 + 注册表。 |
| `pdf` | `pdf_*` | 本地 PDF/文本向量搜索（sqlite-vec）。可选 -- 取决于 `sqlite-vec`。 |
| `composite` | `composite_*` | 组合多个上游 MCP 服务器 + 链式工具流水线。 |

每组工具列表见 [工具组](groups.md)。

!!! note "技能 vs. MCP"
    技能与 MCP 工具共享一个 `daas.db`。技能更简单/离线；MCP 服务器更丰富（调度、告警、编排、搜索）。任选其一。

## 未移除

`cron` / `alerts` / `leader` / `composite` 组**未**移除 -- 它们以 `<group>_<tool>` 形式折进 `fd-daas-mcp`。已丢弃的 `scrapling` / `firecrawl` / `massive` MCP 组和每源 `mcp__*` 工具已不存在；不要引用。
