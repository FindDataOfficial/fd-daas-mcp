# 贡献者指南

面向扩展 DAAS 的人 -- 添加技能、数据源、MCP 工具，或做文档。普通用户指南在[这里](../user/index.md)。

## 一段话架构

数据获取是**技能驱动**：技能直接调用 Python 数据库（`akshare`、`yfinance`、`edgar`、`edinet-tools`、`dartlab`、`world_bank_data`、`ckanapi`）并通过 `sqlite3` 读写 `daas.db`。统一的 **`fd-daas-mcp`** MCP 服务器是 `.mcp.json` 的唯一条目 -- 它在一个 stdio 服务器和一个 Click CLI 背后托管 9 个工具组（`alerts`/`cron`/`composite`/`daas`/`dashboard`/`gateway`/`workflow`/`pdf`/`research`）。薄合并层是 `fd-daas-mcp/daas/fd_daas_mcp/`（`server.py`/`registry.py`/`cli.py`/`selfcheck.py`）；每个组的工具代码位于 `fd-daas-mcp/<group>-mcp/`。服务器和 CLI 都消费 `registry.build()`，所以表面不会漂移。

## 仓库布局

```
DAAS/
  .claude/skills/        # fd-daas-* 与 fd-coding-* 技能
  .mcp.json              # 唯一条目：fd-daas-mcp
  daas.db                # 仓库根目录的 git 跟踪 SQLite（注册表 + 数据）
  .env                   # 单一 env 文件（git 忽略）
  fd-daas-mcp/           # 统一 MCP 服务器 + CLI + 测试
    daas/fd_daas_mcp/    # 合并层（server/registry/cli/selfcheck）
    <group>-mcp/         # 各组工具代码（alerts/cron/composite/.../research）
    bin/fd-daas-mcp-server
    tests/
  dashboards/            # 独立 HTML 看板 + 索引
  daas-doc/              # 技能生成的 markdown（研究计划、简介……）
  docs-site/             # 本 MkDocs Material 站
  construction/          # （过时）建造笔记
  pyproject.toml         # uv 项目 + dev 依赖组（mkdocs-material）
```

## 环境

- **uv** + Python 3.10+（dartlab 需 3.12 -- 用 `uv run --python 3.12 --with dartlab ...`）。
- 仓库根单一 `.env`。脚本自动加载。
- `DAAS_DATABASE_URL=sqlite:///daas.db`（相对路径按仓库根解析）。从仓库根查询：`sqlite3 daas.db "..."`；`PRAGMA foreign_keys=ON`。

## 接下来看哪

- [编写技能](author-skill.md) - 创建新的 `fd-daas-*` / `fd-coding-*` 技能。
- [MCP 测试套件](mcp-tests.md) - 跑服务器测试 + 自检。
- [daas.db 表结构](schema.md) - 表参考。
- [部署文档站](deploy-docs.md) - GitHub Pages + WiFi/隧道分享。

## 已移除表面 -- 不要引用

已移除 CLI：`fd-akshare`/`fd-yfinance`/`fd-dartlab`/`fd-edgar`/`fd-edinet`/`fd-world`。
已移除技能/组：`fd-daas-workflow-creator`、`fd-daas-scraw-scrapling`、`fd-daas-scrapling-scraw-creator`、`fd-daas-cli-datasource-entities-builder`、每源 `mcp__*` 工具、以及 `scrapling`/`firecrawl`/`massive` MCP 组。`cron`/`alerts`/`gateway`/`workflow`/`composite` MCP **未**移除 -- 它们以 `<group>_<tool>` 形式折进 `fd-daas-mcp`。`pdf` 已恢复（可选）。
