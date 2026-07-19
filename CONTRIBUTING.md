# Contributing to fd-daas-mcp

Thanks for your interest in contributing! This guide gets you set up and covers the workflow.

## Prerequisites

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) (the package manager this repo uses)
- git

## Dev setup

```bash
git clone https://github.com/FindDataOfficial/fd-daas-mcp.git
cd fd-daas-mcp
uv sync --extra dev          # installs the package (editable) + dev deps (pytest, mkdocs, twine)
cp .env.example .env       # then edit .env with your real values
```

The package uses **src-layout** (`src/fd_daas_mcp/`). `uv sync` installs it
editable, so `fd_daas_mcp` is importable from the `.venv` without further
setup.

## Running the server / CLI

```bash
uv run fd-daas-mcp --help                 # CLI help
uv run python -m fd_daas_mcp.server       # start the MCP stdio server (schema auto-creates)
./bin/fd-daas-mcp-server                  # self-locating launcher (prefers .venv)
```

To point Claude Code (or any MCP client) at the local server, copy
`examples/.mcp.json` to your project root.

## Tests

```bash
uv run pytest                              # full suite
uv run pytest tests/test_alert_tools.py    # one file
uv run pytest -k alert                     # by keyword
```

The suite is offline - no network, no live MCP transport. Run via
`uv run pytest`, not `python -m pytest` directly (the latter won't pick up the
editable install and the `addopts` plugin suppression).

## Selfcheck

```bash
uv run python -m fd_daas_mcp.selfcheck
```

Verifies registry invariants: tool count across core groups, known collisions
are namespaced, leaf-module isolation, no APScheduler thread (cron suppression),
and the registration report has no core-group failure. The same invariants run
as a pytest assertion in `tests/test_selfcheck.py`.

## Docs

The docs site is MkDocs Material under `docs-site/`:

```bash
uv run mkdocs serve --config-file docs-site/mkdocs.yml    # live preview
uv run mkdocs build --strict --config-file docs-site/mkdocs.yml   # CI-equivalent build
```

Docs deploy automatically to GitHub Pages on push to `master` via
`.github/workflows/docs.yml`.

## Code style

- Match the surrounding style. The codebase uses `from __future__ import
  annotations` and PEP 604 unions (`X | None`).
- Keep tool-group source under `src/fd_daas_mcp/mcp/<group>/`. The registry
  discovers tools by AST-harvesting each group's `server.py` - new tools don't
  need manual registration.
- No new dependencies without justification. Optional deps go under
  `[project.optional-dependencies]` and are lazy-imported so a missing extra
  degrades to a per-feature error, never a startup crash.

## Pull requests

- Branch from `master`, name it `<topic>-<short-description>` (e.g.
  `fix-cron-timezone`).
- One logical change per PR.
- Run `uv run pytest` and `uv run python -m fd_daas_mcp.selfcheck` before
  pushing - CI runs the same checks.
- If you change user-visible behavior, update `CHANGELOG.md` and the relevant
  docs page.
- Commit messages: imperative mood, short subject line. Reference issues in the
  body (`Fixes #123`).

## Reporting issues

Use the [issue templates](.github/ISSUE_TEMPLATE/). Include:
- `fd-daas-mcp --version` output
- The tool group(s) involved (alerts, cron, daas, etc.)
- The exact command or `.mcp.json` config
- What you expected vs. what happened

## Releasing

Releases are cut by maintainers. The flow: bump version in `pyproject.toml` +
`CHANGELOG.md`, tag `vX.Y.Z`, push the tag - `.github/workflows/publish.yml`
builds and publishes to PyPI automatically.

## License

By contributing you agree your contributions are licensed under the project's
[MIT license](LICENSE).
