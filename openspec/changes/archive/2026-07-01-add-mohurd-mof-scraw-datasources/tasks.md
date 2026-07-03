## 1. Discovery (probe pagination + confirm list shape)

- [x] 1.1 Fetched MOHURD `/xinwen/jsyw/index.html` — list shape is `ul > li.date > a.fl[href][title] + span.date-info`, detail URLs `art_<32-hex>.html`.
- [x] 1.2 Probed pagination: `index_N.html` is 404. The list is loaded via XHR `GET https://www.mohurd.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit` with query `webId=86ca573ec4df405db627fdc2493677f3&pageId=<per-section>&tplSetId=fc259c381af3496d85e61997ea7771cb&pageType=column&tagId=栏目-list&parseType=bulidstatic&paramJson={"pageNo":N,"pageSize":20}`. Response is JSON `{data:{html:"<ul>...</ul>"}}` carrying 20 items. Per-section `pageId`/`count`: jsyw `f317736c953f43b893310d52b48aadaa` 1681, gzdt `919e942639b5477d96e4c97471c61d9f` 6019, dfxx `13f214f3a89147ea859e47aab5f60d72` 13392.
- [x] 1.3 MOF list shapes + pagination confirmed in the prior fetch pass (see proposal/design): `ul.xwbd_lianbolistfrcon > li > a[title] + span` and `ul.xwfb_listbox > li > a[title] + span`; pagination `index_{N-1}.htm` 404/empty terminates.

## 2. MOHURD scraper (mohurd_xinwen_archive)

- [x] 2.1 Wrote `mcp/scrapling-uv-mcp/scripts/mohurd_xinwen_archive.py` — calls the discovered jpaas API (`api-gateway/jpaas-publish-server/front/page/build/unit` with `paramJson={"pageNo":N,"pageSize":20}`), parses the embedded `<li class="date"><a class="fl" href title><span class="date-info">` shape via one regex, columns `section/title/date/url/doc_type`, default `--max-pages 50`, `--all` for full, `SLEEP=0.3`, stderr `# [section/slug] N docs` + `# TOTAL`.
- [x] 2.2 Mirrored to `mcp/scrapling-docker-mcp/scripts/mohurd_xinwen_archive.py` (identical, 5179 bytes).
- [x] 2.3 Verified with `--max-pages 5`: 300/300 docs across 3 sections (100 each), 0 missing dates, 0 empty titles, range 2025-06-03 → 2026-06-30. Sample: `部门动态 / 倪虹为住房城乡建设部党员干部讲专题党课 / 2026-06-30`.

## 3. MOF scraper (mof_gkml_archive)

- [x] 3.1 Wrote `mcp/scrapling-uv-mcp/scripts/mof_gkml_archive.py` mirroring `mot_shuju_archive.py`: 6 sub-archives, `page_url()` MOF offset-by-1, `parse_archive()` accepts both `ul.xwbd_lianbolistfrcon > li` and `ul.xwfb_listbox > li`, `url_date()` regex pulls `t<YYYYMMDD>_` token with `<span>` fallback, columns `section/subsection/title/date/url/doc_type`.
- [x] 3.2 Mirrored to `mcp/scrapling-docker-mcp/scripts/mof_gkml_archive.py`.
- [x] 3.3 Verified with `--max-pages 3`: 364 docs across 6 sub-archives (通知通告 66 / 财政部令 66 / 财政部公告 66 / 财政数据 75 / 财政文告 16 / 财经论坛 75), 0 missing dates, 0 empty titles, 21 PDFs auto-classified, range 2008-06-03 → 2026-06-30. URL-token dating works (sample: `t20260630_3992526.htm` → `2026-06-30`).

## 4. Register MOHURD datasource in daas.db

- [x] 4.1 Category resolved: `网页抓取 / Web Scraw` already exists at `id=10` (with `mot_shuju_archive` under it). Reused — did NOT create.
- [x] 4.2 Called `mcp__daas-mcp__create_datasource` → `sources.id=10`, name `mohurd_xinwen_archive`, category_id=10. `config_json` carries the API/sections/columns recipe.
- [x] 4.3 **Skipped — codebase mismatch with skill doc.** Inspection of `mcp/daas.db` shows `datasource_columns` is empty for ALL existing scraw datasources (`moa_gk`, `moa_govpublic_archive`, `mot_shuju_archive`). In this codebase, the `datasources` table is for DB connection strings (used by dashboard-mcp), and `datasource_columns` FKs to it — not to `sources`. Column metadata for scraw rows travels inside `sources.config_json.columns` (already written in 4.2). Running `register_columns.py` would either fail (no `datasources` row) or pollute the connection-string table; following the existing scraw fleet's pattern instead.
- [x] 4.4 `scraw_configs.id=4` saved via `db_helper.py save mohurd_xinwen_archive ...`.

## 5. Register MOF datasource in daas.db

- [x] 5.1 Reused `网页抓取` category id=10.
- [x] 5.2 `mcp__daas-mcp__create_datasource` → `sources.id=11`, name `mof_gkml_archive`, category_id=10. `config_json` lists all 6 sub-archives + columns.
- [x] 5.3 Skipped for the same reason as 4.3 — column metadata is in `sources.config_json.columns`.
- [x] 5.4 `scraw_configs.id=5` saved via `db_helper.py save mof_gkml_archive ...`.

## 6. Post-registration check

- [x] 6.1 `mcp__dashboard-mcp__list_datasources` returns `[]` — but that tool queries the `datasources` connection-strings table, NOT the `sources` scraw registry. Direct SQL on `sources WHERE category_id=10` confirms both new rows alongside `mot_shuju_archive`.
- [x] 6.2 `json_array_length(sources.config, '$.columns')` shows MOHURD=5 columns, MOF=6 columns (matches spec).
- [x] 6.3 Report in the chat message below.
