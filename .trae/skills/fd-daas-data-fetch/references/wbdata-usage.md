# wbdata — World Bank Data (world_bank_data package)

Source name: `wbdata`. Wraps the [`world_bank_data`](https://github.com/mwouts/world_bank_data)
PyPI package, which queries the World Bank Open Data API. Curated to ~20 key
indicators (GDP, population, trade, education, health, environment) refreshed
**yearly**. Entities are 30 major economies; each country's
`identifier_in_source` is its ISO-3 code.

## 1. Install / environment

The adapter lives in the shared `daas-agent-harness` CLI. From the repo root:

```bash
cd daas-agent-harness
uv sync --extra wbdata        # installs world_bank_data
```

If `uv sync` fails resolving unrelated extras (e.g. a yanked `wbgapi`), install
just the data library into the venv directly:

```bash
uv pip install world_bank_data
```

## 2. Run the CLI

Entry command (from `daas-agent-harness/`):

```bash
uv run python -m cli_anything.daas search wbdata          # list wbdata functions
uv run python -m cli_anything.daas describe wbdata_ny_gdp_mktp_cd
uv run python -m cli_anything.daas call wbdata_ny_gdp_mktp_cd country=USA mrv=3
```

Core subcommands: `search <term>`, `describe <function>`, `call <function> key=value ...`.

## 3. Load this source into the DB

**Step 3a — seed (offline):** load the portable registry into `mcp/daas.db`
(idempotent — re-runs upsert). This registers the `wbdata` source, 20 curated
functions (each `frequency='yearly'`), 30 country entities, and 3 indicator rules:

```bash
uv run --directory mcp/daas-mcp \
  python .trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py \
  .trae/skills/fd-daas-data-fetch/references/wbdata.registry.json
```

Add `--dry-run` to preview.

**Step 3b — full catalog (requires network):** the World Bank API exposes
~16,000 indicators, far more than the 20 curated above. To make the entire
catalog searchable in the DB, run the catalog loader once on a machine with
access to `api.worldbank.org`:

```bash
uv pip install world_bank_data   # into the daas-mcp venv if not present
uv run --directory mcp/daas-mcp \
  python .trae/skills/fd-daas-data-fetch/scripts/load_wbdata_catalog.py
```

This calls `world_bank_data.get_indicators()` and bulk-upserts one `wbdata_*`
function per indicator (idempotent). After it runs, `search_functions` returns
matches across the full ~16k-indicator catalog, not just the 20 curated ones.
The adapter's `fetch()` already works for any indicator code, so no further
setup is needed to call a non-curated indicator by name.

## 4. Search functions through the database

Via the daas-mcp tool:

```python
search_functions(query="gdp", source="wbdata")
get_function_detail("wbdata_ny_gdp_mktp_cd")   # includes frequency
```

Direct SQL on `mcp/daas.db`:

```sql
SELECT f.name, f.label, f.frequency, s.name AS source
FROM daas_functions f
JOIN sources s ON s.id = f.source_id
WHERE s.name = 'wbdata';

-- Entities covered by wbdata, with their source lookup code:
SELECT e.code, e.name, l.identifier_in_source
FROM entities e
JOIN entity_datasource_links l ON l.entity_id = e.id
JOIN sources s ON s.id = l.source_id
WHERE s.name = 'wbdata';
```

## 5. Worked example

Fetch the last 3 years of GDP (current US$) for the United States. The entity
`USA` has `identifier_in_source = "USA"` (ISO-3), passed as the `country` param:

```bash
uv run python -m cli_anything.daas call wbdata_ny_gdp_mktp_cd country=USA mrv=3
```

Expected output shape (DataFrame):

| country      | country_code | year | value           |
|--------------|--------------|------|-----------------|
| United States| USA          | 2021 | 2.33e+13        |
| United States| USA          | 2022 | 2.54e+13        |
| United States| USA          | 2023 | 2.74e+13        |

Columns: `country` (name), `country_code` (ISO-3), `year`, `value` (indicator value).
