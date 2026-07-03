## Why

Two central-government archives we want to track — 住房和城乡建设部 (MOHURD) news at `https://www.mohurd.gov.cn/xinwen/index.html` and 财政部 (MOF) 信息公开 at `https://www.mof.gov.cn/gkml/` — are public, well-structured, and have no off-the-shelf datasource. Both are paginated `.htm` archives that should be cataloged in `mcp/daas.db` like the existing `moa_govpublic_archive` / `mot_shuju_archive` so they can be queried, scheduled, and surfaced in the dashboard with the rest of the scraw fleet.

## What Changes

- Add `mohurd_xinwen_archive` scraw script: crawls 3 MOHURD news sections (`jsyw` 部门动态 / `gzdt` 工作动态 / `dfxx` 地方信息) under `/xinwen/`. List item shape `art_<uuid>.html` + `<span class="date-info">YYYY-MM-DD`. Columns: `section`, `title` (`a@title`), `date` (`span.date-info`), `url` (`a@href`, PK).
- Add `mof_gkml_archive` scraw script: crawls 4 MOF 信息公开 sections — 通知公告 (`bulinggonggao/tongzhitonggao/`, `czbl/`, `czbgg/`), 财政数据 (`caizhengshuju/`), 财政文告 (`caizhengwengao/`), 财经论坛 (`diaochayanjiu/`). List shapes `ul.xwbd_lianbolistfrcon > li > a[title]+span` and `ul.xwfb_listbox > li > a[title]+span`. Pagination `index_{N-1}.htm`, 404 on overflow. Columns: `section`, `subsection`, `title` (`a@title`), `date` (`url:re:t(\d{8})_` → fallback `span` text), `url` (`a@href`, PK), `doc_type` (html/pdf).
- Default `--max-pages 50` per archive; `--all` / `--max-pages 0` for full crawl. Both scripts mirrored to `mcp/scrapling-uv-mcp/scripts/` and `mcp/scrapling-docker-mcp/scripts/`.
- Register both as managed datasources in `mcp/daas.db`: one `datasources` row each (via `mcp__daas-mcp__create_datasource`), N `datasource_columns` rows each (via the skill's bundled `register_columns.py`), a `scraw_configs` recipe row each (via `mcp/scrapling-uv-mcp/scripts/db_helper.py`), placed under a `网页抓取 / Web Scraw` category (reuse if it exists, else create).

## Capabilities

### New Capabilities

- `mohurd-xinwen-scraw`: cataloged scraw datasource for the MOHURD `/xinwen/` archive (3 sections), with a verified crawler, registered datasource + columns + category + scraw recipe.
- `mof-gkml-scraw`: cataloged scraw datasource for the MOF `/gkml/` archive (4 sections, 6 sub-archives), with a verified crawler, registered datasource + columns + category + scraw recipe.

### Modified Capabilities

None. Existing scraw datasources (`moa_govpublic_archive`, `mot_shuju_archive`) are untouched.

## Impact

- **New files**: `mcp/scrapling-uv-mcp/scripts/mohurd_xinwen_archive.py`, `mcp/scrapling-uv-mcp/scripts/mof_gkml_archive.py`, plus identical mirrors under `mcp/scrapling-docker-mcp/scripts/`.
- **`mcp/daas.db`**: 2 new `datasources` rows, ~6 + ~6 new `datasource_columns` rows, 2 new `scraw_configs` rows, possibly 1 new `categories` row. No schema changes.
- **`mcp/daas-mcp/`**: read-only — invoke `create_datasource`, `create_category`, `get_category_tree`; no code changes.
- **Network**: outbound HTTPS to `www.mohurd.gov.cn` and `www.mof.gov.cn`. Verified crawls bounded to 50 pages/archive by default; `0.3s` sleep between requests.
- **Risk**: low. Both sites are static HTML — no JS, no anti-bot. If a section is missing on first run, the script logs `# [section] 0 docs` to stderr (matching the `mot_shuju_archive.py` convention) instead of silently registering empty.
