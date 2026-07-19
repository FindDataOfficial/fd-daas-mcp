# Add a Personal Datasource

DAAS is designed so you can bring your own data - a **website**, a **document**,
or a **database** - and query it like the built-in sources. Three paths.

## Path A: A website (scrape it)

Use the `fd-daas-scrapling-official` skill, which drives the
[Scrapling](https://github.com/D4Vinci/Scrapling) library directly (anti-bot
bypass, CSS/XPath selectors). In Claude Code:

> Scrape the daily price table from <https://example.com/markets> and persist it to daas.db.

The skill fetches the page, extracts the table, and persists rows to a
`scraw_<slug>` table via `scripts/upsert.py` (which backs up `daas.db` first).
From there it behaves like any source table - compute indicators, add to
collections, put in a research.

!!! note "This is the Scrapling *library*, not the dropped MCP group"
    `fd-daas-scrapling-official` drives Scrapling directly. The old
    `scrapling`/`firecrawl`/`massive` MCP groups were removed - do not reference
    them.

For a heavy recurring crawl, scaffold a full Scrapy project with
`fd-coding-daas-scraw-builder` (scrapy + scrapy-redis + scrapyd + scrapyd-web).

## Path B: A document (PDF / text)

Ingest a local PDF or text with the `fd-daas-pdf` skill / `pdf` MCP group:

```text
pdf_ingest_document(file_path="/path/to/report.pdf")
# or plain text:
pdf_ingest_text(text="...", name="my-notes")
pdf_search_documents(query="what are the main risks", top_k=5)
```

The document is chunked + embedded (sqlite-vec) into `daas.db` and becomes
semantically searchable. For structured extraction from the text, author an
`llm` rule with `fd-daas-rules-creator` and run `daas_run_rule` (results land in
`process_results`).

## Path C: A database (or any Python-callable source)

Register a datasource and link it to entities, then fetch through the dispatch
layer.

```text
daas_create_datasource(name="mydb", label="My Internal DB", url="postgresql://...")
daas_link_entity_datasource(entity_id=123, source_name="mydb", identifier_in_source="AAPL")
```

If your source has a Python library, add a dispatch prefix mapping in
`.claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py` (mirroring the
existing `akshare_`/`yfinance_`/... entries), then resolve + fetch:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve mydb_<func>
```

Persist with `scripts/upsert.py` into a `scraw_<slug>` table.

## Register functions/columns (optional, for catalog browsing)

To make your source browsable in the MCP catalog, register its functions and
columns:

```text
daas_create_datasource(...)
daas_add_form(source_name="mydb", form_type="table")     # or a "form"/"section" structure
daas_add_section(form_id=..., section_name="daily_prices", instruction="...")
```

Then `daas_search_functions`, `daas_search_datasources`, and
`daas_get_entity_coverage` include your source.

## Next

Once your data is in `daas.db`, the rest is the same: compute indicators
([Browse Indicators](browse-indicators.md)), build
[Collections](create-collections.md), or run a
[Research](create-research.md).
