## 1. Package scaffold

- [x] 1.1 Create `gov-scraw/` at repo root with `gov_scraw/__init__.py`, `gov_scraw/scripts/__init__.py`, `gov_scraw/registry/__init__.py`
- [x] 1.2 Write `gov-scraw/pyproject.toml`: name `gov-scraw`, python ≥3.10, deps `scrapling`, `pandas`, `sqlalchemy`; console script `gov-scraw = "gov_scraw.cli:main"`
- [x] 1.3 Add `gov-scraw/.gitignore` (exclude `__pycache__/`, `*.pyc`, `.venv/`, `build/`, `dist/`, `*.egg-info/`; keep `registry.db` + `registry.json`)
- [x] 1.4 Add `gov-scraw/LICENSE` (MIT)

## 2. Vendor contract + port scripts

- [x] 2.1 Copy `scraw_contract.py` into `gov_scraw/scraw_contract.py`, trimming `to_config()` to drop the `scraper_script` / `scraper_script_docker` monorepo-path fields; keep `to_columns_json()` and `to_scraw_columns()` byte-identical; keep the `__main__` self-check
- [x] 2.2 Copy the 11 archive scripts into `gov_scraw/scripts/`: `mee_gsgg_archive`, `mem_tzgg_archive`, `mnr_tzgg_archive`, `moa_govpublic_archive`, `mof_gkml_archive`, `mofcom_xwfb_archive`, `mohurd_xinwen_archive`, `mot_shuju_archive`, `ndrc_tzgg_archive`, `pbc_xinwen_archive`, `safe_whxw_archive` (verbatim crawl logic)
- [x] 2.3 In each copied script, rewrite `from scraw_contract import ...` → `from gov_scraw.scraw_contract import ...`; leave everything else (MANIFEST, `Fetcher`, `main()`, `argparse`) untouched
- [x] 2.4 Run `python -m gov_scraw.scraw_contract` to confirm the self-check passes; confirm `python -c "import gov_scraw.scripts.mof_gkml_archive"` works from inside `gov-scraw/`

## 3. Registry build

- [x] 3.1 Write `gov_scraw/build_registry.py`: import each `gov_scraw.scripts.<name>` module's `MANIFEST`, create `registry.db` with `sources` / `datasource_columns` / `scraw_configs` tables (same column shapes as `daas.db` for these tables, no FK to `datasources`), write rows using `MANIFEST.to_columns_json()` + `MANIFEST.to_scraw_columns()`, and write `registry.json` with the full dump
- [x] 3.2 Make `build_registry.py` logically idempotent (delete-then-insert per source; deterministic JSON `sort_keys`; re-run produces identical `.dump` + byte-identical `registry.json` — only SQLite's file-change-counter header byte differs)
- [x] 3.3 Run it once to generate `gov_scraw/registry/registry.db` + `registry.json`; verify 11 sources, ≥55 columns, each has a `url` PK column

## 4. Read API + CLI

- [x] 4.1 Write `gov_scraw/registry.py` with `list_sources()`, `get_source(name)`, `get_columns(name)` reading the bundled `registry.db` read-only; `get_source` raises `KeyError` on unknown name
- [x] 4.2 Write `gov_scraw/cli.py` (`argparse`) with subcommands: `crawl <name> [--max-pages N|--all]` (import `gov_scraw.scripts.<name>`, call its `main()` with synthesized `sys.argv`), `list` (print sources), `describe <name>` (print source + columns), `build-registry` (call `build_registry.main()`)
- [x] 4.3 Verify `crawl nope_archive` exits non-zero with a list of available names

## 5. README + packaging

- [x] 5.1 Write `gov-scraw/README.md`: purpose, per-ministry table (name/label/seed URL for all 11), `pip install git+<url>` install, `gov-scraw crawl` / `list` / `describe` / `build-registry` examples, `list_sources`/`get_columns` API example, registry schema (3 tables), polite-crawl warning
- [x] 5.2 `pip install -e gov-scraw/` and run `gov-scraw list` + `gov-scraw describe mof_gkml_archive` to confirm the end-to-end install path works

## 6. Verification

- [x] 6.1 `python -m gov_scraw.scraw_contract` self-check passes
- [x] 6.2 `gov-scraw build-registry` twice → `cmp` confirms `registry.json` byte-identical and `sqlite3 .dump` diff is empty (only the SQLite file-change-counter header byte differs)
- [x] 6.3 `git diff mcp/scrapling-uv-mcp/scripts/` is empty (monorepo untouched)
- [x] 6.4 `gov-scraw crawl mof_gkml_archive --max-pages 1` emits a JSON array to stdout and per-archive counts to stderr
