## Context

The repo already has a proven scraw pipeline (the `fd-daas-scrapling-scraw-creator` skill):

- **Contract**: `mcp/scrapling-uv-mcp/scripts/scraw_contract.py` defines `ScrawManifest` / `ScrawColumn` / `ScrawArchive` — the single source of truth for a scraper's identity, crawl recipe, and columns.
- **Authoring**: `fd-daas-scrapling-official` writes the crawler; fetcher escalation is `Fetcher.get` (static) → `DynamicFetcher` → `StealthyFetcher`.
- **Registration**: `mcp__daas-mcp__create_datasource` writes the `sources` row (with `config_json = MANIFEST.to_config_json()`); `register.py <name>` writes `datasource_columns` + `scraw_configs`. Both idempotent.
- **Category**: `网页抓取 / Web Scraw` (id=10) exists at top level.

Current state: 5 scripts exist (`mohurd_xinwen_archive`, `fetch_mofcom_news`, `moa_govpublic_archive`, `mof_gkml_archive`, `mot_shuju_archive`). Two have a `MANIFEST` (`moa_govpublic_archive`, `mot_shuju_archive`); three do not. **None are registered in `mcp/daas.db`** — `scraw_configs` is empty. The proven reference is `moa_govpublic_archive` (10,803 records, 1980→2026, 0 missing dates).

## Goals / Non-Goals

**Goals:**
- Register all 5 existing scraw scripts into `mcp/daas.db` (add `MANIFEST` to the 3 that lack one).
- Add 9 new ministry scrapers, each `MANIFEST`-bearing, verified, and registered.
- Reuse `scraw_contract` + `register.py` unchanged — no new abstraction.

