# 分享看板

DAAS 看板是注册在 `dashboards` 表里的独立 HTML 文件。本示例展示如何构建一个并通过 **WiFi/局域网** 或 **公网隧道** 分享。

## 1. 构建看板

**技能：** `fd-daas-dashboard-creator` 技能从你的数据构建独立 HTML 看板并注册：

> 为 `momentum` 指标集合做一个看板，注册为 `my-momentum`。

它把 HTML 写到仓库根目录 `dashboards/`，并在 `dashboards` 表写一行（slug、名称、source_tables、chart_config、file_path、file_url），然后重建 `dashboards/index.html` + `daas.md`。

**MCP：**

```text
dashboard_register(slug="my-momentum",
                   name="Momentum Dashboard",
                   intro="RSI + MA signals for my watchlist",
                   source_tables=["observations"],
                   refresh_cadence="daily",
                   file_path="dashboards/my-momentum/index.html",
                   file_url="/dashboards/my-momentum/index.html")
```

**浏览：** `dashboard_list()` / `dashboard_search(keyword="momentum")`。

## 2. 通过 WiFi/局域网分享

把 `dashboards/` 目录（或本文档站）在局域网发布，同 WiFi 下任何人都能打开。

```bash
# 方式 1：Python 内置静态服务器
cd dashboards && python3 -m http.server 8000 --bind 0.0.0.0

# 方式 2：同时服务本文档站
uv run mkdocs serve --dev-addr 0.0.0.0:8000
```

然后从同 WiFi 的另一台设备访问：

```text
http://<本机局域网IP>:8000
```

查本机局域网 IP：`ipconfig getifaddr en0`（macOS）或 `hostname -I`（Linux）。

!!! warning "WiFi 分享仅限本地"
    设备必须在同一网络。要让局域网外访问，用隧道（见下）。

## 3. 通过公网隧道分享

用某个隧道技能把本地端口暴露到公网：

**`fd-coding-bore-tunnel`**（bore -- 简单、快速）：

```bash
# 暴露本地 8000 端口 -> 给你一个公网 bore.pub URL
uv run python -m bore local 8000 --to bore.pub
```

**`fd-coding-cloudflare-tunnel`**（Cloudflare -- 通过 `cloudflared` 快速隧道，无需装客户端）：

```bash
cloudflared tunnel --url http://localhost:8000
```

两者都会给你一个可发给任何人的公网 URL。完整技能走查见 [分享看板](../skills/sharing.md)。

## 4. 刷新数据

看板从 `daas.db` 读取，所以刷新 = 重算底层指标（若看板属于一个研究，用 `research_refresh`）。HTML 不变；数据在下次渲染时更新。

## 下一步

- 完整分享技能文档：[分享看板](../skills/sharing.md)。
- 看板技能文档：[fd-daas-dashboard](../skills/dashboard.md)。
