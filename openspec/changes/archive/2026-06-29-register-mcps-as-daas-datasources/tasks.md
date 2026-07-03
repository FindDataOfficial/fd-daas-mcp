## 1. Seed script scaffolding

- [x] 1.1 Create `mcp/daas-mcp/seed_external_mcps.py` with a `__main__` block, `argparse` for `--unseed` and `--db-url` flags (defaults to `DAAS_DATABASE_URL`), and a top-of-file docstring explaining idempotency and routing-grammar
- [x] 1.2 Import `RegistryService` from `registry_service.py` and `Database` from `daas_database.py`; bootstrap a single session reused across the run
- [x] 1.3 Add a small `_get_or_create_*` helper per entity type (`source`, `category`, `form`, `section`, `collection`, `collection_item`) — each looks up by natural key and only calls the service's `create_*` method when missing; for `section` also updates `instruction` if it differs
- [x] 1.4 Define a module-level `SEED_MARKER` tuple of all natural keys this seed owns (used by `--unseed` to delete only its own rows)

## 2. Category tree data

- [x] 2.1 Define a `CATEGORIES` literal: top-level `Filings`, `Market-Data`, `Macro`; second-level `Filings → US-SEC`, `Filings → JP-EDINET`, `Market-Data → Global`, `Macro → China`
- [x] 2.2 Call `_get_or_create_category` for each, capturing `id`s into a dict keyed by name path (e.g. `"Filings/US-SEC"`)

## 3. EDGAR datasource

