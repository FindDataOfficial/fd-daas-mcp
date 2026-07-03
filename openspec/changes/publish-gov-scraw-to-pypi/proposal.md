## Why

The `gov-scraw` package is built and installable via `pip install git+https://github.com/FindDataOfficial/DAAS.git` (subtree `gov-scraw/`), but that path requires cloning the whole monorepo and was explicitly deferred from the prior change. Consumers who just want the 11 ministry scrapers should be able to `pip install gov-scraw` from PyPI with zero repo knowledge. PyPI is also the distribution channel every other tool in this ecosystem expects.

## What Changes

- Bump `gov-scraw` to a releaseable version and finalize `pyproject.toml` for PyPI: pinned metadata, README as long-description, license expression, classifiers, project URLs (homepage/source), and ensure `registry.db` / `registry.json` ship in the wheel via `package-data` (already set — verify).
- Add a PyPI publishing workflow: build sdist + wheel (`python -m build`), upload with `twine upload`, validate with `pip install gov-scraw` in a clean venv.
- Add a GitHub Actions workflow (`.github/workflows/publish-gov-scraw.yml`) that builds and publishes to PyPI on a pushed `gov-scraw-v*` tag, using `PYPI_API_TOKEN` from repo secrets (Trusted Publishing optional alternative).
- Add a `RELEASE.md` (or a `## Releasing` section in the package README) documenting the version-bump → tag → publish flow and the local build/upload commands.
- Mark the package metadata as published: README install instructions updated to show `pip install gov-scraw` as the primary path (git install remains a fallback).

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `gov-scraw-package`: add a PyPI distribution requirement — the package SHALL be published to PyPI so `pip install gov-scraw` installs it without cloning the repo, and the release flow (build → twine → tag-triggered CI) SHALL be documented and reproducible.

## Impact

- **Affected code**: `gov-scraw/pyproject.toml` (metadata finalization), `gov-scraw/README.md` (install instructions), new `gov-scraw/RELEASE.md`, new `.github/workflows/publish-gov-scraw.yml`. No change to scraper logic, `cli.py`, `build_registry.py`, or the bundled registry.
- **Dependencies**: adds `build` and `twine` as dev/build-time tools (not runtime deps). Runtime deps (`scrapling`, `sqlalchemy>=2.0`) unchanged.
- **External systems**: PyPI — requires a `gov-scraw` project ownership + an API token stored as `PYPI_API_TOKEN` repo secret. First release claims the name on PyPI.
- **Versioning**: first PyPI release targets `0.1.0` (current) or `0.1.1` if `0.1.0` was already used locally; subsequent releases follow semver with a git tag `gov-scraw-vX.Y.Z`.
- **Out of scope**: TestPyPI pre-release (optional, mentioned in RELEASE.md only), automated reproducible builds (sigstore/attestations), splitting `gov-scraw/` into its own repo. The monorepo scripts remain untouched.
