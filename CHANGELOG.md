# Changelog

All notable changes to **fd-daas-mcp** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-20

Initial public release. Carves the consolidated DAAS MCP server + CLI out of
the private working monorepo into a standalone, PyPI-installable package.

### Shipped

- **Package** (`fd_daas_mcp`): src-layout, one stdio FastMCP server + one Click
  CLI, both driven by `registry.py` (~187 tools across 8 groups).
- **Tool groups**: `alerts`, `cron`, `composite`, `daas`, `dashboard`,
  `leader`, `pdf` (optional, gated on `sqlite-vec`), `research`. Source lives
  at `src/fd_daas_mcp/mcp/<group>/` and ships as package data.
- **Vendored schema**: the former `mcp-models` package is now
  `fd_daas_mcp.models` (single module, vendored) - no local-path dependency,
  the wheel builds clean on PyPI.
- **CLI**: `fd-daas-mcp` console script with `<group> <tool>` invocation, a
  REPL (with the `repl` extra), and `create_all` for schema bootstrap.
- **Skills** (15): `fd-daas-based-data-fetch`, `fd-daas-brainstorm`,
  `fd-daas-dashboard`, `fd-daas-dashboard-creator`, `fd-daas-entities-collection`,
  `fd-daas-entities-collection-creator`, `fd-daas-fetch-data`,
  `fd-daas-indicators-collection-creator`, `fd-daas-indicators-creator`,
  `fd-daas-pdf`, `fd-daas-research`, `fd-daas-rules-creator`,
  `fd-daas-scrapling-official`, `fd-daas-skill-creator`, `fd-daas-skill-review`.
  At `skills/` in the repo root (not installed by `pip install` - clone the repo
  to use them with Claude Code).
- **Docs site**: MkDocs Material at `docs-site/`, deployed to
  https://finddataofficial.github.io/fd-daas-mcp/ (en + zh).
- **CI**: `docs.yml` (Pages deploy), `tests.yml` (pytest on PR),
  `publish.yml` (PyPI on tag).
- **Repo standards**: `LICENSE` (MIT), `CONTRIBUTING.md`, `.env.example`,
  issue templates.

### Deferred (not in v0.1)

- The 9 `fd-coding-*` skills and `fd-datasource-akshare` (internal developer
  tools) - may ship in a later release.
- An automated `fd-daas-mcp install-skills` command (for now, skills are
  consumed by cloning the repo; see `CONTRIBUTING.md`).
- CI matrix testing across Python versions (v0.1 targets 3.12 only).
- Old-repo cleanup decision (the prior `FindDataOfficial/DAAS` monorepo is
  untouched by this release).

### Breaking (vs. the private monorepo's internal layout)

- Import paths changed: `from models import X` -> `from fd_daas_mcp.models
  import X`; `from daas.fd_daas_mcp.X` -> `from fd_daas_mcp.X`. Only affects
  code inside the old private repo; there were no external consumers.
- `mcp-models` is no longer a separate package - it's vendored into
  `fd_daas_mcp.models`.
