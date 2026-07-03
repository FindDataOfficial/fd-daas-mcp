## 1. Register the 5 existing scraw scripts

- [x] 1.1 Added `MANIFEST = ScrawManifest(...)` to `mohurd_xinwen_archive.py` (import from `scraw_contract`); `MANIFEST.name == mohurd_xinwen_archive`. Verified: 60 docs, keys match columns, 0 missing dates.
- [x] 1.2 Added `MANIFEST` to `mof_gkml_archive.py` (columns: section, subsection, title, date, url, doc_type; url pk). Verified: 128 docs, keys match, 0 missing dates.
- [x] 1.3 SKIPPED as written: `fetch_mofcom_news.py` is docker-only and outputs a dict `{category: [...]}`, not the flat-table shape `datasource_columns` models; retrofitting a MANIFEST would force a round peg. MOFCOM moves to the new batch (Group 11) as a fresh paginated `mofcom_xwfb_archive` scraper. `moa_gk.py` likewise skipped (landing preview, superseded by `moa_govpublic_archive`); its orphan `scraw_configs` row (id=1) left in place. Net 14 sources unchanged (4 existing + 10 new).
- [x] 1.4 Ran `register.py <name> --check` for the 4 MANIFEST-bearing scripts (`moa_govpublic_archive`, `mot_shuju_archive`, `mof_gkml_archive`, `mohurd_xinwen_archive`) — all load, `name == basename`.
- [x] 1.5 For each of the 4: `create_datasource`/`update_datasource` (config_json = `MANIFEST.to_config_json()`, category_id=10) → `register.py <name>`. Verified `sources` rows (ids 9,10,11,12) + `datasource_columns` + `scraw_configs` rows exist. `moa_govpublic` created as id=12; `mohurd`(10)/`mof`(11) had stale pre-MANIFEST config → refreshed via `update_datasource`; `mot`(9) already correct.
- [x] 1.6 Confirmed: 4 sources registered (ids 9,10,11,12) + 1 orphan `scraw_configs` recipe (`moa_gk`, no sources row). `scraw_configs` has 5 rows total.

## 2. New scraper — 人民银行 (PBOC, pbc.gov.cn)

- [x] 2.1 Discovered the 新闻发布 archive at `/goutongjiaoliu/113456/113469/` — PBC's rolling announcement stream (~8100 docs / 406 pages). List: `font.newslist_style > a[title][istitle] + span.hui12`. Pagination: TRS module-id `index.html` → `11040-<N>.html`. Date: URL `<YYYYMMDD>` token + span fallback. Static `Fetcher.get` sufficed (no Dynamic/Stealthy needed).
- [x] 2.2 Authored `mcp/scrapling-uv-mcp/scripts/pbc_xinwen_archive.py` with `MANIFEST` (renamed from `pbc_zhengce_archive` — accurate to the 新闻发布 feed scraped); mirrored to docker-mcp. Columns: section, title, date, url(pk), doc_type.
- [x] 2.3 Verified `--max-pages 2`: 30 docs over 2 real pages (module-id pagination confirmed), dates 2026-06-30→2026-06-05, 0 missing dates, URLs unique.
- [x] 2.4 Registered: `create_datasource` (id=13, category_id=10) → `register.py` (5 columns, scraw_configs inserted).

## 3. New scraper — 发改委 (NDRC, ndrc.gov.cn)

- [x] 3.1 Discovered 通知公告 archive at `/xwdt/tzgg/` — clean TRS `ul.u-list > li > a[title] + span`, `createPageHTML(20)` pagination, `t<YYYYMMDD>_` URL date token. Static fetch sufficed.
- [x] 3.2 Authored `ndrc_tzgg_archive.py` (renamed from `ndrc_zcfg_archive` for accuracy) with `MANIFEST`; mirrored to docker-mcp.
- [x] 3.3 Verified `--max-pages 2`: 50 docs, 0 missing dates, unique URLs.
- [x] 3.4 Registered: id=14, 5 columns, scraw_configs inserted.

## 4. New scraper — 海关总署 (Customs, customs.gov.cn)

- [x] 4.1 DROPPED — `/customs/xwfb34/index.html` returns HTTP **412** with a JS anti-bot challenge meta (`r="m"`) on both static `Fetcher.get` and `StealthyFetcher`. No practical crawl path without a paid/complex bypass. Honest-coverage note recorded.
- [~] 4.2–4.4 N/A (dropped).

## 5. New scraper — 外汇局 (SAFE, safe.gov.cn)

- [x] 5.1 Discovered 外汇新闻 archive at `/safe/whxw/` — `div.list_conr li > dt a[title] + dd` (date), pagination `index.html` → `index_N.html` (no offset).
- [x] 5.2 Authored `safe_whxw_archive.py` (renamed from `safe_tjxx_archive` for accuracy) with `MANIFEST`; mirrored to docker-mcp. Tightened selector to `div.list_conr li` after first run caught nav `<li>` items.
- [x] 5.3 Verified `--max-pages 2`: 40 docs, 0 missing dates, unique URLs.
- [x] 5.4 Registered: id=15, 5 columns, scraw_configs inserted.

## 6. New scraper — 工信部 (MIIT, miit.gov.cn)

