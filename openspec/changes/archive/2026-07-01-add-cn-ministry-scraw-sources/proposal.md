## Why

The daas catalog has scraper scripts for 5 Chinese ministries (住建部, 商务部, 农业农村部, 财政部, 交通运输部) but **none are registered in `mcp/daas.db`** — `scraw_configs` is empty and no matching `sources` rows exist, so the dashboard and daas-mcp tools cannot see or drive them. Separately, the major economic regulators (人民银行, 发改委, 海关总署, 外汇局) and several more ministries (工信部, 自然资源部, 生态环境部, 应急部, 科技部) have no scrapers at all. These ministries publish paginated 信息公开 / 通知公告 archives that fit the existing `fd-daas-scrapling-scraw-creator` pattern, so broadening coverage is mechanical work, not new architecture.

## What Changes

- **Register the 5 existing scraw scripts** into `mcp/daas.db`: one `sources` row each (via `mcp__daas-mcp__create_datasource`), `datasource_columns` + `scraw_configs` (via `register.py`), under the `网页抓取 / Web Scraw` category (id=10). Two already ship a `MANIFEST` (`moa_govpublic_archive`, `mot_shuju_archive`); three need a `MANIFEST` added before `register.py` can register them (`mohurd_xinwen_archive`, `mof_gkml_archive`, `fetch_mofcom_news`).
- **Add 9 new MANIFEST-style scrapers**, one per ministry, each authored via `fd-daas-scrapling-official` and registered via the same `MANIFEST → create_datasource → register.py` flow:

  | script | ministry | host |
  |---|---|---|
  | `pbc_zhengce_archive` | 人民银行 | pbc.gov.cn |
  | `ndrc_zcfg_archive` | 发改委 | ndrc.gov.cn |
  | `customs_zwgk_archive` | 海关总署 | customs.gov.cn |
  | `safe_tjxx_archive` | 外汇局 | safe.gov.cn |
  | `miit_zcwj_archive` | 工信部 | miit.gov.cn |
  | `mnr_zwgk_archive` | 自然资源部 | mnr.gov.cn |
  | `mee_zcwj_archive` | 生态环境部 | mee.gov.cn |
  | `mem_zcwj_archive` | 应急部 | mem.gov.cn |
  | `most_tzgg_archive` | 科技部 | most.gov.cn |

- Each new script mirrors to `mcp/scrapling-docker-mcp/scripts/` per the scraw convention.
- No new dependencies, no `.mcp.json` change, no schema change. The `scraw_contract.ScrawManifest` contract and `register.py` registrar already exist and are reused as-is.

## Capabilities

### New Capabilities
- `cn-ministry-scraw-sources`: Scrapers + daas registration for Chinese central-government ministries. Covers the 9 new ministry archives above and the registration of the 5 existing scraw scripts. Each source follows the established contract: a `MANIFEST`-bearing crawler script, a `sources` row, `datasource_columns` rows, a `scraw_configs` recipe row, and placement under the `网页抓取` category — verified before registration.

### Modified Capabilities
<!-- None. mof-gkml-scraw and mohurd-xinwen-scraw already require registration;
     this change executes that requirement rather than changing it. -->
- _(none)_

## Impact

- **New files**: 9 crawler scripts at `mcp/scrapling-uv-mcp/scripts/<name>.py` + 9 mirrors at `mcp/scrapling-docker-mcp/scripts/<name>.py`.
- **Modified files**: 3 existing scripts gain a module-level `MANIFEST` (`mohurd_xinwen_archive.py`, `mof_gkml_archive.py`, `fetch_mofcom_news.py`) so `register.py` can register them.
- **Database**: `mcp/daas.db` gains ~14 `sources` rows + N `datasource_columns` rows + 14 `scraw_configs` rows, all under category `网页抓取` (id=10). No schema migration — the tables already exist.
- **Skills**: uses `fd-daas-scrapling-scraw-creator` (orchestration + registration) and `fd-daas-scrapling-official` (script authorship). No skill edits.
- **No impact** on `.mcp.json`, dependencies, the dashboard schema, or other MCP servers.
- **Network**: ~14 crawl runs against `.gov.cn` hosts during verification; each bounded to 50 pages by default, `download_delay` pacing, single-threaded. Respect robots.txt.
