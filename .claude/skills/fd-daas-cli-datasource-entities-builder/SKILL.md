---
name: fd-daas-cli-datasource-entities-builder
description: "Scans a GitHub repo, Python package, or local folder and builds a daas CLI + datasource + entity/indicator registry for it — reuses an existing CLI if present, else scaffolds a new Python project, registers everything into a portable JSON, and writes a usage doc. Invoke when the user wants to wrap a data library/source into a searchable daas CLI with entities and indicators."
---

# fd-daas-cli-datasource-entities-builder

Turn a data source (GitHub repo / PyPI package / local folder) into a **daas CLI + datasource + entity/indicator registry**: a runnable Click CLI, a registered searchable datasource, and a portable JSON file capturing the datasource, its functions, the entities it covers, and any indicator rules. If the target already ships a usable CLI, reuse it; otherwise scaffold a new Python project around it.

## Architecture you are plugging into

Two layers coexist — understand both before building:

1. **MCP layer** — `mcp/<source>-mcp/`: FastMCP servers. `mcp/daas-mcp/` is the central registry/search/fetch MCP. Its tools `search_functions`, `get_function_detail`, `fetch_data` (see [daas_tools.py](file:///Users/chengsishi/code/cli-anything/mcp/daas-mcp/daas_tools.py)) query the canonical registry.
2. **CLI harness layer** — `<source>-agent-harness/cli_anything/<source>/`: Click CLIs. Reference implementation: [daas-agent-harness/cli_anything/daas/](file:///Users/chengsishi/code/cli-anything/daas-agent-harness/cli_anything/daas/cli.py). Each source implements a `SourceAdapter` (discover/fetch/columns) and is routed by `SourceRouter`.

**Canonical registry DB**: `mcp/daas.db` (URL from `DAAS_DATABASE_URL` in root `.env`, currently `sqlite:///mcp/daas.db`). Relevant tables:
- `sources` (DaasSource): `name`, `label`, `description`, `url`, `enabled`, `config`, `category_id`, `score`.
- `daas_functions` (DaasFunction): `source_id`, `name`, `label`, `description`, `category`, `parameters`(JSON), `output_type`, **`frequency`** (refresh cadence). Unique `(source_id, name)`.
- `entities` (Entity): `entity_type` (`stock`|`country`), `code`, `name`, `ticker`, `exchange`, `country_code`, `isin`, `aliases`(JSON), `status`. Unique `(entity_type, code)`.
- `entity_datasource_links`: M:N entity↔source, with `identifier_in_source` (the value to plug into that source's lookup) and `coverage`.
- `indicator_rules` (IndicatorRule): `name`, `datasource` (soft ref → `sources.name`), `function_name`, `source_table`, `date_column`, `value_column`, `op`, `params_json`, `indicator_name`, `enabled`. Unique `name`.

Models: [mcp/models/models.py](file:///Users/chengsishi/code/cli-anything/mcp/models/models.py). Registration service: [mcp/daas-mcp/registry_service.py](file:///Users/chengsishi/code/cli-anything/mcp/daas-mcp/registry_service.py).
`frequency` values: `daily` | `weekly` | `monthly` | `quarterly` | `yearly` | `realtime` | `irregular`.

## Inputs to confirm first

- **target**: a GitHub URL, a PyPI package name, or a local folder path.
- **source name**: short slug used everywhere (DB `sources.name`, CLI module `cli_anything.<source>`, function name prefix `<source>_*`). Lowercase, underscores, e.g. `fred`, `simfin`.
- **frequency**: default refresh cadence for the source's data.
- **entities**: which entities this source covers (stocks/countries) and, for each, the `identifier_in_source` the source's lookup expects.

## Step 1 — Scan the target and detect an existing CLI

Inspect the target for an existing CLI before scaffolding anything:
- `pyproject.toml` / `setup.py` / `setup.cfg` → `[project.scripts]` or `entry_points` console scripts.
- A `__main__.py`, or a module with `click` / `typer` / `argparse` + `if __name__ == "__main__"`.

**Decision**:
- **Existing CLI is usable** (takes a function/endpoint name + params, returns data) → reuse it. Do NOT scaffold a new project. Skip to Step 3 (write a thin `SourceAdapter` that shells out to / imports the existing CLI) and Step 4.
- **No CLI, or CLI is not data-fetch oriented** → proceed to Step 2 and scaffold.

## Step 2 — Scaffold a new Python project (only if no usable CLI)

Create a harness package mirroring the reference layout. Root: `<source>-agent-harness/` (sibling of `daas-agent-harness/`).

```
<source>-agent-harness/
├── pyproject.toml
└── cli_anything/<source>/
    ├── __init__.py
    ├── __main__.py            # `from cli_anything.<source>.cli import cli; cli()`
    ├── cli.py                 # Click group: list-sources, search, describe, call, repl
    ├── core/
    │   ├── __init__.py
    │   ├── database.py        # Database singleton → mcp/daas.db
    │   ├── models.py          # Source / Function / FunctionColumn ORM
    │   ├── registry.py        # search_functions, get_function_info, list_sources
    │   └── migrate_registry.py
    ├── sources/
    │   ├── __init__.py
    │   ├── base.py            # SourceAdapter ABC (copy from daas-agent-harness)
    │   ├── router.py          # SourceRouter — add "<source>_" to SOURCE_PREFIXES
    │   ├── config.py          # load_sources(), get_adapter(), SourceConfig
    │   └── <source>_source.py # the adapter you implement (Step 3)
    ├── utils/
    │   ├── __init__.py
    │   └── output.py          # format_output(result, json_output)
    └── tests/
        └── test_core.py
```

`pyproject.toml` template (see [daas-agent-harness/pyproject.toml](file:///Users/chengsishi/code/cli-anything/daas-agent-harness/pyproject.toml)):
```toml
[project]
name = "cli-anything-<source>"
version = "0.1.0"
description = "CLI for <source> data access"
requires-python = ">=3.10"
dependencies = ["click>=8.0", "pandas>=1.0", "sqlalchemy>=1.4", "pyyaml>=6.0"]

[project.optional-dependencies]
<source> = ["<underlying-package>"]
repl = ["prompt_toolkit>=3.0"]
dev = ["pytest>=8.0"]

[project.scripts]
cli-anything-<source> = "cli_anything.<source>.cli:cli"

[tool.setuptools.packages.find]
include = ["cli_anything.*"]
```

Use `uv` for env management: `uv sync`, `uv run python -m cli_anything.<source>`.

## Step 3 — Implement the SourceAdapter

In `sources/<source>_source.py`, subclass `SourceAdapter` (see [base.py](file:///Users/chengsishi/code/cli-anything/daas-agent-harness/cli_anything/daas/sources/base.py)) and implement:

- `name` / `label` / `description` / `url` / `enabled` properties.
- `is_available()` → check the underlying package imports.
- `discover()` → `list[dict]`, one per function: `{name, category, description, parameters: [{name,type,required,description}], columns: [{name,type,description,nullable}]}`. Names MUST be namespaced: `<source>_<func>`.
- `fetch(function_name, **params)` → return a pandas DataFrame (preferred) or dict/list.
- `columns(function_name)` → column metadata.

Register the adapter in `sources/config.py` and add the `"<source>_"` prefix to `SourceRouter.SOURCE_PREFIXES` in [router.py](file:///Users/chengsishi/code/cli-anything/daas-agent-harness/cli_anything/daas/sources/router.py).

If reusing an existing CLI (Step 1 reuse path), `fetch()` invokes it (subprocess or in-process import) and normalizes output to a DataFrame.

## Step 4 — Produce the portable registry JSON (REQUIRED output)

Write a JSON file to **`.trae/skills/fd-daas-data-fetch/references/<source>.registry.json`**. This is the portable artifact the `fd-daas-data-fetch` skill loads into `mcp/daas.db` (via its `scripts/load_registry_json.py`) before fetching. Schema (see [references/README.md](file:///Users/chengsishi/code/cli-anything/.trae/skills/fd-daas-data-fetch/references/README.md)):

```json
{
  "schema_version": 1,
  "source": {
    "name": "<source>", "label": "<Label>", "description": "...",
    "url": "https://...", "config": {}, "enabled": true, "score": 0.8
  },
  "functions": [
    {
      "name": "<source>_gdp", "label": "GDP", "description": "...",
      "category": "Macro", "parameters": [{"name": "series_id", "type": "str", "required": true, "description": "..."}],
      "output_type": "DataFrame", "frequency": "quarterly",
      "columns": [{"name": "date", "type": "str", "description": "...", "nullable": false}]
    }
  ],
  "entities": [
    {
      "entity_type": "country", "code": "US", "name": "United States",
      "ticker": null, "exchange": null, "country_code": "US", "isin": null,
      "aliases": ["USA"], "status": "active",
      "identifier_in_source": "US"
    }
  ],
  "indicator_rules": [
    {
      "name": "us_gdp_level", "datasource": "<source>", "function_name": "<source>_gdp",
      "source_table": "<source>_gdp", "date_column": "date", "value_column": "value",
      "op": "identity", "params_json": {}, "indicator_name": "gdp_level", "enabled": true
    }
  ]
}
```

Rules:
- `functions[].name` must be namespaced `<source>_*` and match what `discover()` returns.
- Set `frequency` on every function from the source's real refresh cadence.
- `entities[].identifier_in_source` is the value to plug into this source's lookup for that entity (e.g. `US` for FRED, `AAPL` for yfinance, `600519` for cnreport). Omit `indicator_rules` if the source defines no indicators.
- Do NOT enumerate every function/indicator if the source has hundreds — include the full function list (it's machine-loaded), but keep `entities` to the ones this source actually covers.

## Step 5 — Write the usage doc (REQUIRED output)

Write a Markdown file to **`.trae/skills/fd-daas-data-fetch/references/<source>-usage.md`**. Follow the format in [references/README.md](file:///Users/chengsishi/code/cli-anything/.trae/skills/fd-daas-data-fetch/references/README.md).

**Hard constraints for the doc**:
- DO NOT list all indicators/functions. The registry JSON + DB are the source of truth.
- DO include:
  1. **How to run the CLI** — env setup (`uv sync`, optional-extra install), the entry command, and the core commands (`search`, `describe`, `call`).
  2. **How to load this source into the DB** — the one-liner:
     `uv run --directory mcp/daas-mcp python .trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py .trae/skills/fd-daas-data-fetch/references/<source>.registry.json`
  3. **How to search functions through the database** — the `search_functions` / `get_function_detail` MCP tools and a direct-SQL snippet against `mcp/daas.db`.
  4. A worked `call` example with one representative function (name + params), including how an entity's `identifier_in_source` is passed as a param.

## Step 6 — Validate

1. `uv run python -m cli_anything.<source> search <term>` returns results.
2. Load the JSON into the DB (the Step 5.2 one-liner) and confirm: `search_functions(query="<source>")` returns the new functions (each with `frequency`), and the entities appear in `entities` with links to this source.
3. `fetch_data("<source>_<func>", '{"...":"..."}')` (daas-mcp tool) returns a DataFrame, OR `... call <source>_<func> key=value` from the CLI does.
4. Both `references/<source>.registry.json` and `references/<source>-usage.md` exist and match the contract.

Report back: source name, # functions registered, frequency distribution, # entities + links, # indicator rules, CLI run command, and the paths to the JSON + usage doc.
