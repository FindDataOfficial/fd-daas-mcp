## 1. Pre-flight (one-time, manual)

- [ ] 1.1 Check `https://pypi.org/project/gov-scraw/` — confirm the name is free; if taken, decide on `gov-scraw-cn` (or similar) and update `pyproject.toml` `name` + README before proceeding
- [ ] 1.2 Create a PyPI account (if none) and, after the first upload succeeds, verify ownership of the `gov-scraw` project
- [ ] 1.3 Generate a PyPI API token scoped to the `gov-scraw` project only and add it to the GitHub repo as secret `PYPI_API_TOKEN` (Settings → Secrets and variables → Actions)
- [ ] 1.4 Decide first-release version: `0.1.0` (default) unless `0.1.0` was previously uploaded to TestPyPI, in which case `0.1.1`

## 2. Finalize package metadata

- [ ] 2.1 In `gov-scraw/pyproject.toml`: confirm/align `license = "MIT"`, add `classifiers` (Python 3, 3.10, 3.11, 3.12; License :: OSI Approved :: MIT License; Topic :: Internet :: WWW/HTTP :: Indexing/Search), add `[project.urls]` Homepage + Repository = `https://github.com/FindDataOfficial/DAAS`, confirm `readme = "README.md"`
- [ ] 2.2 Ensure `version` in `pyproject.toml` and `__version__` in `gov_scraw/__init__.py` match the chosen first-release version
- [ ] 2.3 Add `gov-scraw/dist/` and `gov-scraw/build/` to `gov-scraw/.gitignore` (build artifacts must not be committed)
- [ ] 2.4 Add `build` and `twine` to a `[project.optional-dependencies]` `dev` extra (or document them as release-only tools in RELEASE.md) — keep them out of runtime `dependencies`

## 3. README install instructions

- [ ] 3.1 Make `pip install gov-scraw` the first/primary install command in `gov-scraw/README.md`
- [ ] 3.2 Keep `pip install git+https://github.com/FindDataOfficial/DAAS.git` as a labeled "development / latest" alternative
- [ ] 3.3 Remove any wording implying the monorepo must be cloned

## 4. Local build + verification gate

- [ ] 4.1 From `gov-scraw/`, run `python -m build` — confirm `dist/` contains one `.tar.gz` and one `.whl` with matching versions
- [ ] 4.2 Inspect the wheel: `unzip -l dist/*.whl` — confirm `gov_scraw/registry/registry.db` and `gov_scraw/registry/registry.json` are present
- [ ] 4.3 In a fresh venv: `pip install dist/*.whl`, then `gov-scraw list` (expect 11 names) and `python -c "import gov_scraw; assert len(gov_scraw.list_sources())==11"`
- [ ] 4.4 `twine check dist/*` — must pass with no warnings before upload

## 5. First release (manual upload)

- [ ] 5.1 `twine upload dist/*` using the scoped API token (first upload claims the name on PyPI)
- [ ] 5.2 Verify on a truly clean venv (not the build venv): `pip install gov-scraw && gov-scraw list && python -c "import gov_scraw; print(len(gov_scraw.list_sources()))"`
- [ ] 5.3 Confirm the PyPI project page renders the README, license, URLs, and classifiers

## 6. CI publish workflow

- [ ] 6.1 Add `.github/workflows/publish-gov-scraw.yml` triggering on `push` of tags `gov-scraw-v*`
- [ ] 6.2 Job: checkout → setup Python 3.11 → install `build` + `twine` → `cd gov-scraw && python -m build`
- [ ] 6.3 Add a verify step: create a fresh venv, `pip install gov-scraw/dist/*.whl`, run `python -c "import gov_scraw; assert len(gov_scraw.list_sources())==11"` — fail the job if it errors
- [ ] 6.4 Upload step (`twine upload dist/*`) gated behind the verify step, using `PYPI_API_TOKEN` from secrets; mark it `if: success()`
- [ ] 6.5 Confirm the workflow does NOT trigger on plain branch pushes (tag-only)

## 7. Release documentation

- [ ] 7.1 Add `gov-scraw/RELEASE.md` documenting: one-time PyPI account + token setup, the local build/upload commands, the verify step, and the tag-triggered CI path
- [ ] 7.2 Document the version-bump checklist: update `version` in `pyproject.toml` + `__init__.py`, commit, `git tag gov-scraw-vX.Y.Z`, `git push origin gov-scraw-vX.Y.Z`
- [ ] 7.3 Document rollback: yank-on-PyPI (cannot delete), then publish a fixed `X.Y.Z+1`
- [ ] 7.4 Note Trusted Publishing (OIDC) as the future upgrade path to remove the long-lived token

## 8. Final validation

- [ ] 8.1 Re-run `openspec validate publish-gov-scraw-to-pypi --strict` and fix any reported issues
- [ ] 8.2 Confirm `git diff mcp/scrapling-uv-mcp/scripts/` is empty (monorepo scrapers untouched)
- [ ] 8.3 End-to-end smoke: from a clean venv, `pip install gov-scraw && gov-scraw describe mof_gkml_archive` succeeds and prints the source + its columns
