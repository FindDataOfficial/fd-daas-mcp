## Context

`gov-scraw` (v0.1.0) is a complete, installable Python package at `gov-scraw/` in this monorepo (`FindDataOfficial/DAAS`). It bundles 11 Chinese-ministry scrapers, a CLI (`gov-scraw`), a read API, and a self-contained `registry.db`/`registry.json`. Its `pyproject.toml` uses setuptools, declares runtime deps `scrapling` + `sqlalchemy>=2.0`, and ships the registry via `package-data`. Today the only install path is `pip install git+https://github.com/FindDataOfficial/DAAS.git` — which pulls the entire monorepo. The prior change (`2026-07-01-gov-data-scraper-package`, archived) explicitly deferred PyPI publishing. This change closes that gap: publish to PyPI so `pip install gov-scraw` works, and make the release reproducible via CI.

The package lives in a subdirectory of a larger repo, not its own repo. PyPI publishes a **source tree**, not a repo, so the subdirectory location is fine — we build from `gov-scraw/`.

## Goals / Non-Goals

**Goals:**
- `pip install gov-scraw` installs the published package from PyPI into a clean venv, with the `gov-scraw` console script on PATH and `registry.db`/`registry.json` present inside the install.
- The release flow is documented and reproducible: version bump → build sdist+wheel → upload via twine → verify.
- A GitHub Actions workflow publishes automatically when a `gov-scraw-v*` tag is pushed, using a stored `PYPI_API_TOKEN`.
- Package metadata on PyPI is complete (description, classifiers, URLs, license) so the listing looks maintained.

**Non-Goals:**
- Splitting `gov-scraw/` into its own git repo.
- TestPyPI pre-releases (documented as optional, not automated).
- Signed releases / SLSA attestations / Trusted Publishing migration (API token is the v1 path; Trusted Publishing noted as a future upgrade).
- Changing scraper logic, the CLI, or the registry build.
- Publishing any other package in this monorepo to PyPI.

## Decisions

### Decision 1: Build backend stays setuptools; build via `python -m build`
The package already uses `setuptools.build_meta`. We keep it — no migration to hatchling/flit. Release artifacts are produced with `python -m build` (PEP 517), which generates both `sdist` (.tar.gz) and `wheel` (.whl) under `gov-scraw/dist/`.
- **Why not flit/hatchling**: zero benefit for a package that already builds cleanly under setuptools; migration churn risks breaking the bundled-registry `package-data` that currently works.
- **Why both sdist and wheel**: wheel is what most users install; sdist is the canonical source archive PyPI expects and is required for some downstream packaging.

### Decision 2: Upload via `twine upload` with a scoped PyPI API token
Use `twine upload dist/*` authenticated with a PyPI API token scoped to the `gov-scraw` project, stored as the `PYPI_API_TOKEN` repository secret. The first upload claims the project name on PyPI.
- **Alternative considered: Trusted Publishing (OIDC)**: cleaner (no long-lived token), but requires the package to be the repo's primary project and adds GitHub OIDC config. The package lives in a subdirectory of a multi-project repo, so a token is simpler for v1. Trusted Publishing is noted in RELEASE.md as the upgrade path.
- **Alternative considered: uploading from a local machine**: works for the first release but is not reproducible. CI-on-tag is the supported path; local upload is the documented fallback.

### Decision 3: Tag-triggered CI, not on-push
The workflow triggers on tags matching `gov-scraw-v*` (e.g. `gov-scraw-v0.1.0`). This avoids accidental publishes and decouples gov-scraw releases from monorepo commits.
- **Why a prefixed tag**: this repo contains other projects/tools that may later release independently; the `gov-scraw-` prefix namespaces this package's releases.
- The workflow: checkout → set up Python 3.11 → `uv`/`pip` install `build` + `twine` → `python -m build` → `twine upload dist/*` (token from secrets). A preceding job validates `python -c "import gov_scraw"` against the built wheel in a clean venv before the upload step runs.

