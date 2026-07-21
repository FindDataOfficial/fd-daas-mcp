# Changelog

All notable changes to **fd-daas-mcp** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-07-21

First-run database bootstrap - zero-config from `pip install` to a working,
queryable database.

### Added

- **`fd-daas-mcp init`** - provisions the database (creates the file + full
  schema via `Base.metadata.create_all` + every group's idempotent `init_db()`)
  and seeds a dep-free starter catalog of `sources` (`akshare`, `yfinance`,
  `worldbank`, `edgar`, all `enabled=False`). Idempotent; re-running is a no-op.
  Flags: `--db-url`, `--seed`/`--no-seed`, `--json`.
- **`fd-daas-mcp doctor`** - read-only diagnostic (resolved DB path, file
  existence, schema state, row counts, missing optional extras). Never creates
  or writes the DB. Exits 0 when healthy, non-zero with a pointer to `init`
  when not.
- **Writable default DB path** - with `DAAS_DATABASE_URL` unset, the database
  resolves to `<cwd>/daas.db` (writable cwd) or `~/.fd-daas-mcp/daas.db`
  (read-only cwd fallback), never inside the installed package (read-only
  under `pip install`). `DAAS_DATABASE_URL` is now optional.
- **Eager provisioning + path logging on server start** - the server
  provisions the schema before any tool registers and logs the resolved DB
  path at INFO.
- **Selfcheck invariant** - asserts the default DB path never resolves inside
  the installed package.

### Changed

- `DAAS_DATABASE_URL` is now optional (was effectively required for a clean
  first run). The in-package `mcp/daas.db` default is dropped.

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
