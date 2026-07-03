## Context

Two .gov.cn archives need to join the scraw fleet alongside `moa_govpublic_archive` and `mot_shuju_archive`:

- **MOHURD** (`https://www.mohurd.gov.cn/xinwen/index.html`) — a CMS-rendered news landing with three section archives at `/xinwen/{jsyw,gzdt,dfxx}/index.html`. Detail links are `art_<32-hex>.html`, dates live in `<span class="date-info">`. No date token in the URL.
- **MOF** (`https://www.mof.gov.cn/gkml/`) — TRS WCM `信息公开` portal with four sections (通知公告 / 财政数据 / 财政文告 / 财经论坛). The 通知公告 hub is itself a 3-tab sub-archive (通知通告 / 财政部令 / 财政部公告). Pagination is the TRS-standard `index_{N-1}.htm` offset-by-1, 404 on overflow. Most detail URLs carry a `t<YYYYMMDD>_<id>.htm` token — the most reliable date source.

Both are static HTML — verified via `Fetcher.get` returning a populated DOM. No JS, no anti-bot, no XHR escalation needed. Follows the exact pattern already established by `mot_shuju_archive.py` (15 archives, paginated `index_N.html`).

## Goals / Non-Goals

**Goals:**
- One scraw script per site that paginates every section under a 50-page-per-section default cap, with `--all` for full crawl.
- Records keyed by absolute URL (the primary key), with full `<a title>` (never truncated), parsed dates, and section/subsection labels.
- A `datasources` row + N `datasource_columns` rows + a `scraw_configs` recipe in `mcp/daas.db` per site, under a shared `网页抓取 / Web Scraw` category.
- Verification before registration: never register a datasource that returns 0 records for any section.

**Non-Goals:**
- Fetching the detail page bodies. Out of scope — only the archive list metadata is captured.
- A unified "gov-cn archive" datasource shape. Each site is its own `datasources` row with its own columns; cross-site joining is a downstream concern.
- Adding new MCP tools or schema columns. Both fit the existing `datasources` / `datasource_columns` / `scraw_configs` tables.
- Cron scheduling. The skill registers the scraper as a callable datasource; scheduling is a separate `cron-mcp` step the user can take later.

## Decisions

### Two scripts, not one

Each site is registered as a separate datasource because the URL schemes, section labels, list shapes, and date-source rules are different (MOF has `t<date>_` URL tokens, MOHURD does not; MOF has a `subsection` dimension under 通知公告, MOHURD has none). Merging them into one script would force a lowest-common-denominator schema and lose the per-site provenance the dashboard wants.

### Mirror `mot_shuju_archive.py` exactly

Same CLI surface (`--max-pages N` mutually exclusive with `--all`), same `SLEEP = 0.3`s pacing, same per-archive stderr breakdown, same `json.dumps(records, ensure_ascii=False, indent=2)` stdout shape. Consistency across the scraw fleet beats per-script cleverness — when the next person adds the third archive script, they shouldn't have to learn a new convention.

Alternative considered: a `Spider` class. Rejected — both sites paginate one section at a time with low concurrency needs (~3–6 sections × ≤50 pages = ≤300 GETs per full run), and the function-style paginator is what the existing fleet uses. `Spider` is appropriate for >~10-page-per-archive crawls with detail-page fan-out; we have neither.

### Date source: URL token first, span fallback

For MOF, the `t(\d{8})_` URL token (e.g. `t20260630_3992526.htm`) is the publish date. Some MOF list items also include a `<span>` date that lags the URL token by 1–4 days (clearly a review/release-date gap). The URL token wins because it's stable across cross-domain links (e.g. `http://zwgls.mof.gov.cn/ywgg/...`). The `<span>` text is the fallback when the URL has no `t<date>_` token (rare, mostly for sub-index pages).

For MOHURD, URLs are opaque `art_<32-hex>.html`. The `<span class="date-info">` is the only date source — use it directly.

### Page cap: 50 default, `--all` for full

Non-negotiable per the skill's guardrails. Empirically MOF 通知通告 currently has 22 pages (last shown `index_22.htm`), 财经论坛 has 19, 财政文告 has 1, so default 50 covers them all today; MOHURD section depths aren't yet measured but news archives typically run deep — `--all` is the explicit "I know it's big" lever.

### Single category `网页抓取 / Web Scraw`

Both datasources land in the same category so they're discoverable next to `moa_govpublic_archive` and `mot_shuju_archive`. If the category doesn't already exist in `daas.db`, create it at root (no parent).

## Risks / Trade-offs

- **Site layout drift** → both sites have used these layouts for years (TRS WCM for MOF, a custom CMS for MOHURD). Mitigation: per-section stderr line and a verification step before registration mean a layout change is loud, not silent.
- **Date-token failure on MOF** → if a record has no URL `t<date>_` token AND an empty `<span>`, `date` will be `""`. Mitigation: count empty dates on verification; if >1% of records, drop the script back to span-only and document.
- **Cross-domain MOF detail links** → many MOF records link to subdomain hosts (`zwgls.mof.gov.cn`, `gks.mof.gov.cn`, ...). We only store the URL; no follow. Mitigation: explicit — we don't fetch detail pages.
- **MOHURD pagination unknown until script is run** → I confirmed the list shape and date-info span but not the exact pagination token (`index_N.html`? AJAX?). Mitigation: the task list has an explicit "probe page 2 URL form" step before writing the loop; if it's AJAX-fed, escalate to capturing the XHR per the skill's playbook.
- **Going past 50 pages by default** → would hammer the host. Mitigation: hard-coded default; `--all` is the only escape and is the user's explicit choice.

## Migration Plan

Additive. No existing rows in `daas.db` are modified, no schema changes. To roll back: delete the two `datasources` rows (cascades via `datasource_columns` if FK is set, else delete those rows too), delete the two `scraw_configs` rows, and remove the four script files. The `网页抓取` category can stay or be deleted if it's empty.

## Open Questions

- **MOHURD pagination form** — confirmed at the "probe" step in tasks.md before writing the crawler. If it turns out to be AJAX-fed (unlikely given the page renders the date span server-side), escalate to `AsyncDynamicSession` + `capture_xhr` per the skill.
- **Date semantics on MOF** — using URL token vs span; document the rule in each column's `description` so dashboard consumers know which one they're looking at.
