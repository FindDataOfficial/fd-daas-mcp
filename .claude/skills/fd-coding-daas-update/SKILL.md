---
name: fd-coding-daas-update
description: Release a new version of fd-daas-mcp to GitHub + PyPI. Use this skill whenever the user wants to publish/release/upload the package - phrases like "upload to github and pypi", "publish fd-daas-mcp", "release a new version", "ship to PyPI", "发版", "上传到 github 和 pypi". The skill drives scripts/release.py: it bumps the version, updates the CHANGELOG, runs the offline tests + selfcheck, builds the sdist+wheel, twine-checks, verifies via a fresh-venv install + `init`/`doctor`, pushes to the default branch on GitHub (FindDataOfficial/fd-daas-mcp), publishes to PyPI using the PYPI_API_KEY from the repo-root `.env` (or `~/.zshrc`, loaded without leaking the value), and verifies the upload is live (PyPI JSON + a real `pip install -U`). PyPI upload is irreversible, so the script is non-mutating by default and requires explicit confirmation before push+publish (`--yes` to skip). It supports a `--testpypi` dry-run (publish to TestPyPI instead of real PyPI) and `--skip-publish` (push GitHub only). Do NOT use this skill to port code from the monorepo into the public repo - that path translation (daas-mcp/ -> src/fd_daas_mcp/mcp/, `from models` -> `from fd_daas_mcp.models`) is a manual prerequisite. Do NOT use it for the private monorepo FindDataOfficial/DAAS (it targets the public package repo at `$FD_DAAS_MCP_PUBLIC_REPO`, defined in the repo-root `.env`).
---

# fd-coding-daas-update

Release a new `fd-daas-mcp` version to GitHub + PyPI, end to end. Drives
`scripts/release.py` - a guarded orchestrator that is **non-mutating by default**
and **requires explicit confirmation** before the irreversible push + PyPI upload.

## Repositories

- **Public package repo** (the release target): `$FD_DAAS_MCP_PUBLIC_REPO`
  (path defined in the repo-root `.env`; defaults to `~/code/fd-daas-mcp-public/`
  if unset, overridable via `--public-repo`)
  - remote `origin` = `https://github.com/FindDataOfficial/fd-daas-mcp.git`
  - default branch: `master` (the script detects it via `gh`)
  - src-layout: `src/fd_daas_mcp/` + `src/fd_daas_mcp/mcp/<group>/`; `models`
    is vendored as `fd_daas_mcp.models` (no local-path dep).
- **Private working monorepo**: the current DAAS repo (repo root, `.`) - the dev
  source. NOT the release target. Changes made here must be **ported** into the
  public repo first (see Prerequisite below).

## Prerequisite: port your changes into the public repo first

The skill does NOT auto-port. The monorepo and the public repo have different
layouts and import conventions, so a raw copy breaks:

| Monorepo path | Public repo path | Import change |
|---|---|---|
| `fd-daas-mcp/daas-mcp/daas_database.py` | `src/fd_daas_mcp/mcp/daas/daas_database.py` | `from models import Base` -> `from fd_daas_mcp.models import Base` |
| `fd-daas-mcp/daas/fd_daas_mcp/cli.py` | `src/fd_daas_mcp/cli.py` | `from daas.fd_daas_mcp import registry` -> `from fd_daas_mcp import registry` |
| `fd-daas-mcp/daas/fd_daas_mcp/server.py` | `src/fd_daas_mcp/server.py` | (same) |
| `fd-daas-mcp/daas/fd_daas_mcp/selfcheck.py` | `src/fd_daas_mcp/selfcheck.py` | (same) |
| `fd-daas-mcp/daas-mcp/<new>.py` | `src/fd_daas_mcp/mcp/daas/<new>.py` | (leaf module, no import change) |

Before invoking this skill, ensure the public repo has the changes you want to
release (ported + working). Run a quick diff to confirm nothing is missing:

```bash
cd "$FD_DAAS_MCP_PUBLIC_REPO" && git status   # should show only what you intend to release
```

> Load `$FD_DAAS_MCP_PUBLIC_REPO` from the repo-root `.env` first:
> `set -a; source .env; set +a` (or pass `--public-repo <path>`).

## Workflow (what the script does)

All steps run from `$FD_DAAS_MCP_PUBLIC_REPO`. Run with no `--yes` for a safe
preview that stops before any irreversible action.

1. **Pre-flight** - verify the public repo exists, `gh` is authed, `uv` is on
   PATH, and a PyPI token (`UV_PUBLISH_TOKEN` / `PYPI_API_KEY` in the repo-root
   `.env` or env, or `PYPI_API_KEY` in `~/.zshrc`) is reachable. Abort early if
   any are missing.
2. **Version** - read the current version from `pyproject.toml`; compute the next
   (`--bump patch|minor|major`, default `patch`, or `--version X.Y.Z` explicit).
   Print old -> new and require confirmation (or `--yes`).
3. **Bump + CHANGELOG** - set `version = "X.Y.Z"` in `pyproject.toml` and insert
   a `## [X.Y.Z] - YYYY-MM-DD` entry under `## [Unreleased]` in `CHANGELOG.md`
   (a stub - fill the bullet list from the git log since the last tag).
4. **Tests + selfcheck** - `uv run pytest` + `uv run python -m fd_daas_mcp.selfcheck`.
   Abort on failure (do not publish a red build).
