# Deploy the Docs

This site (`docs-site/`) is built with MkDocs Material and deployed to GitHub
Pages. This page covers Pages setup, local/WiFi serving, and tunnel publishing.

## Prerequisites

`mkdocs-material` is in the `dev` dependency group in `pyproject.toml`, so
`uv sync` installs it. Verify:

```bash
uv run mkdocs --version
```

## Local serve (write/preview)

```bash
uv run mkdocs serve               # http://127.0.0.1:8000
```

Live reload on every save. Use `uv run mkdocs build --strict` before committing
to catch broken links.

## GitHub Pages deployment

### One-time repo setup

1. Push the repo to GitHub.
2. In the repo: **Settings -> Pages -> Build and deployment -> Source:
   GitHub Actions**.
3. Add the workflow `.github/workflows/docs.yml` (see below).

### The workflow

`.github/workflows/docs.yml` builds on push to `master` (and on manual dispatch)
and publishes the static site to Pages:

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

After the first green run, the site is live at the Pages URL in
`mkdocs.yml` (`site_url`).

## Share over WiFi / LAN

Bind the dev server to all interfaces so other devices on the same WiFi can
browse:

```bash
uv run mkdocs serve --dev-addr 0.0.0.0:8000
# others browse http://<your-LAN-IP>:8000
```

Find your LAN IP: `ipconfig getifaddr en0` (macOS) or `hostname -I` (Linux).

## Share over a public tunnel

For access outside your LAN, front the local port with a tunnel skill:

```bash
# bore (fd-coding-bore-tunnel)
uv run python -m bore local 8000 --to bore.pub

# cloudflare (fd-coding-cloudflare-tunnel)
cloudflared tunnel --url http://localhost:8000
```

See [Sharing Dashboards](../skills/sharing.md).

## Add a page

Use `fd-coding-documents-add`, or manually: drop a markdown file under the right
role directory, wire it into `mkdocs.yml` `nav`, run
`uv run mkdocs build --strict`. See the on-disk `docs-site/README.md` and
`docs-site/references/docs-site-conventions.md` for the full conventions.
