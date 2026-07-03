## Context

`cnreport-mcp` exposes six tools (`list_outline`, `extract_section`, `ai_extract`, `index_records`, `search_reports`, `delete_index`) for ingesting and querying Chinese A-share annual reports (年度报告). `extract_section` already implements the section-get ability — given a source (URL or path) and a selector (title / regex / ordinal), it returns the body text of the matched outline node.

`daas-mcp`'s `seed_external_mcps.py` registers four sibling MCPs (`edgar`, `edinet`, `yfinance`, `cnstats`) as datasources with categories, forms, sections, and a `core` collection, routing every section to an upstream MCP tool via the grammar `mcp=… tool=… param=k=v`. cnreport is conspicuously absent: the section-get ability exists but is invisible to anyone browsing the unified registry.

This change closes that gap by treating cnreport like edgar/edinet — a filings datasource with one form (`Annual-Report`) whose sections are the standard 年报 sections, each pre-bound to `extract_section` with the section selector baked in and the source left for the agent to supply.

## Goals / Non-Goals

**Goals:**
- Make Chinese 年度报告 sections discoverable through the same daas-mcp surface (`list_sources`, `search_datasources`, `list_collection`) used for US 10-Ks and Japanese 有価証券報告書.
- Keep the seed script idempotent, dry-runnable, and unseedable for cnreport rows on the same terms as the existing four sources.
- No changes to `cnreport-mcp` itself — the registry simply routes to its existing `extract_section` tool.

**Non-Goals:**
- Adding new tools to `cnreport-mcp`. `extract_section` already covers the section-get ability the daas routing needs.
- Discovering the report URL automatically. The agent supplies `source` (URL or path) — same pattern as `edgar`'s `ticker_or_cik=<ask-agent>`.
- Catalogue of every possible 年报 sub-section. The seed lists the nine standard top-level (节) sections; sub-sections remain reachable via the agent calling `extract_section` with a more specific selector.
- Per-year forms. One `Annual-Report` form covers all years; year is provenance metadata the agent can pass through as an optional param.

## Decisions

### Decision 1: Reuse `extract_section`, do not add a new tool

The user asked to "add the section-get ability to cnreport-mcp", but inspection shows `extract_section` already implements exactly that: selector-based outline lookup → body text slice. Adding a `get_section` alias would duplicate behavior with no new capability. We register the seed routes directly against `extract_section`.

**Alternative considered:** add a thin `get_section(source, selector)` wrapper that omits the DB writes `extract_section` performs (`upsert_document`, `upsert_section`). Rejected — those writes are provenance metadata, not state mutations that would surprise a read-side caller, and matching the existing tool surface keeps the seed simple.

### Decision 2: One `Annual-Report` form, not one form per year

EDGAR uses one form per filing type (10-K, 10-Q, 8-K, 4) because those are distinct schemas. Chinese 年度报告 has one schema; the year is just a value. A single `Annual-Report` form with year-agnostic sections mirrors `yfinance`'s `default` form decision and keeps the registry shallow.

**Alternative considered:** one form per year (`Annual-Report-2023`, `Annual-Report-2024`, ...). Rejected — explodes the form count without distinguishing behavior, and the agent already supplies the source URL which encodes the year.

### Decision 3: Standard 年报 section list

The CSRC-mandated structure for A-share 年度报告 (per 上市公司年度报告内容与格式准则, currently 编号第2号) has ten 节 (sections). The seed includes the nine canonical body sections, omitting `董事会报告` because it was folded into `管理层讨论与分析` in the post-2017 format and most modern reports use only the latter:

1. 重要提示、目录及释义
2. 公司简介和主要财务指标
3. 管理层讨论与分析
4. 公司治理
5. 环境与社会责任
6. 重要事项
7. 股份变动及股东情况
8. 财务报告
9. 其他报告 (董事、监事、高级管理人员和员工情况 + 其他备查文件)

Each section's `instruction` pre-binds `selector=<section-title-prefix>` so an agent that picks "管理层讨论与分析" routes through `extract_section` with that exact selector — no fuzzy-matching required.

**Alternative considered:** dump all 三级 sub-sections into the registry (e.g. `1.公司业务概要`, `2.报告期内公司从事的主要业务` under MD&A). Rejected — the registry would balloon to ~50 sections per source and most sub-sections are recoverable by passing a more specific selector to `extract_section` at call time.

### Decision 4: Selector pre-binding uses the title prefix

`extract_section` already accepts a regex / exact title / ordinal. The seed stores the Chinese section title (without leading `第N节` numbering) as the selector, e.g. `param=selector=管理层讨论与分析`. `extract_section`'s `resolve_selector` falls back to a regex search if exact title fails, so partial titles match the body heading even when the report's outline uses `第三节 管理层讨论与分析` and the title alone.

### Decision 5: New category leaf `CN-Cninfo` under `Filings`

Symmetric with `US-SEC` (EDGAR) and `JP-EDINET`. Cninfo (巨潮资讯网) is the de-facto disclosure portal for Chinese A-share annual reports, so the leaf name follows the existing source-portal naming convention.

### Decision 6: One `core` collection item from cnreport

Pick `管理层讨论与分析` — same role as `Item 7 MD&A` (EDGAR) and the equivalent narrative section in EDINET 120 documents. Keeps `core` a balanced narrative-heavy baseline rather than a financials-only view.

## Risks / Trade-offs

- **Risk:** The CSRC format spec evolves and section names drift (e.g. ESG section renames). → Mitigation: section selectors are pre-bound to titles, not ordinals, and `extract_section` already falls back to regex matching, so minor title drift still resolves. The seed is single-source-of-truth and easy to edit when CSRC publishes a new template.
- **Risk:** Some PDFs use scanned (image-only) pages, defeating `pypdf` text extraction inside `cnreport-mcp`. → Out of scope for this change; surfaces as an empty-body error from `extract_section`, same as before.
- **Trade-off:** `Annual-Report` is the only form. Quarterly / 半年报 / 临时公告 are not surfaced. → Acceptable for the first registry pass; can be added later without touching the spec for the annual report case (`Quarterly-Report` would be additive, not modifying).
- **Risk:** `OWNED_SOURCES` growing to four entries means `--unseed` is now responsible for cleaning one more datasource. → Mitigation: the existing loop iterates the tuple; adding cnreport to the tuple plus a one-line guard in the category cleanup is enough. `PROTECTED_SOURCES` is unchanged.

## Migration Plan

1. Update `seed_external_mcps.py` with the new constants and seed/unseed logic (single file).
2. Run `--dry-run` against `mcp/daas.db` to confirm planned writes.
3. Run the seed against `mcp/daas.db` (idempotent — safe even if previous seeds have run).
4. Verify `list_sources`, `get_category_tree`, `list_collection("core")`, and `search_datasources(source_name="cnreport", ...)` reflect the new rows.
5. Rollback: `--unseed` removes the new rows and the `CN-Cninfo` category leaf; protected sources remain untouched.
