## 1. Seed constants

- [x] 1.1 Add `("CN-Cninfo", "China Cninfo", "Filings")` to `CATEGORIES` in `mcp/daas-mcp/seed_external_mcps.py`
- [x] 1.2 Extend `OWNED_SOURCES` from `("edgar", "edinet", "yfinance")` to include `"cnreport"`
- [x] 1.3 Add a `"cnreport"` entry to `SOURCES` with label `"Chinese Annual Reports"`, description naming `cnreport-mcp` and Cninfo as the upstream source, url `http://www.cninfo.com.cn/`, and category `"CN-Cninfo"`
- [x] 1.4 Define `CNREPORT_FORMS = {"Annual-Report": "年度报告 (A-share Annual Report)"}`
- [x] 1.5 Define `CNREPORT_SECTIONS: list[tuple[str, str]]` listing the 9 standard 年报 sections (`重要提示、目录及释义`, `公司简介和主要财务指标`, `管理层讨论与分析`, `公司治理`, `环境与社会责任`, `重要事项`, `股份变动及股东情况`, `财务报告`, `其他报告`), each paired with an `instruction` string of the form `mcp=cnreport-mcp tool=extract_section param=source=<ask-agent> param=selector=<section-title>`

## 2. Seed wiring

- [x] 2.1 In `seed()`, after the cnstats default form block, add a cnreport block that creates the `Annual-Report` form and iterates `CNREPORT_SECTIONS` calling `goc_section` (use existing helpers — do not bypass `validate_routing`)
- [x] 2.2 Add `("cnreport", "管理层讨论与分析")` to `CORE_ITEMS` so the `core` collection gains a cnreport row
- [x] 2.3 Confirm src loop (`for src_name in ("edgar", "edinet", "yfinance", "cnstats")`) is extended to include `"cnreport"` so the source row is created before forms

## 3. Unseed wiring

- [x] 3.1 Confirm `OWNED_SOURCES` containing `"cnreport"` is sufficient for the existing owned-source deletion loop in `unseed()` to cascade-remove its form + sections + collection items
- [x] 3.2 Verify the existing reversed `CATEGORIES` loop will pick up `CN-Cninfo` for deletion (no special handling needed — leaf-first order is preserved by reversing the insertion list)

## 4. Dry-run + seed verification

- [x] 4.1 Run `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py --dry-run` and confirm the plan lists the new category, source, form, sections, and collection item
- [x] 4.2 Run the seed for real and confirm the printed counts show `+1 sources` (or `~1 updated` on repeat), `+1 categories`, `+1 forms`, `+9 sections`, `+1 collection_items`
- [x] 4.3 Re-run the seed and confirm all `+N` counters print `+0` (idempotent)

## 5. Live verification against daas-mcp tools

- [x] 5.1 `list_sources` returns a row with `name="cnreport"`, non-null `category_id`, and `enabled=True`
- [x] 5.2 `get_category_tree` shows `Filings → CN-Cninfo` with `datasource_count >= 1`
- [x] 5.3 `search_datasources(source_name="cnreport", form="Annual-Report", section="管理层讨论与分析")` returns at least one row whose `instruction` contains `mcp=cnreport-mcp`, `tool=extract_section`, `param=source=<ask-agent>`, and a non-empty `param=selector=`
- [x] 5.4 Every row returned by `search_datasources(source_name="cnreport")` passes `_ROUTING_RE`
- [x] 5.5 `list_collection(collection_name="core")` returns at least one item with `source_name="cnreport"` and a non-orphan section reference

## 6. Unseed rollback

- [x] 6.1 Run `--unseed` and confirm `cnreport`, the `Annual-Report` form, all its sections, the matching `core` collection item, and the `CN-Cninfo` category are removed
- [x] 6.2 Confirm `ckan`, `cnstats`, `worldbank` rows are still present after `--unseed`
- [x] 6.3 Re-run the seed and confirm cnreport rows are recreated identically

## 7. Docs

- [x] 7.1 Update `CLAUDE.md` under `mcp/daas-mcp/` description to mention `cnreport` in the list of MCPs seeded by `seed_external_mcps.py` (one-word change)