5. **Build + twine** - `uv build` then `twine check dist/*`. Abort on failure.
6. **Fresh-venv install verify** - create a throwaway venv, `pip install` the
   built wheel (no extras, no src on path), run `fd-daas-mcp init` + `doctor`
   with `DAAS_DATABASE_URL` unset. This proves a real external user gets a
   working DB. Abort on failure.
7. **Confirm** - print the version, the dist files, the target branch, and the
   PyPI target (real or TestPyPI). Require an explicit "yes" (or `--yes`).
8. **Push to GitHub** - commit the version bump + CHANGELOG, fast-forward the
   default branch (`master`) to the new commit, `git push origin HEAD:master`.
9. **Publish to PyPI** - load the token from the repo-root `.env` / env, then
   `~/.zshrc` (the `PYPI_API_KEY` export line, via `eval`-style extraction - the
   value is never printed), set it as `UV_PUBLISH_TOKEN` in the child env (not on
   the CLI, so `ps` can't see it), and run `uv publish dist/*`. With `--testpypi`,
   publish to TestPyPI instead (`--publish-url https://test.pypi.org/legacy/`).
10. **Verify live** - fetch the PyPI JSON (`/pypi/fd-daas-mcp/json`), confirm the
    new version is `latest`, and run a fresh `pip install -U fd-daas-mcp` +
    `init`/`doctor` to prove the published package works.

## Invocation

```bash
# Preview (non-mutating): runs tests + build + fresh-venv verify, then stops
# before push + publish, printing exactly what it would do.
uv run python .claude/skills/fd-coding-daas-update/scripts/release.py

# Real release: patch bump (0.1.1 -> 0.1.2), push GitHub + publish PyPI.
uv run python .claude/skills/fd-coding-daas-update/scripts/release.py --bump patch --yes

# Explicit version
uv run python .claude/skills/fd-coding-daas-update/scripts/release.py --version 0.2.0 --yes

# TestPyPI dry-run (safe - nothing lands on real PyPI)
uv run python .claude/skills/fd-coding-daas-update/scripts/release.py --testpypi --yes

# Push GitHub only, skip PyPI
uv run python .claude/skills/fd-coding-daas-update/scripts/release.py --yes --skip-publish
```

## Safety guarantees (in the script)

- **Non-mutating by default.** Without `--yes`, the script runs every safe
  check (tests, build, fresh-venv verify) and then stops, printing the planned
  push + publish. Nothing is pushed or uploaded.
- **`--yes` required to push/publish.** Even with `--yes`, the publish step
  prints the version + files + target and proceeds only if the pre-flight +
  tests + build + verify all passed.
- **Abort on any failure.** Tests fail, build fails, twine fails, or the
  fresh-venv `init`/`doctor` fails -> the script exits non-zero before any push
  or upload. No red build reaches PyPI.
- **Token never leaks.** `PYPI_API_KEY` / `UV_PUBLISH_TOKEN` is read from the
  repo-root `.env` / env (or `PYPI_API_KEY` in `~/.zshrc`) into the script's
  memory only; it is passed to `uv publish` via the child environment
  (`UV_PUBLISH_TOKEN`), never as a CLI arg (so it's not visible in `ps`) and
  never printed.
- **TestPyPI escape hatch.** `--testpypi` publishes to TestPyPI for a real
  dry-run of the upload + install path without touching real PyPI.
- **No auto-port.** The script will not copy code from the monorepo. If the
  public repo has uncommitted/unported changes you didn't intend, `git status`
  is shown in the pre-flight so you can abort.

## Token setup

The script loads the repo-root `.env` at startup, then looks for a PyPI token in
this order:

1. `UV_PUBLISH_TOKEN` in the current env / `.env` (what `uv publish` reads natively).
2. `PYPI_API_KEY` in the current env / `.env`.
3. `PYPI_API_KEY` exported in `~/.zshrc` (loaded by extracting that one export
   line - the value is never printed).

To set it up once (if not already): add to the repo-root `.env`:

```sh
PYPI_API_KEY=pypi-<your-upload-token-for-fd-daas-mcp>
```

(Or, if you prefer a shell-global token, add `export PYPI_API_KEY=pypi-...` to
`~/.zshrc` - the script falls back to that.)

(Get the token from https://pypi.org/manage/account/token/ - scope it to the
`fd-daas-mcp` project, or an account-scoped upload token.)

## Boundaries

- **Targets the public package repo only** (`$FD_DAAS_MCP_PUBLIC_REPO` -> the
  `FindDataOfficial/fd-daas-mcp` GitHub repo + PyPI `fd-daas-mcp`). It does not
  touch the private monorepo `FindDataOfficial/DAAS`.
- **Does not port code.** Porting monorepo changes into the public repo is a
  manual prerequisite (different layout + import paths). The skill's pre-flight
  shows `git status` so you can confirm the public repo is in the state you want
  to release.
- **Does not tag.** Pushing a `v*` tag would trigger `.github/workflows/publish.yml`
  (CI re-publish), which races with the manual `uv publish`. Tag manually
  afterward if you want a GitHub release marker - expect the CI publish step to
  error with "file already exists" (harmless, since the version is already live).
- **PyPI is irreversible.** Once `uv publish` succeeds, the version is permanent
  (can't re-upload the same version). That's why the script gates publish behind
  `--yes` + all-green checks + offers `--testpypi`.
