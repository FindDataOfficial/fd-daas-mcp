## ADDED Requirements

### Requirement: PyPI distribution

The `gov-scraw` package SHALL be published to PyPI such that `pip install gov-scraw` installs it into a clean virtual environment with no reference to the source repository. The published artifacts SHALL include both a source distribution (`sdist`, `.tar.gz`) and a binary distribution (`wheel`, `.whl`) built via PEP 517 (`python -m build`). The wheel SHALL ship the bundled `registry.db` and `registry.json` so that `import gov_scraw; gov_scraw.list_sources()` works immediately after install with no additional fetch.

#### Scenario: Clean-venv install from PyPI

- **WHEN** a user runs `pip install gov-scraw` in a fresh virtual environment
- **THEN** the install succeeds without cloning any git repository
- **AND** the `gov-scraw` console script is on PATH
- **AND** `python -c "import gov_scraw; print(len(gov_scraw.list_sources()))"` prints `11`
- **AND** `gov-scraw list` prints the 11 source names

#### Scenario: Wheel contains the bundled registry

- **WHEN** the built wheel is inspected
- **THEN** it contains `gov_scraw/registry/registry.db` and `gov_scraw/registry/registry.json`
- **AND** installing only the wheel (no sdist) is sufficient for the read API and CLI to function

#### Scenario: Both sdist and wheel are produced

- **WHEN** `python -m build` runs in `gov-scraw/`
- **THEN** `gov-scraw/dist/` contains exactly one `.tar.gz` and one `.whl` whose versions match `pyproject.toml`

### Requirement: PyPI metadata is complete

The package `pyproject.toml` SHALL declare metadata sufficient for a maintained PyPI listing: `name`, `version`, `description`, `readme = "README.md"`, `license` (MIT), `requires-python`, `authors`, `classifiers` (Python 3 + 3.10/3.11/3.12, MIT license, relevant topic), and `[project.urls]` with Homepage and Repository pointing at `https://github.com/FindDataOfficial/DAAS`. Runtime dependencies SHALL remain `scrapling` and `sqlalchemy>=2.0`.

#### Scenario: PyPI listing renders the README

- **WHEN** the package page is viewed on pypi.org after upload
- **THEN** the rendered long-description matches `gov-scraw/README.md`
- **AND** the page lists the project URL, MIT license, and supported Python versions
- **AND** the only declared runtime requirements are `scrapling` and `sqlalchemy>=2.0`

### Requirement: Reproducible release flow

The release flow SHALL be documented in `gov-scraw/RELEASE.md` and reproducible from a clean checkout: bump version in `pyproject.toml` and `gov_scraw/__init__.py` → build sdist+wheel with `python -m build` → upload with `twine upload dist/*` → verify with a clean-venv install. The first release SHALL additionally document the one-time PyPI account setup and scoped API-token creation. A subsequent release SHALL only require a version bump and a tagged push.

#### Scenario: Local release from clean checkout

- **WHEN** a maintainer follows `RELEASE.md` from a fresh clone
- **THEN** they can build and upload a release without referencing any external documentation
- **AND** the documented verify step (`pip install gov-scraw==<version>` in a fresh venv, then `gov-scraw list`) succeeds

### Requirement: Tag-triggered CI publish

A GitHub Actions workflow at `.github/workflows/publish-gov-scraw.yml` SHALL build and publish `gov-scraw` to PyPI when a tag matching `gov-scraw-v*` is pushed. The workflow SHALL authenticate to PyPI using the `PYPI_API_TOKEN` repository secret. Before uploading, the workflow SHALL install the built wheel into a clean virtual environment and assert `gov_scraw.list_sources()` returns 11 sources; the upload step SHALL NOT run if this assertion fails.

#### Scenario: Pushing a release tag publishes to PyPI

- **WHEN** a maintainer pushes a tag `gov-scraw-v0.1.0`
- **THEN** the workflow builds the sdist and wheel
- **AND** installs the wheel in a clean venv and verifies `gov_scraw.list_sources()` returns 11
- **AND** uploads the artifacts to PyPI using `PYPI_API_TOKEN`
- **AND** `pip install gov-scraw==0.1.0` succeeds afterwards

#### Scenario: Non-release commits do not publish

- **WHEN** a commit is pushed to the default branch without a `gov-scraw-v*` tag
- **THEN** no upload to PyPI occurs
- **AND** the workflow either does not run or runs only the build/verify steps without uploading

#### Scenario: Verification failure blocks upload

- **WHEN** the built wheel is missing `registry.db` (or otherwise fails the `list_sources()` check)
- **THEN** the workflow fails the verification step
- **AND** the upload step does not execute
- **AND** no artifact is published to PyPI

### Requirement: Primary install path is PyPI

The `gov-scraw/README.md` install instructions SHALL present `pip install gov-scraw` as the primary install path. The `pip install git+https://...` form SHALL remain documented as a fallback for tracking the development tip. The README SHALL NOT imply the package requires cloning the monorepo.

#### Scenario: README points at PyPI

- **WHEN** the README is read
- **THEN** the first install command shown is `pip install gov-scraw`
- **AND** a `pip install git+https://github.com/FindDataOfficial/DAAS.git` form is shown as an alternative labeled for development/latest
