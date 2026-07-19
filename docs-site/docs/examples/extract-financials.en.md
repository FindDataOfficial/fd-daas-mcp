# Extract & Analyze Financial Reports

Pull a financial filing and compute indicators on top - with many indicators
prebuilt. DAAS supports SEC EDGAR (US), EDINET (Japan), and DART (Korea), plus
local PDF/document extraction with semantic search.

## 1. Resolve the filing source

Each filing source has a dispatch prefix:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve edgar_get_filing
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/dispatch.py --resolve edinet_list_documents
```

These print the exact Python import + call shape (e.g.
`edgar.Filing(filing_id)`, `edinet_tools.Entity(code).documents`).

## 2. Fetch the filing (skill)

In Claude Code:

> Fetch Apple's latest 10-K from EDGAR and persist it.

The `fd-daas-fetch-data` skill resolves AAPL -> `edgar` identifier, calls the
`edgar` library, and persists structured rows to a `scraw_<slug>` table (and/or
`process_results` for LLM-extracted sections).

## 3. Extract structured sections (LLM)

For free-text filings, DAAS extracts structured records via an `llm` rule
(`rules.rule_type='llm'`, `target='rows'`) into `process_results`. The
`fd-daas-rules-creator` skill authors the rule; `daas_run_rule` runs it.

```text
daas_test_rule(name="extract_revenue_segments")   # dry-run sample
daas_run_rule(name="extract_revenue_segments")    # persist
```

## 4. Ingest a PDF / document for semantic search

If you have a local PDF (an annual report, a prospectus), ingest it with the
`fd-daas-pdf` skill (backed by the `pdf` MCP group):

```text
pdf_ingest_document(file_path="/path/to/report.pdf")
pdf_search_documents(query="revenue concentration by segment", top_k=5)
```

This chunks + embeds (sqlite-vec) into `daas.db` (`pdf_documents` /
`pdf_chunks` / `pdf_chunks_vec`) and returns ranked chunks with page numbers.

## 5. Compute indicators on top

Once the filing's data is in a `scraw_<slug>` table, compute indicators exactly
like any other series:

```bash
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py <indicator_name>
```

Prebuilt ops: `sma`, `ema`, `rsi`, `pct_change`, `log_return`, `diff`,
`rolling_std`, `rolling_min`, `rolling_max`, `zscore`, `ratio`, `level`. Create
a new indicator rule with `daas_create_indicator` (or the
`fd-daas-indicators-creator` skill) and run it.

## 6. Put it in a research

Bundle the filing extraction + indicators + a dashboard into a research:

```text
research_create(name="aapl-10k-analysis", ...)
research_generate_report(name="aapl-10k-analysis")
```

See [Create a Research](create-research.md).

## Datasource coverage

| Source | Prefix | Region |
| --- | --- | --- |
| SEC EDGAR | `edgar_` | US |
| EDINET | `edinet_` | Japan |
| DART | `dartlab_` (Python 3.12) | Korea |

!!! note "dartlab needs Python 3.12"
    Run dartlab via `uv run --python 3.12 --with dartlab ...` (not a root dep).