### Decision 4: Metadata finalization in `pyproject.toml`
Add: `license = "MIT"` expression (currently `{ text = "MIT" }` — acceptable, but align to a single form), `classifiers` (Programming Language :: Python :: 3, 3.10/3.11/3.12, License :: OSI Approved :: MIT License, Topic :: Internet :: WWW/HTTP :: Indexing/Search), `[project.urls]` Homepage/Repository pointing at the monorepo, and confirm `readme = "README.md"` is present (it is). Keep `version = "0.1.0"` for the first release; bump on subsequent releases.
- **Why publish at 0.1.0**: it matches the current `__version__` and the package is already functionally complete and tested. If a local `0.1.0` was ever uploaded to TestPyPI, bump to `0.1.1`.

### Decision 5: Verify the bundled registry survives the wheel
The existing `[tool.setuptools.package-data]` declares `registry/registry.db` and `registry/registry.json`. Before publishing, run a clean-venv install of the built wheel and assert `python -c "import gov_scraw; gov_scraw.list_sources()"` returns 11 sources — this proves the DB shipped inside the install and the read API works post-install. This is the single most likely failure mode (data files missing from the wheel), so it is an explicit gate.

## Risks / Trade-offs

- **PyPI name collision** (`gov-scraw` taken by someone else) → check `https://pypi.org/project/gov-scraw/` before first upload; if taken, rename to `gov-scraw-cn` or similar and update `pyproject.toml` + README before building.
- **`registry.db` missing from the wheel** → mitigated by the clean-venv install gate (Decision 5); if it fails, add the path to `package-data` / `MANIFEST.in`.
- **Long-lived API token leaks** → token is scoped to the `gov-scraw` project only and stored as a GitHub Actions secret; Trusted Publishing is the documented future path to remove the token entirely.
- **Accidental publish from a mistagged commit** → workflow only fires on `gov-scraw-v*` tags; tags require explicit `git push --tags`.
- **Monorepo subdirectory build context** → the workflow `cd`s into `gov-scraw/` before building; sdist will contain only the `gov-scraw/` subtree (setuptools packages.find is scoped to `gov_scraw*`), so no monorepo leakage into the published artifact.
- **First-release-only steps (PyPI account, token, name claim) are not CI-reproducible** → documented in RELEASE.md as one-time setup; everything after the first release is automated.

## Migration Plan

1. **One-time (manual, outside CI)**: create a PyPI account, claim/verify the `gov-scraw` project name, generate a scoped API token, add it as repo secret `PYPI_API_TOKEN`.
2. Finalize `gov-scraw/pyproject.toml` metadata (Decision 4) and update README install instructions to `pip install gov-scraw`.
3. Add `.github/workflows/publish-gov-scraw.yml` and `gov-scraw/RELEASE.md`.
4. Locally: `cd gov-scraw && python -m build && twine upload dist/*` for the v0.1.0 first release (validates the pipeline end-to-end before relying on CI).
5. Verify: clean venv `pip install gov-scraw && gov-scraw list && python -c "import gov_scraw; print(len(gov_scraw.list_sources()))"`.
6. Going forward: bump version → commit → tag `gov-scraw-vX.Y.Z` → push tag → CI publishes.

**Rollback**: a published PyPI release cannot be deleted (only yanked). If v0.1.0 is broken, yank it on PyPI and publish a fixed `0.1.1` immediately. The git tag can be deleted/moved locally but the PyPI artifact is permanent — hence the clean-venv gate before upload.

## Open Questions

- Is `gov-scraw` still free on PyPI, or do we need `gov-scraw-cn`? (Resolved by a 30-second check of pypi.org/project/gov-scraw before first upload — tasks include this check.)
- First release version: `0.1.0` (current) or `0.1.1`? Default `0.1.0` unless the name was previously used on TestPyPI.
