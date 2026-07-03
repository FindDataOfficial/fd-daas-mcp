---
name: fd-daas-scrapling-scraw-creator
description: Create a recurring, cataloged web data source end-to-end from a URL. Discovers the page's structure, clarifies the FULL data scope with the user (not just the current URL — also sub-URLs and pagination), writes a multipage scrapling crawler (delegates script authorship to the fd-daas-scrapling-official skill), then registers the site into the daas-mcp database as a managed datasource with columns and a category. Use whenever the user gives a website URL and wants reusable structured extraction that is persisted to the database — phrases like "scrape this site and save it", "crawl the whole section not just this page", "add this website as a datasource", "抓取这个网站并存到数据库", "把整个栏目的数据都抓下来", or any URL + "save/register/persist/crawl all". Default crawls multipage with a 50-page cap (override with --all). Prefer this over fd-daas-scraw-scrapling when full sub-URL coverage, multipage crawling, and daas datasource/column/category registration are wanted, not a one-shot single-page fetch.
---

# fd-daas-scrapling-scraw-creator

Turn a website into a managed, reusable daas datasource: discover → clarify full
scope → crawl multipage → register (datasource + columns + category) into
`mcp/daas.db`. The actual scraper scripts are written by the
`fd-daas-scrapling-official` skill — this skill is the orchestration + database
registration layer on top of it.

## Mental model

Three things must end up true when this skill finishes:

1. **A scraper script exists** at `mcp/scrapling-uv-mcp/scripts/<name>.py`,
   written via `fd-daas-scrapling-official`, that paginates and follows the
   agreed sub-URLs. Default cap 50 pages; `--all` / `--max-pages 0` for full.
   **The script ships a module-level `MANIFEST = ScrawManifest(...)`** — the
   stable contract that defines its identity, crawl recipe, and output schema.
   See `mcp/scrapling-uv-mcp/scripts/scraw_contract.py`.
2. **The scraped data was verified** — you ran the script and showed the user
   real records + counts. Never register before verifying.
3. **A daas datasource exists in `mcp/daas.db`** with:
   - one `sources` row (via the `mcp__daas-mcp__create_datasource` MCP tool —
     this writes the `sources` table, NOT the legacy `datasources` table)
   - N `datasource_columns` rows + an upserted `scraw_configs` recipe row,
     both written by **`mcp/scrapling-uv-mcp/scripts/register.py <name>`**
     (one command, reads MANIFEST, handles the `sources`/FK gotcha)
   - a category assignment (via `mcp__daas-mcp__create_category` /
     `get_category_tree`)

## Defaults (state these to the user up front)

| knob | default | override |
|---|---|---|
| crawl breadth | **section + pagination + sub-pages** | user picks narrower/broader at clarify step |
| multipage stop | **50 pages** | `--all` or `--max-pages N` |
| fetcher | `Fetcher.get` (static) → escalate `DynamicFetcher` → `StealthyFetcher` | based on what the page needs |
| persistence | datasource + columns + category + scraw recipe | records → output file (not the DB) |

The 50-page cap exists so a runaway crawl can't hammer a site for an hour before
anyone notices. `--all` is the explicit "I know it's big, get everything" switch.

## Workflow

### 1. Intake + scope clarification (REQUIRED, do not skip)

The user gives a URL and (maybe) what they want. Your first job is to clarify
the **full** scope — the user explicitly wants you to ask, not assume. Present
these scope options and recommend the default:

- **A. single page** — just the list on this URL, no pagination
- **B. section + pagination** *(default)* — paginate the list/archive this URL
  is part of, AND follow linked sub-pages within the same archive/section

  This is the recommended breadth: it covers "sub-URLs" the user asked for
  without boiling the whole domain.
- **C. whole path/subdomain** — follow every link under the given URL path.
  Heaviest; only on explicit request.
- **D. explicit sub-URL list** — user names the exact pages/sections.

Also confirm: default 50-page cap, or `--all`? And if the user named target
columns, use them; if not, you'll discover and propose them.

> Why ask: a URL is a pointer to one page, but the valuable data is almost
> always the *archive behind it* (paginated, with linked detail/section pages).
> Confirming scope up front prevents both under-scraping (missing the history)
> and over-scraping (crawling unrelated sections of the site).

### 2. Discovery fetch

Delegate to `fd-daas-scrapling-official`. Start cheap and escalate:

```python
from scrapling.fetchers import Fetcher
page = Fetcher.get('<URL>')        # static HTML — try first
# empty / JS-rendered grid? escalate:
from scrapling.fetchers import DynamicFetcher      # needs a browser
from scrapling.fetchers import StealthyFetcher     # anti-bot / Cloudflare
```