- [x] 3.1 `_get_or_create_source` for `edgar` (label, description, url=https://www.sec.gov/edgar, category=`Filings/US-SEC`)
- [x] 3.2 Define `EDGAR_FORMS` constant: forms `10-K`, `10-Q`, `8-K`, `4`
- [x] 3.3 Define `EDGAR_SECTIONS_10K` constant: at minimum `Item 1 Business`, `Item 1A Risk Factors`, `Item 7 MD&A`, `Item 7A Quantitative and Qualitative Disclosures About Market Risk`, `Item 8 Financial Statements and Supplementary Data`; each instruction = `mcp=edgartools-mcp tool=get_filing param=form=10-K param=ticker=<ask-agent> param=section=<this-section-name>`
- [x] 3.4 Define `EDGAR_SECTIONS_10Q`, `EDGAR_SECTIONS_8K`, `EDGAR_SECTIONS_4` (smaller, e.g. `Item 2 MD&A` for 10-Q; `Item 1.01`, `Item 2.02`, `Item 5.02`, `Item 8.01` for 8-K; `Transactions` for Form 4)
- [x] 3.5 Add a `Financials` form (or extra sections under `10-K`) routed at `get_financials` (statement=`income_statement` / `balance_sheet` / `cashflow`) and `Insider-Trades` routed at `get_insider_trades` — pick the form-vs-section split here and stick with it across the file

## 4. EDINET datasource

- [x] 4.1 `_get_or_create_source` for `edinet` (label, description, url=https://disclosure.edinet-fsa.go.jp/, category=`Filings/JP-EDINET`)
- [x] 4.2 Define `EDINET_FORMS` constant with form_type and human label for each of: `120` 有価証券報告書, `130` 四半期報告書, `140` 半期報告書, `150` 臨時報告書, `160` 訂正届出書, `170` 自己株式取得状況, `180` 親会社等状況報告書, `350` 大量保有報告書, `360` 公開買付届出書
- [x] 4.3 For each form, add sections: a `Document` section routed at `get_document` with `param=doc_type_code=<form_type>`, a `Listing` section under form `120` routed at `list_documents`, and (under `120` only) a `Lookup` section routed at `get_entity`

## 5. yfinance datasource

- [x] 5.1 `_get_or_create_source` for `yfinance` (label, description, url=https://finance.yahoo.com/, category=`Market-Data/Global`)
- [x] 5.2 Add the single `default` form
- [x] 5.3 Define `YFINANCE_SECTIONS` constant grouping yfinance tools: `Search`/`Download` (instruction routes `call_yfinance_function` with `name=search` or `name=download`), `Price-History`, `Fundamentals`, `Options`, `Holders`, `News`; each section's instruction is `mcp=yfinance-mcp tool=call_yfinance_function param=name=<the-fn-name> param=params_json=<ask-agent>` — pick one representative `name` per section, document the rest in the section description

## 6. cnstats datasource

- [x] 6.1 `_get_or_create_source` for `cnstats` — re-use existing row by `name='cnstats'`; only set `category_id` to `Macro/China`; leave label/description/url untouched
- [x] 6.2 Add the single `default` form
- [x] 6.3 Define `CNSTATS_SECTIONS` constant grouping cnstats tools: `Search`, `Function-Info`, `Categories`, `Call` — each routed at the corresponding cnstats-mcp tool (`search_functions`, `get_function_info`, `list_categories`, `call_cnstats_function`)

## 7. Core collection

- [x] 7.1 `_get_or_create_collection` for `core`
- [x] 7.2 Add items: `(edgar, "Item 1A Risk Factors" under 10-K)`, `(edgar, "Item 7 MD&A" under 10-K)`, `(edinet, "Document" under 120)`, `(yfinance, "Price-History")`, `(yfinance, "Fundamentals")`, `(cnstats, "Categories")` — assert each item resolves before insert

## 8. `--unseed` mode

- [x] 8.1 Branch on `args.unseed`: iterate `SEED_MARKER` in reverse-dependency order (collection_items → collection → sections → forms → sources(edgar/edinet/yfinance) → unset `category_id` on cnstats → categories)
- [x] 8.2 For the `cnstats` row: never call `delete_datasource`; only delete the forms/sections this seed created under it and null out the `category_id` it set
- [x] 8.3 Guard against deleting `ckan`/`cnstats`/`worldbank` source rows themselves — explicit allow-list of source names this seed may delete (`edgar`, `edinet`, `yfinance` only)

## 9. Verification helpers

- [x] 9.1 Add a `--dry-run` mode that prints the plan (creates / updates / no-ops per entity) without writing
- [x] 9.2 Add a final summary print after each real run: counts per table (`sources +N`, `forms +N`, `sections +N`, `collection_items +N`) and an exit-status line — useful for CI logs and re-run sanity checks
- [x] 9.3 Add a `routing-grammar` self-validator: before inserting any section, parse its `instruction` and assert it matches `mcp=… tool=… (param=k=v )*` — raises on malformed instructions so typos in the seed source are caught before they hit the DB

## 10. Manual verification on live `daas.db`

- [x] 10.1 Back up `mcp/daas.db` (cp), run `uv run python mcp/daas-mcp/seed_external_mcps.py` once, confirm exit 0 and summary numbers match expectation
- [x] 10.2 Run it a second time; assert summary reports `+0` everywhere (idempotency)
- [x] 10.3 Call `list_sources`, `get_category_tree`, `search_datasources(form="10-K")`, `search_datasources(source_name="edinet", form="120")`, `list_collection(collection_name="core")` — every call returns non-empty, well-formed results
- [x] 10.4 Run `uv run python mcp/daas-mcp/seed_external_mcps.py --unseed`; assert `ckan`/`cnstats`/`worldbank` rows remain and `edgar`/`edinet`/`yfinance` are gone
- [x] 10.5 Re-run the seed and re-verify; restore the backup if any check fails

## 11. Docs

- [x] 11.1 Add a one-line pointer in the `mcp/daas-mcp/` section of `CLAUDE.md`: "Seed external MCPs into the registry with `uv run python mcp/daas-mcp/seed_external_mcps.py` (idempotent; `--unseed` rolls back)."
- [x] 11.2 Run `openspec validate register-mcps-as-daas-datasources --strict` and fix any spec/task issues
