# 分享看板

两个 `fd-coding-*` 技能把本地服务（一个看板或本文档站）暴露到公网。当你要把 `localhost` 上跑的东西分享给 WiFi 外的人时用。

## fd-coding-bore-tunnel（bore）

通过 [bore](https://github.com/ekzhang/bore) 和 `bore.pub` 的简单、快速隧道。

**触发：** "内网穿透"、"外网访问"、"expose local service"、"share over the internet"。

**典型用法：**

```bash
# 在本地 8000 端口提供看板（或文档）
cd dashboards && python3 -m http.server 8000 --bind 0.0.0.0
# (或) uv run mkdocs serve --dev-addr 0.0.0.0:8000

# 通过 bore 暴露 -> 打印一个公网 bore.pub URL
uv run python -m bore local 8000 --to bore.pub
```

技能管理隧道的启停。

## fd-coding-cloudflare-tunnel（cloudflared）

通过 Cloudflare（`cloudflared`）的 HTTPS 隧道 -- 快速隧道无需装客户端。

**触发：** "内网穿透"、"外网访问"、"expose local service over HTTPS"。

**典型用法：**

```bash
cloudflared tunnel --url http://localhost:8000
# -> 打印一个公网 https://<random>.trycloudflare.com URL
```

## 用哪个

| 需求 | 选择 |
| --- | --- |
| 快速、免账号、HTTP 或 TCP | `fd-coding-bore-tunnel` |
| HTTPS、Cloudflare 托管、稳定主机名 | `fd-coding-cloudflare-tunnel` |

## 仅 WiFi/局域网分享（无隧道）

若所有人都在同 WiFi，不需要隧道 -- 绑定到 `0.0.0.0` 即可：

```bash
uv run mkdocs serve --dev-addr 0.0.0.0:8000
# 其他人访问 http://<你的局域网IP>:8000
```

完整走查见 [分享看板](../examples/share-dashboard.md)。

## 安全提示

隧道会把你的本地服务发布到公网。只暴露你打算分享的东西，内容敏感时不要让隧道无人值守地运行。看板从 `daas.db` 读取 -- 它会暴露你已获取的数据。
