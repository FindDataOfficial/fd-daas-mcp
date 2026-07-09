# Per-source artifacts (contract)

This directory holds two artifacts per source, both produced by the
`fd-daas-cli-datasource-entities-builder` skill and consumed by the
`fd-daas-data-fetch` skill:

| File | Purpose |
|---|---|
| `<source>.registry.json` | Portable machine-loadable registry: datasource + functions + entities + indicator rules. Loaded into `mcp/daas.db` by `../scripts/load_registry_json.py`. |
| `<source>-usage.md` | Human/agent run instructions: how to install, run the CLI, search the DB, and one worked `call` example. |

---

## `<source>.registry.json` schema

```json
{
  "schema_version": 1,
  "source": {
    "name": "<source>",
    "label": "<Label>",
    "description": "...",
    "url": "https://...",
    "config": {},
    "enabled": true,
    "score": 0.8
  },
  "functions": [
    {
      "name": "<source>_<func>",
      "label": "...",
      "description": "...",
      "category": "Macro",
      "parameters": [{"name": "series_id", "type": "str", "required": true, "description": "..."}],
      "output_type": "DataFrame",
      "frequency": "quarterly",
      "columns": [{"name": "date", "type": "str", "description": "...", "nullable": false}]
    }
  ],
  "entities": [
    {
      "entity_type": "country",
      "code": "US",
      "name": "United States",
      "ticker": null,
      "exchange": null,
      "country_code": "US",
      "isin": null,
      "aliases": ["USA"],
      "status": "active",
      "identifier_in_source": "US"
    }
  ],
  "indicator_rules": [
    {
      "name": "us_gdp_level",
      "datasource": "<source>",
      "function_name": "<source>_gdp",
      "source_table": "<source>_gdp",
      "date_column": "date",
      "value_column": "value",
      "op": "identity",
      "params_json": {},
      "indicator_name": "gdp_level",
      "enabled": true
    }
  ]
}
```

### Field rules
- `source.name` is the primary key; must match the CLI module `cli_anything.<source>` and the function-name prefix `<source>_`.
- `functions[].name` MUST be namespaced `<source>_*` and match what the `SourceAdapter.discover()` returns.
- `functions[].frequency` is required — set from the source's real refresh cadence: `daily` | `weekly` | `monthly` | `quarterly` | `yearly` | `realtime` | `irregular`.
- `entities[].identifier_in_source` is the value to plug into this source's lookup for that entity (e.g. `US` for FRED, `AAPL` for yfinance, `600519` for cnreport). The loader writes it to `entity_datasource_links.identifier_in_source`.
- `entities` natural key is `(entity_type, code)` — re-running the loader updates the same row.
- `indicator_rules` is optional — omit the key if the source defines no indicators. `indicator_rules[].name` is unique.
- The loader upserts everything idempotently; re-running is safe.

### Loading
```bash
uv run --directory mcp/daas-mcp \
  python .trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py \
  .trae/skills/fd-daas-data-fetch/references/<source>.registry.json
```
Add `--dry-run` to preview; `--env <path>` to use a specific `.env`.

---

## `<source>-usage.md` required sections

A valid usage doc MUST contain, in this order:

1. **Install / environment** — `uv sync` + the optional extra/package providing the underlying data library.
2. **Run the CLI** — entry command + core subcommands (`search`, `describe`, `call`).
3. **Load this source into the DB** — the `load_registry_json.py` one-liner above.
4. **Search functions through the database** — `search_functions(query="...", source="<source>")` tool call + a direct-SQL snippet on `mcp/daas.db` (include `frequency`).
5. **Worked example** — one representative `call` invocation: function name, params (showing how `identifier_in_source` is passed), and expected output shape.

### Hard constraints
- DO NOT enumerate all indicators/functions — the registry JSON + DB are the source of truth. One worked example is enough.
- DO NOT include setup for unrelated sources.
- Keep it under ~120 lines.

## Filename convention
- Registry JSON: `<source>.registry.json`
- Usage doc: `<source>-usage.md`

where `<source>` matches `sources.name` in `mcp/daas.db` and the `cli_anything.<source>` package name. Example: `fred.registry.json`, `fred-usage.md`.