**Non-Goals:**
- Per-ministry spec files (one grouped capability; per-ministry mechanics live here + the scripts).
- A new category subtree under `网页抓取` — all sources land directly under id=10. Split later if the tree grows.
- Scheduling via `cron-mcp` (out of scope; can be added per-source later).
- Full-text search / Elasticsearch indexing of scraped docs (that's `cnreport-mcp`'s job, not scraw's).
- Re-scraping the existing 3 pre-MANIFEST scripts' logic — only add `MANIFEST`, don't rewrite crawlers.

## Decisions

### D1. One grouped capability, not one spec per ministry
**Decision**: a single `cn-ministry-scraw-sources` capability covers all 14 sources.
**Rationale**: the existing `mof-gkml-scraw` / `mohurd-xinwen-scraw` specs leak per-site mechanics (section names, pagination rule) into the spec, which is implementation detail. The spec contract is invariant across ministries (MANIFEST exists → registered → verified); the per-site crawl details belong in the script + this design. Grouping avoids 9 near-duplicate spec files. A future change touching one ministry modifies the script, not the spec.
**Alternative rejected**: 9 per-ministry specs (matches existing convention but is 9× the boilerplate for a batch add, and freezes per-site details into spec text prematurely).

### D2. Reuse `scraw_contract` + `register.py` as-is
**Decision**: no edits to `scraw_contract.py` or `register.py`. Each new script imports `ScrawManifest`/`ScrawColumn` and defines a module-level `MANIFEST`.
**Rationale**: the contract already round-trips (self-check passes) and `register.py` already handles the `sources`-vs-`datasources` lookup and the stale-FK gotcha. Adding a layer would be reinventing what works.
**Alternative rejected**: a batch-registrar script that loops all 14 — unnecessary; `register.py` is already one-command-per-source and idempotent. A shell loop suffices.

### D3. Add `MANIFEST` to the 3 pre-MANIFEST scripts, don't rewrite them
**Decision**: for `mohurd_xinwen_archive`, `mof_gkml_archive`, `fetch_mofcom_news`, add a `MANIFEST = ScrawManifest(...)` block matching their existing output columns; do not touch the crawl logic.
**Rationale**: these scripts work and have been run. Rewriting risks behavior change. `register.py` only needs the `MANIFEST`; the crawl code can stay as-is.
**Risk**: the added `MANIFEST.columns` must exactly match the keys the script actually emits, or the registered schema will lie. Mitigation: diff the `MANIFEST.columns` names against a sample run's record keys before registering.

### D4. Category placement — flat under `网页抓取` (id=10)
**Decision**: all 14 sources get `category_id=10`. No new sub-categories.
**Rationale**: 14 sources is manageable in one category; a subtree is speculative structure. The dashboard groups by category, and `sources.config.archives` already carries per-source section/subsection for finer grouping. Add a sub-tree only if a category becomes unwieldy.

### D5. Fetcher escalation + date source per site
**Decision**: each new script starts with `Fetcher.get` (static) and escalates only if the list is empty/JS-rendered. Date extraction prefers the URL `t<YYYYMMDD>_` token (proven authoritative on MOF/MOA), falling back to the sibling `<span>` date text.
**Rationale**: `.gov.cn` archive pages are overwhelmingly static HTML with `index_N.htm` pagination and URL date tokens — the proven shape. Escalating to `DynamicFetcher`/`StealthyFetcher` only when needed keeps crawl cost low and avoids a browser dependency for sites that don't need it.
**Risk**: some ministry sites (e.g. MIIT, MEE) are known to be AJAX-fed or behind a WAF. Mitigation: if static + dynamic both return empty, capture the XHR endpoint (per the skill's discovery step) and hit it directly with `Fetcher`.

### D6. Default 50-page cap, `--all` override, gentle pacing
**Decision**: every new script takes `--max-pages` (default 50) / `--all`, single-threaded, `time.sleep(0.3)` between pages.
**Rationale**: the 50-page cap is the skill's non-negotiable default — a runaway crawl can't hammer a `.gov.cn` host for an hour before anyone notices. `--all` is the explicit "I know it's big" switch. Mirrors the existing scripts.

## Risks / Trade-offs

- **[AJAX / WAF-protected ministry sites]** → Discovery step captures the XHR endpoint and hits it directly; if a site needs `StealthyFetcher`, that script escalates per-fetch. Sites that cannot be scraped at all are dropped from scope with an honest note (per the skill's guardrails), not registered empty.
- **[Date token absent on some sites]** → Fall back to the visible `<span>` date; if both fail for a non-trivial fraction of records, block registration per the verify-before-register requirement.
- **[Pre-MANIFEST `MANIFEST.columns` mismatch]** → Diff `MANIFEST.columns` names vs. a sample run's record keys before registering the 3 converted scripts.
- **[Crawl volume on `.gov.cn` hosts]** → 50-page default cap + 0.3s sleep + single thread; `--all` only on explicit request. Verification runs use the default cap.
- **[Idempotency / partial registration]** → `register.py` is idempotent (replaces `datasource_columns`, upserts `scraw_configs`); `create_datasource` is re-callable. A failed run can be re-run after a fix without manual cleanup.
- **[Mirroring to docker-mcp]** → Each new script is copied to `mcp/scrapling-docker-mcp/scripts/` per convention; the two trees can drift if forgotten. Mitigation: the `sources.config.scraper_script_docker` field records the docker path so drift is visible; a future lint can diff the two trees.

## Migration Plan

Additive change — no migration, no schema work, no breaking change.

1. Add `MANIFEST` to the 3 pre-MANIFEST scripts; verify each still runs.
2. Register the 5 existing sources (create_datasource → register.py, ×5).
3. For each of the 9 new ministries: discover → author script → verify → register. One at a time, verify before moving on.
4. After all 14 are registered, run a final `sqlite3 mcp/daas.db "SELECT name FROM sources WHERE config LIKE '%scraw%';"` sanity check (expect 14 rows).

**Rollback**: delete the 14 `sources` rows (cascade clears `datasource_columns`; `scraw_configs` rows deleted by name), and `git rm` the 9 new script files. No DB schema to reverse.

## Open Questions

- **Exact archive sections per ministry**: the specific 信息公开 / 通知公告 sub-archives and their pagination shape are discovered during implementation (per the skill's discovery step). The 9 hosts above are the targets; the exact seed URLs are confirmed at authoring time.
- **`fetch_mofcom_news` naming**: it's the only existing script not named `*_archive`. Keep the name (renaming breaks the convention that `MANIFEST.name` equals basename and would orphan any prior references), or rename to `mofcom_news_archive` for consistency. Lean: keep the name — consistency of the `MANIFEST.name == basename` rule matters more than the `_archive` suffix.
- **Whether any of the 9 new sites is AJAX-only**: unknown until discovery. If a site has no static fallback, its script uses the XHR-direct path and the `MANIFEST.crawl` field documents the endpoint.
