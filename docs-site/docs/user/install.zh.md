# 安装与部署

DAAS 本地运行，使用 **uv** 和 Python 3.10+。所有读写都针对仓库根目录的一个 SQLite 文件（`daas.db`）。

## 1. 克隆并安装

```bash
git clone https://github.com/FindDataTechnology/fd-daas-mcp.git
cd DAAS
uv sync            # 配置根 venv（数据库 + mkdocs-material）
```

`uv sync` 会安装运行时依赖（`akshare`、`yfinance`、`edgar`、`edinet-tools`、`world_bank_data`、`ckanapi`）和 `dev` 组（包含本站的 `mkdocs-material`）。

!!! note "Python 版本"
    根 venv 是 Python 3.10+。`dartlab` 数据源需要 3.12 -- 用 `uv run --python 3.12 --with dartlab ...` 临时运行（它不是根依赖）。

## 2. 配置 `.env`

复制模板，只填你用到的 key：

```bash
cp .env.example .env   # 若有模板；否则新建 .env
```

仓库根目录的单一 `.env` 包含：

| 键 | 用途 |
| --- | --- |
| `DAAS_DATABASE_URL` | `sqlite:///daas.db`（仓库根目录的 DB）。 |
| `HTTP_PROXY` | 出站代理（网络需要时）。 |
| `EDGAR_IDENTITY` | 你的 SEC EDGAR user agent。 |
| `EDINET_API_KEY` | 日本 EDINET API key。 |
| `ALERTS_FEISHU_WEBHOOK_URL` | 用于告警投递的飞书 webhook。 |
| `LLM_*` / `LEADER_MODEL*` | Gateway/workflow agent 模型配置。 |
| `DASHBOARD_PORT` | 看板服务器端口。 |
| `CKAN_PORTAL_URL` | CKAN portal 基础 URL。 |

!!! warning "切勿提交真实密钥"
    `.env` 已被 git 忽略。本站示例用占位符如 `<YOUR_API_KEY>` -- 切勿把真实 key 粘进文档或提交。

## 3. 启动 MCP 服务器

统一的 `fd-daas-mcp` 服务器是仓库根 `.mcp.json` 的唯一条目。Claude Code 会自动识别。手动启动（测试或其他 MCP 客户端）：

```bash
fd-daas-mcp/bin/fd-daas-mcp-server        # .mcp.json 的 `command`
```

## 4. 自检

运行离线不变量检查，确认服务器接线正确：

```bash
fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck
```

## 5. 直接查询 `daas.db`

从仓库根目录，规范 DB 是 `daas.db`（不是 `mcp/daas.db`）：

```bash
sqlite3 daas.db "SELECT count(*) FROM entities;"
sqlite3 daas.db "SELECT name, op, indicator_name FROM indicator_rules LIMIT 5;"
```

需要 FK 级联时用 `PRAGMA foreign_keys=ON;`。

## 6.（可选）本地启动文档站

```bash
uv run mkdocs serve               # http://127.0.0.1:8000
```

GitHub Pages 部署与 WiFi/隧道分享见 [贡献者指南 -> 部署文档站](../contributor/deploy-docs.md)。

## 下一步

继续 [5 分钟首次获取](first-fetch.md)。
