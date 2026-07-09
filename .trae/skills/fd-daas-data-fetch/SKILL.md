---
name: "fd-daas-data-fetch"
description: "Helps find and fetch data using ENTITIES and INDICATORS — resolves an entity + indicator to the right source/function, loads the source's registry JSON into the DB (adding the datasource if missing), prepares the env, and runs the fetch. Invoke when the user wants data for a specific entity/indicator and needs help locating the source, ensuring it's registered, installing deps, and executing the fetch."
---

# fd-daas-data-fetch

Use this when the user wants data tied to an **entity** ("get me Kweichow Moutai's financials", "US GDP", "Apple's 10-K") and/or an **indicator** ("monthly revenue", "GDP growth", "debt-to-equity"). You resolve the entity + indicator to the right source/function, make sure that source is registered in the DB (loading its registry JSON if missing), prepare the environment, and run the fetch.

## How it works

1. **Clarify the data need** — which entity (stock/country, by code/name/ticker) and which indicator (or raw function).
2. **Resolve entity + indicator** against the registry (`mcp/daas.db`).
3. **Ensure the source is registered** — if the datasource isn't in the DB yet, load its registry JSON via the loader script.
4. **Read the per-source usage doc** under `references/` for the matched source.
5. **Prepare the environment** (install deps via `uv`).
6. **Run the fetch** — via the source CLI or the daas-mcp `fetch_data` tool.

## Step 1 — Resolve the entity + indicator

The canonical registry is `mcp/daas.db` (URL from `DAAS_DATABASE_URL` in root `.env`). Key tables:
- `entities` — `entity_type` (`stock`|`country`), `code`, `name`, `ticker`, `exchange`, `country_code`, `aliases`.
- `entity_datasource_links` — for each entity, the `source_id` + `identifier_in_source` (the value to plug into that source's lookup) + `coverage`.
- `indicator_rules` — `name`, `datasource` (→ `sources.name`), `function_name`, `indicator_name`, `op`, `params_json`.
- `daas_functions` — `name`, `source_id`, `parameters`, `frequency`.

**Resolve the entity** (daas-mcp tools or SQL):
```sql
-- sqlite3 mcp/daas.db
SELECT e.entity_type, e.code, e.name, e.ticker, s.name AS source,
       l.identifier_in_source, l.coverage
FROM entities e
JOIN entity_datasource_links l ON l.entity_id = e.id
JOIN sources s ON s.id = l.source_id
WHERE e.code = '600519' OR e.ticker = 'AAPL' OR e.name LIKE '%Moutai%';
```

**Resolve the indicator** → it tells you which datasource + function produces it:
```sql
SELECT name, datasource, function_name, indicator_name, op, frequency
FROM indicator_rules r
LEFT JOIN daas_functions f ON f.name = r.function_name
WHERE r.indicator_name LIKE '%gdp%' OR r.name LIKE '%gdp%';
```
(`frequency` lives on `daas_functions`; join to get it.)

If the user asks for a raw function (not an indicator), search functions directly:
- daas-mcp tool: `search_functions(query="<term>", source=None, limit=20)` → matches name/category/description. See [daas_tools.py](file:///Users/chengsishi/code/cli-anything/mcp/daas-mcp/daas_tools.py).
- `get_function_detail(function_name="<source>_<func>")` → full params + output columns.

Combine: the entity gives you `identifier_in_source` for a source; the indicator gives you the `function_name` on that source. The fetch plugs the identifier into the function's expected param.

## Step 2 — Ensure the source is registered in the DB

Before fetching, confirm the datasource exists in `mcp/daas.db`:
```sql
SELECT id, name, enabled FROM sources WHERE name = '<source>';
```
- If it exists → skip to Step 3.
- If it does NOT exist → the source's data project hasn't been loaded yet. Load its registry JSON (produced by the `fd-daas-cli-datasource-entities-builder` skill) using the loader script:

```bash
uv run --directory mcp/daas-mcp \
  python .trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py \
  .trae/skills/fd-daas-data-fetch/references/<source>.registry.json
```

The loader ([scripts/load_registry_json.py](file:///Users/chengsishi/code/cli-anything/.trae/skills/fd-daas-data-fetch/scripts/load_registry_json.py)) is idempotent: it reads `DAAS_DATABASE_URL` from the `.env` file, then upserts the `sources` row + its `daas_functions` (with `frequency`) + `entities` + `entity_datasource_links` + `indicator_rules`. Re-running updates in place. Use `--dry-run` to preview. If `references/<source>.registry.json` is missing, the source hasn't been built — tell the user to invoke the `fd-daas-cli-datasource-entities-builder` skill.

## Step 3 — Read the per-source usage doc

Read the matching doc in [references/](file:///Users/chengsishi/code/cli-anything/.trae/skills/fd-daas-data-fetch/references): `references/<source>-usage.md`. It specifies, for that source only: install/env commands, the CLI entry + core subcommands, one worked `call` example (including how `identifier_in_source` is passed), and the exact way to search that source's functions. **Always read it before running.** If the doc is missing, tell the user the source needs to be built first.

## Step 4 — Prepare the environment

Following the usage doc:
1. `cd` into the source's harness dir (e.g. `<source>-agent-harness/`).
2. `uv sync` for the base env.
3. Install the source's optional extra if the underlying data library isn't present: `uv sync --extra <source>` (the doc names the exact extra/package).
4. Verify the adapter is available: `uv run python -c "from cli_anything.<source>.sources.<source>_source import <Adapter>; print(<Adapter>().is_available())"`.

## Step 5 — Run the fetch

Plug the entity's `identifier_in_source` into the function's expected param (from `get_function_detail` / the indicator's `function_name`).

**A. Source CLI** (most explicit):
```bash
uv run python -m cli_anything.<source> call <source>_<func> <id_param>=<identifier_in_source> --json
```
or the installed script: `cli-anything-<source> call <source>_<func> <id_param>=<identifier> --json`.

**B. daas-mcp `fetch_data` tool** (routes through `SourceRouter`):
```
fetch_data(function_name="<source>_<func>",
           params_json='{"<id_param>":"<identifier_in_source>"}')
```

Output is a DataFrame serialized to JSON records.

## Step 6 — Return results

Return the data (or a head/summary if large) plus: the entity (type/code/name), the indicator name (if any), the function name used, the source, the `frequency`, and the exact command/tool call so the user can re-run. If the fetch fails, read the error, check the usage doc, and fix the env/params before retrying.

## Notes
- `frequency` (on `daas_functions`) tells the user how fresh the data can be — mention it when relevant (e.g. "this is quarterly data").
- Never fabricate a function name, param, or `identifier_in_source` — always resolve them from the registry first.
- If multiple sources cover the entity, prefer the one with higher `score`, the one whose `frequency` matches the user's need, or the one with `coverage = 'full'`.
- If the user gives only an entity (no indicator), list the functions/indicators available for that entity (via `entity_datasource_links` → source → `daas_functions`) and let them pick.