Discover:
- **the list structure** — what CSS selector wraps one record? (e.g. `div.content_list li`, `tr`, `.quote`)
- **per-record fields** — title, date, url, etc. Note the extraction source for
  each (CSS selector, or a URL token like `t<date>` for dates — URL tokens are
  the most reliable date source, prefer them over visible spans).
- **pagination mechanism** — one of:
  - `index_N.htm` / `index_2.htm` (path-based, 404 on overflow) ← common on .gov.cn
  - `?page=N` / `?pageNow=N` query param
  - a "下一页/Next" link with an `href`
  - **AJAX/XHR** — the grid loads via a separate endpoint, not in the DOM.
    If static HTML + DynamicFetcher both return no docs, capture the XHR:
    ```python
    async with AsyncDynamicSession(capture_xhr=r"https://api\.site\.com/.*") as s:
        page = await s.fetch('<URL>')
        for xhr in page.captured_xhr: print(xhr.url, xhr.status)
    ```
    then hit that endpoint directly with `Fetcher`.
- **sub-page links** — links to detail/section pages within the same archive
  (scope B). Decide follow depth (usually 1: list → detail, not recursive).

### 3. Agree columns → author them in the script's `MANIFEST`

Columns are defined ONCE, as `ScrawColumn` instances inside the script's
module-level `MANIFEST = ScrawManifest(...)`. The same manifest is read by
`register.py` (writes `datasource_columns` + `scraw_configs`) and embedded in
`sources.config` (read by the dashboard) — one source of truth, no hand-rolled
JSON files.

```python
# top of scripts/<name>.py
from scraw_contract import ScrawManifest, ScrawColumn, ScrawArchive

MANIFEST = ScrawManifest(
    name="<name>",                              # MUST equal script basename
    label="<human label>",
    url="<seed URL>",
    description="<what + how it's crawled>",
    columns=[
        ScrawColumn(name="title", nullable=False,
                    description='document title (from <span class="news-title">)',
                    source_field="span.news-title", semantic_type="title"),
        ScrawColumn(name="date", type="date", nullable=False,
                    description="publish date YYYY-MM-DD",
                    source_field="span.news-date", semantic_type="date"),
        ScrawColumn(name="url", primary_key=True, nullable=False,
                    description="absolute document URL",
                    source_field="a.news-link@href", semantic_type="url"),
    ],
    archives=[ScrawArchive(section="...", subsection="...", url="...")],
    crawl={"item_selector": "li.news-item",
           "pagination": "index.html → index_{N-1}.html, 404 on overflow",
           "default_max_pages": 50},
)
```

`ScrawColumn` field meanings:

| field | what to put |
|---|---|
| `name` | the field name (Python-idiomatic; becomes `column_name` on disk) |
| `type` | `string` (default) / `integer` / `float` / `date` / `datetime` / `boolean` |
| `primary_key` | `True` if this uniquely identifies a record (often the `url`) |
| `nullable` | `False` if always present, `True` (default) if sometimes missing |
| `description` | plain-language meaning, **including where the value comes from** |
| `source_field` | **the scraw bridge** — CSS selector (`a@title`), URL token (`url:re:t(\d{8})_`), or `meta:section` for a column the scraper synthesizes. |
| `unit` | `元`, `%`, etc.; `""` (default) if none |
| `semantic_type` | `title` / `date` / `url` / `identifier` / `category` / `amount` / `text` |

Show the user the proposed columns (list + descriptions + source_fields),
confirm before scraping. Each column needs a `description` and a
`source_field` — these are what make the data self-documenting in the
dashboard.

### 4. Write the scraper (delegate to fd-daas-scrapling-official)

Invoke the `fd-daas-scrapling-official` skill to author the crawler. Tell it:
- the discovery findings (list selector, pagination mechanism, sub-page rule)
- the agreed columns + their `source_field`s
- save to `mcp/scrapling-uv-mcp/scripts/<name>.py`
- **default `--max-pages 50`**, `--all` / `--max-pages 0` for full crawl
- output JSON to stdout (`json.dumps(records, ensure_ascii=False, indent=2)`)
- respect robots.txt, add `download_delay` for big crawls, `robots_txt_obey=True`
  on spiders

For multipage, prefer the `Spider` class (concurrent, pause/resume) when the
crawl is large (>~10 pages); a plain paginating function is fine for small ones.

Mirror the script to `mcp/scrapling-docker-mcp/scripts/<name>.py` too (the
docker runtime), per the scraw convention.

### 5. Run & verify

```bash
uv run --directory mcp/scrapling-uv-mcp python scripts/<name>.py
# with the default cap. For full:
uv run --directory mcp/scrapling-uv-mcp python scripts/<name>.py --all
```

Show the user: total record count, per-category/section spread, date range,
sample record. Confirm it looks right before registering. Fix and re-run if
dates are missing (try the URL token), counts look wrong, or a section came
back empty (often a filter bug — see the MOA case where `./nszd_1/*.htm` links
were dropped by an over-narrow URL filter).

