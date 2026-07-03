## Why

`cnreport-mcp` already ships `extract_section`, the section-get ability for Chinese annual reports, but it is invisible inside `daas-mcp`'s unified datasource registry. Agents browsing `list_sources` / `search_datasources` / `list_collection("core")` can find EDGAR 10-K items and EDINET 有価証券報告書 sections, but cannot discover the analogous Chinese 年度报告 sections — they have to know `cnreport-mcp` exists and call it out-of-band. Registering cnreport as a fifth seeded datasource closes that gap and makes filings discovery symmetric across US / Japan / China.

## What Changes

- Register `cnreport` as a new daas-mcp datasource via `mcp/daas-mcp/seed_external_mcps.py`.
- Add a `China` filings category (`Filings → CN-Cninfo`) and assign `cnreport` to it.
- Add a single `Annual-Report` form on `cnreport` covering the standard Chinese annual report (年度报告) section structure: 重要提示·目录·释义 / 公司简介和主要财务指标 / 管理层讨论与分析 / 公司治理 / 环境与社会责任 / 重要事项 / 股份变动及股东情况 / 财务报告 / 其他报告.
- Each section's `instruction` routes to the existing `cnreport-mcp` `extract_section` tool with a pre-filled `selector=<title-prefix>` and `source=<ask-agent>`, following the established routing grammar (`mcp=… tool=… param=k=v`).
- Extend the `core` collection to include at least one cnreport section (e.g. `管理层讨论与分析`).
- Update `--unseed` to symmetrically remove the new cnreport rows + the new `CN-Cninfo` category, preserving the protected-source guard.
- No changes to `cnreport-mcp` itself — `extract_section` already implements the section-get ability the registry routes to.

## Capabilities

### New Capabilities

(none — section-get already exists in cnreport-mcp under `report-outline-extraction`; this change is purely a registry-side wiring.)

### Modified Capabilities

- `external-mcp-datasource-seed`: extends the seed contract from four sibling MCPs to five by adding `cnreport`, its `CN-Cninfo` category leaf, its `Annual-Report` form with standard 年报 sections, an `--unseed` mirror, and at least one entry in the `core` collection.

## Impact

- Code: `mcp/daas-mcp/seed_external_mcps.py` — add cnreport constants (`CNREPORT_SECTIONS`, source/category entries), wire it into `seed()` and `unseed()`, extend the `core` collection items list. `OWNED_SOURCES` grows by one entry.
- Data: `mcp/daas.db` — one new `sources` row (`cnreport`), one new `categories` row (`CN-Cninfo`), one new `datasource_forms` row (`Annual-Report`), ~9 new `datasource_sections` rows, 1 new `datasource_collection_items` row under `core`.
- No schema migration (all tables already exist).
- No new dependencies; seed runs in the existing `daas-mcp` venv.
- Re-running the seed remains a no-op on row counts (existing idempotency requirement extended to cnreport rows).