- [x] 6.1 DROPPED — `/zwgk/zcwj/` is a JS-rendered SPA search interface (政策文件库). Playwright `network_idle` render returns rich records, but pagination is JS-click-driven (URL `&p=N` param returns the same page-1 records), and the XHR endpoint path (`/search-front-server/search/search`) returns `code:"404"`. No static/JSON path found; browser-per-page would be heavy. Honest-coverage note recorded.
- [~] 6.2–6.4 N/A (dropped).

## 7. New scraper — 自然资源部 (MNR, mnr.gov.cn)

- [x] 7.1 Discovered 通知公告 archive at `/gk/tzgg/` — `ul.ky_open_list > li > span + a` (date before link), `createPageHTML(40)` pagination, doc URLs on `gi.mnr.gov.cn` subdomain with `t<YYYYMMDD>_` token.
- [x] 7.2 Authored `mnr_tzgg_archive.py` (renamed from `mnr_zwgk_archive` for accuracy) with `MANIFEST`; mirrored to docker-mcp.
- [x] 7.3 Verified `--max-pages 2`: 50 docs, 0 missing dates/titles, unique URLs.
- [x] 7.4 Registered: id=16, 5 columns, scraw_configs inserted.

## 8. New scraper — 生态环境部 (MEE, mee.gov.cn)

- [x] 8.1 Discovered 公示公告 archive at `/ywdt/gsgg/` — `ul li > a.ll_xxgk_gsq_list_a + span`, `.shtml` docs with `t<YYYYMMDD>_` token, `createPageHTML` pagination.
- [x] 8.2 Authored `mee_gsgg_archive.py` (renamed from `mee_zcwj_archive` for accuracy) with `MANIFEST`; mirrored to docker-mcp. No WAF — static fetch worked.
- [x] 8.3 Verified `--max-pages 2`: 8 docs, 0 missing dates/titles, unique URLs (pagination advances).
- [x] 8.4 Registered: id=17, 5 columns, scraw_configs inserted.

## 9. New scraper — 应急部 (MEM, mem.gov.cn)

- [x] 9.1 Discovered 通知公告 archive at `/gk/tzgg/` — `<a href><title text><span>date</span></a>` (span INSIDE link), `countPage=25`/`dataCount=1183`, `.shtml` docs.
- [x] 9.2 Authored `mem_tzgg_archive.py` (renamed from `mem_zcwj_archive` for accuracy) with `MANIFEST`; mirrored to docker-mcp. Pagination cracked: offset-by-1 `.shtml` (`index_1.shtml`=page 2, not `index_1.html` which 404s).
- [x] 9.3 Verified `--max-pages 2`: 40 docs, 0 missing dates/titles, unique URLs.
- [x] 9.4 Registered: id=18, 5 columns, scraw_configs inserted.

## 10. New scraper — 科技部 (MOST, most.gov.cn)

- [x] 10.1 DROPPED — site is fully JS-rendered; Playwright `network_idle` render of `/xxgk/xinxifenlei/...` returns empty `<html></html>`, and the 通知公告 sub-path 404s. No static/JSON path found. Honest-coverage note recorded.
- [~] 10.2–10.4 N/A (dropped).

## 11. New scraper — 商务部 (MOFCOM, mofcom.gov.cn)

- [x] 11.1 Discovered the `/xwfb/index.html` landing statically renders 7 news sections (`h4.sTitle_02 + ul li > a[title] + span`). Deep per-section archives are JS-rendered (no static pagination path), so scope is the landing PREVIEW (~42 latest docs), not a full archive — documented honestly in the MANIFEST `coverage_note`.
- [x] 11.2 Authored `mofcom_xwfb_archive.py` with `MANIFEST`; mirrored to docker-mcp. Replaces the old docker-only `fetch_mofcom_news.py` (dict output) with a flat-table, MANIFEST-bearing scraper.
- [x] 11.3 Verified: 42 docs across 7 sections, 0 missing titles, unique URLs (6/42 missing dates — press-conference items without bracket dates; acceptable for preview scope).
- [x] 11.4 Registered: id=19, 5 columns, scraw_configs inserted.

## 12. Final validation

- [x] 12.1 `scraw_configs` has 12 rows (11 registered sources + 1 orphan `moa_gk` recipe with no sources row).
- [x] 12.2 `sources` table has **11** scraw rows (ids 9–19): 4 existing (mot/mohurd/mof/moa) + 7 new (pbc/ndrc/safe/mnr/mee/mem/mofcom). Original target was 14; 3 dropped (customs/MIIT/MOST).
- [x] 12.3 Every registered source's `datasource_columns` has a `url` row with `is_primary_key=1`, and **0 columns** have empty `description`/`source_field` (verified across all 11).
- [ ] 12.4 Spot-check the dashboard (`/collections` or datasources view) shows the 11 sources under `网页抓取`. (Dashboard server not running in this session — left for user to confirm.)
- [x] 12.5 Coverage notes: **3 ministries dropped** — 海关总署 (412 anti-bot JS), 工信部 (JS SPA, no static/XHR path), 科技部 (JS render returns empty). **1 partial** — 商务部 (landing preview only, ~42 docs). The other 10 are full paginated archives.
