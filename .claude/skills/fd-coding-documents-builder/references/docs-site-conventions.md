# docs-site conventions (for fd-coding-documents-builder / -add)

The shared rules every DAAS docs-site (`docs-site/`) and the
`fd-coding-documents-builder` / `fd-coding-documents-add` skills must follow.
Source of truth: repo-root `CLAUDE.md`, the `daas-concepts.md` reference in
`fd-daas-skill-creator`, and the live repo. Inject these as guardrails; do not
copy them verbatim into generated pages.

## 1. Location & generator

- The docs site lives at repo-root **`docs-site/`**, built with **MkDocs
  Material**. Config: `docs-site/mkdocs.yml`. Markdown sources: `docs-site/docs/`.
- `mkdocs-material` is declared in the `dev` dependency group in `pyproject.toml`
  (installed by `uv sync`).
- Build: `uv run mkdocs build` (output: `docs-site/site/`, git-ignored).
- Serve: `uv run mkdocs serve` (local) or `--dev-addr 0.0.0.0:<port>` (LAN/WiFi).
- The built `docs-site/site/` directory is **never committed** (`.gitignore`).

## 1a. Internationalization (i18n)

The site is **bilingual** (中文 default + English) via the `mkdocs-static-i18n`
plugin (declared in the `dev` dependency group). Convention:

- **Suffix layout**: each page has two files - `page.zh.md` (default) and
  `page.en.md` - side by side in the same directory. Missing translations fall
  back to the default language automatically.
- **`nav` uses the untranslated base path** (`user/index.md`, not
  `user/index.zh.md`); the plugin resolves the per-locale file at build time.
- **Nav labels** are declared in English under `nav:` and translated per-locale
  via the plugin's `nav_translations:` map on the `zh` locale entry.
- **Default locale**: `zh` (`default: true`). English is served under `/en/`.
- **Theme language**: `theme.language: zh` so Material's own strings match the
  default. The plugin swaps to `en` for the English build.

When adding a new page (via `fd-coding-documents-add` or manually), create
both `page.zh.md` and `page.en.md`. If only one is provided, the site still
builds (fallback to the default), but the language selector will land the
reader on the fallback for that URL.

## 2. Role-based navigation (nav)

`mkdocs.yml` `nav` MUST have these top-level sections, in this order:

| Section | Directory | Audience |
| --- | --- | --- |
| User Guide | `docs/user/` | normal users |
| Examples | `docs/examples/` | normal users |
| Concepts | `docs/concepts/` | everyone |
| Skills | `docs/skills/` | everyone |
| MCP Tools | `docs/mcp/` | everyone |
| Contributor Guide | `docs/contributor/` | contributors |
| Roadmap | `docs/roadmap.md` | everyone |

Placement rule: a page a normal user needs goes to `docs/user/` or
`docs/examples/`. A page only a contributor needs goes to `docs/contributor/`.
When adding a page, place it under the role directory that matches its section
and wire it into `nav` under the matching top-level entry.

## 3. Frontmatter & page rules

- Every page starts with a single H1 (`# Title`) matching its nav label.
- Use MkDocs Material admonitions (`!!! note`, `!!! tip`, `!!! warning`) for
  callouts; fenced code blocks with language tags for commands.
- Internal links are relative (`../concepts/entities.md`), never absolute paths.
- Every `nav` entry MUST point to an existing file - `mkdocs build --strict`
  fails on dangling nav links.

## 4. Live-surface check (no removed surfaces)

Every page MUST reference only live skills, MCP groups, CLI commands, and
`daas.db` tables. DO NOT reference (these are removed/stale):

- Removed CLIs: `fd-akshare` / `fd-yfinance` / `fd-dartlab` / `fd-edgar` /
  `fd-edinet` / `fd-world`.
- Removed skills/groups: `fd-daas-workflow-creator`, `fd-daas-scraw-scrapling`,
  `fd-daas-scrapling-scraw-creator`, `fd-daas-cli-datasource-entities-builder`,
  the per-source `mcp__*` tools, and the `scrapling` / `firecrawl` / `massive`
  MCP groups.
- Old DB URLs (`mcp/daas.db`) - the canonical DB is the repo-root `daas.db`.

The live MCP server is the consolidated **`fd-daas-mcp`** (sole `.mcp.json`
entry) with 8 tool groups registering as `<group>_<tool>`: `alerts`, `cron`,
`composite`, `daas`, `dashboard`, `leader`, `pdf`, `research`.

## 5. No secrets

Pages MUST NOT embed `.env` values (`EDINET_API_KEY`, `ALERTS_FEISHU_WEBHOOK_URL`,
`LLM_*`, `LEADER_MODEL*`, `EDGAR_IDENTITY`, etc.). Use placeholders like
`<YOUR_API_KEY>`. Examples show `.env` keys by name only.

## 6. Strict build

After scaffold or after adding any page, run:

```bash
uv run mkdocs build --strict
```

A passing strict build is the acceptance gate: broken internal links, missing
nav targets, and unresolved includes fail it. The `fd-coding-documents-add`
skill runs this after every insertion and rolls back the file/nav change on
failure.

## 7. Deploy

- GitHub Pages via `.github/workflows/docs.yml`: on push to `master` (and manual
  dispatch), `uv run mkdocs build` then `actions/deploy-pages`.
- One-time repo setup: Settings -> Pages -> Source: **GitHub Actions**.
- Local/WiFi share: `uv run mkdocs serve --dev-addr 0.0.0.0:8000`.
- Public tunnel: front the local port with `fd-coding-bore-tunnel` or
  `fd-coding-cloudflare-tunnel`.

## 8. Relationship to daas-doc/ and README.md

- The docs site is a **navigable site**, distinct from `daas-doc/` (skill-
  generated markdown artifacts) and the repo-root `README.md` (verified
  quickstart, governed by the `project-readme` spec).
- Link to `daas-doc/` artifacts (e.g. a research plan) by relative path; do not
  duplicate their content.
- The repo-root `README.md` links to the docs site; the docs site does not
  re-host the README's quickstart verbatim.
