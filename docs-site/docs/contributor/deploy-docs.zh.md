# 部署文档站

本站（`docs-site/`）用 MkDocs Material 构建，部署到 GitHub Pages。本页讲 Pages 设置、本地/WiFi 服务、隧道发布。

## 前置条件

`mkdocs-material` 在 `pyproject.toml` 的 `dev` 依赖组里，`uv sync` 会装。验证：

```bash
uv run mkdocs --version
```

## 本地服务（写/预览）

```bash
uv run mkdocs serve               # http://127.0.0.1:8000
```

每次保存热重载。提交前用 `uv run mkdocs build --strict` 抓断链。

## GitHub Pages 部署

### 一次性仓库设置

1. 把仓库推到 GitHub。
2. 在仓库：**Settings -> Pages -> Build and deployment -> Source: GitHub Actions**。
3. 加工作流 `.github/workflows/docs.yml`（见下）。

### 工作流

`.github/workflows/docs.yml` 在 push 到 `master`（及手动触发）时构建并把静态站发布到 Pages：

```yaml
name: docs
on:
  push:
    branches: [master]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv
      - run: uv sync
      - run: uv run mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with: { path: docs-site/site }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

首次绿之后，站点上线于 `mkdocs.yml` 的 `site_url`。

## 通过 WiFi/局域网分享

把开发服务器绑到所有接口，同 WiFi 下其他设备可浏览：

```bash
uv run mkdocs serve --dev-addr 0.0.0.0:8000
# 其他人访问 http://<你的局域网IP>:8000
```

查局域网 IP：`ipconfig getifaddr en0`（macOS）或 `hostname -I`（Linux）。

## 通过公网隧道分享

要让局域网外访问，用隧道技能前置本地端口：

```bash
# bore（fd-coding-bore-tunnel）
uv run python -m bore local 8000 --to bore.pub

# cloudflare（fd-coding-cloudflare-tunnel）
cloudflared tunnel --url http://localhost:8000
```

见 [分享看板](../skills/sharing.md)。

## 加一页

用 `fd-coding-documents-add`，或手工：把 markdown 文件放到正确角色目录，在 `mkdocs.yml` `nav` 接线，跑 `uv run mkdocs build --strict`。见磁盘上的 `docs-site/README.md` 与 `docs-site/references/docs-site-conventions.md`。