### 6. Register into the daas database

All writes hit the shared `mcp/daas.db`. Three commands total.

**6a. Category** — find or create one so the datasource lands in the tree:

```
mcp__daas-mcp__get_category_tree()              # look for an existing fit, e.g. "Web Scraw" / "网页抓取"
mcp__daas-mcp__create_category(name="网页抓取", label="Web Scraw", parent_id=null)  # if none fits
```
Keep the `category_id`.

**6b. `sources` row** — via the MCP tool. The MCP writes the `sources` table
(NOT the legacy `datasources` table — they're different things). Pass the
manifest's full self-describing blob as `config_json`:

```python
# In Python (or compose the call manually):
from <name> import MANIFEST
mcp__daas-mcp__create_datasource(
  name=MANIFEST.name,
  label=MANIFEST.label,
  description=MANIFEST.description,
  url=MANIFEST.url,
  config_json=MANIFEST.to_config_json(),
  category_id=<from 6a>,
  enabled=true,
)
```
If composing the call by hand, take `config_json` from `MANIFEST.to_config_json()`
— don't hand-roll the JSON.

**6c. Columns + scraw recipe** — one command, reads the MANIFEST:

```bash
python3 mcp/scrapling-uv-mcp/scripts/register.py <name>
# preview only:
python3 mcp/scrapling-uv-mcp/scripts/register.py <name> --check
```

`register.py` writes the N `datasource_columns` rows and upserts the
`scraw_configs` recipe. Idempotent — safe to re-run after the source row exists.
It handles the `sources`-vs-`datasources` lookup and the stale-FK gotcha so
you don't have to.

**6d. (optional) Form + section** — if the source has a form/section structure
(like SEC filings have 10-K/Item-7), register the extraction routing grammar:

```
mcp__daas-mcp__add_form(source_name="<name>", form_type="<e.g. 通知公告>", label="...")
mcp__daas-mcp__add_section(form_id=<id>, section_name="<section>",
                           instruction="mcp=scrapling-uv tool=scripts/<name>.py param=k=v ...")
```
Skip if the source is a flat list with no forms.

### 7. Report

Tell the user: datasource name + id, category path, column count, scraper path,
record count + date range from the verified run, and how to re-run
(`uv run --directory mcp/scrapling-uv-mcp python scripts/<name>.py [--all]`).

## Tools you use

- **`fd-daas-scrapling-official`** (skill) — authors the scraper script.
- **`mcp/scrapling-uv-mcp/scripts/scraw_contract.py`** — the stable contract
  (`ScrawManifest`, `ScrawColumn`, `ScrawArchive`). Every scraper imports it
  and defines a module-level `MANIFEST`.
- **`mcp/scrapling-uv-mcp/scripts/register.py`** — one-shot registrar. Reads
  `MANIFEST` from `scripts/<name>.py` and writes `datasource_columns` +
  `scraw_configs` idempotently.
- **`mcp__daas-mcp__*`** (MCP) — `get_category_tree`, `create_category`,
  `create_datasource`, `add_form`, `add_section`.

The skill's older `scripts/register_columns.py` is retained for backward
compatibility but is **superseded by `register.py`** — it queries the wrong
table (`datasources` instead of `sources`) and trips a stale FK. Don't use it
for new scripts.

## Guardrails

- Only scrape content you're authorized to access; respect robots.txt and ToS.
- Add `download_delay` and a page cap for large crawls — never crawl unbounded
  by default. The 50-page default cap is non-negotiable unless the user says
  `--all`.
- Verify before registering. A datasource row pointing at a broken/empty
  scraper is worse than no row.
- Be honest about coverage: if a section came back empty, the sub-URLs need
  JS, or the archive is AJAX-fed, say so — don't register a datasource that
  quietly returns partial data.

## Worked example (proven)

`https://www.moa.gov.cn/gk/` → user wanted the full archive, not just the
landing preview.

- Discovery: landing `/gk/` is static (10 category blocks, ~6 docs each). The
  deep archive lives at `/govpublic/1/2/<id>/index.htm` → `index_2.htm` …
  (16/page, 404 on overflow). 24 departments.
- Columns: `department`, `department_id`, `title` (`a@title`), `date`
  (`url:re:t(\d{8})_`), `url` (`a@href`, primary key).
- Scraper: `mcp/scrapling-uv-mcp/scripts/moa_govpublic_archive.py`, paginates
  all 24 departments, default cap, `--all` for full.
- Verified: 10,803 records, 1980→2026, 0 missing dates.
- Registered: `moa_govpublic_archive` datasource + 5 columns + category +
  scraw recipe.

The lesson from that run: the `/govpublic/` grid looked empty because it was a
frameset — the real list was one level deeper at `/govpublic/1/2/<id>/`. Always
dig one level past the nav shell before concluding a section is AJAX-fed.
