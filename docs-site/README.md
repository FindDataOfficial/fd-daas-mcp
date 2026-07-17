# DAAS docs-site

The navigable documentation site for the DAAS project, built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

- **Sources:** `docs/` (markdown)
- **Config:** `mkdocs.yml`
- **Conventions:** [`references/docs-site-conventions.md`](references/docs-site-conventions.md)

## Build & serve

```bash
uv sync                       # installs mkdocs-material (dev group)
uv run mkdocs build           # build static site -> site/ (git-ignored)
uv run mkdocs serve           # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict  # strict check (broken links fail)
```

## Share over WiFi / LAN

```bash
uv run mkdocs serve --dev-addr 0.0.0.0:8000
# then browse http://<this-machine-LAN-IP>:8000 from another device
```

For a public URL, front the local port with `fd-coding-bore-tunnel` or
`fd-coding-cloudflare-tunnel` (see the Contributor Guide -> Deploy the Docs).

## Deploy to GitHub Pages

Pushing to `master` triggers `.github/workflows/docs.yml`, which builds and
publishes the site to GitHub Pages. One-time setup: repo **Settings -> Pages ->
Source: GitHub Actions**.

## Add a page

Use the `fd-coding-documents-add` skill, or manually: drop a markdown file under
the right role directory (`docs/user/`, `docs/contributor/`, `docs/examples/`,
`docs/skills/`, `docs/mcp/`, `docs/concepts/`), wire it into `mkdocs.yml` `nav`,
and run `uv run mkdocs build --strict`.

## Scaffold a new docs-site like this one

Use the `fd-coding-documents-builder` skill.
