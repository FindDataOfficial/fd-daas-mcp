## Why

The project reaches every data-fetch MCP (akshare, yfinance, edgartools, edinet, dartlab, cnreport, hkreport, ckan, cnstats, worldbank) through `leader-mcp`'s gateway (`call_data_mcp`), and advertises each one to agents as a daas datasource (forms/sections with routing instructions + the `core` collection). Massive.com is a multi-asset financial-data API (stocks, options, forex, crypto, futures, fundamentals, analyst news, treasuries) exposed as a pre-built MCP server — the `mcp_massive` package — with a 3-tool composable surface (`search_endpoints` → `call_api` → `query_data`). Bringing it into the project the same way as the other ten gives agents one more cross-asset data source reachable through the existing gateway, with its API key managed in the unified root `.env`.

## What Changes

- New `mcp/massive-mcp/` directory: a **launch shim** (not a hand-written server) — `pyproject.toml` pins the upstream `mcp_massive @ git+https://github.com/massive-com/mcp_massive@v0.10.0` (Python 3.12+, isolated venv like `dartlab-mcp`), and a thin `server.py` loads root `.env` then `exec`s the `mcp_massive` console script. Uniform `uv run --directory mcp/massive-mcp python server.py` launch.
- `MASSIVE_API_KEY` added to the gitignored root `.env` (the user-provided value); the shim fails fast with a clear error if it is unset. The key never enters `leader_upstreams.env_json` or any committed file.
- New `massive` row in `leader_upstreams` (via a new idempotent `mcp/leader-mcp/seed_massive_upstream.py`, `--dry-run` / `--unseed`) with `env=NULL` — so the spawned `mcp_massive` subprocess inherits leader-mcp's env, where `MASSIVE_API_KEY` already lives after leader-mcp's own `load_dotenv`. No `.env`-to-subprocess plumbing and no secret in the DB.
- `seed_specialist_agents.py` is re-run (no code change) so the existing "one specialist agent per enabled upstream" loop auto-creates `massive-agent`.
- `mcp/daas-mcp/seed_external_mcps.py` extended to register `massive` as a daas datasource: new `Massive` category (under `Market-Data`), one `default` form with three sections (`Search-Endpoints`, `Call-API`, `Query-Data`) carrying `mcp=massive-mcp tool=…` routing instructions, plus one item in the `core` collection.
- No schema changes (`leader_upstreams`, `sources`, `datasource_forms`, `datasource_sections`, `datasource_collections`, `datasource_collection_items` all exist). No new shared-package tables. No changes to other MCPs — `massive` is called as a client, not modified.

## Capabilities

### New Capabilities
- `massive-mcp-server`: A launch-shim MCP server (`mcp/massive-mcp/`) that pins and `exec`s the upstream `mcp_massive` package, loads `MASSIVE_API_KEY` from root `.env`, fails fast when the key is missing, and is registered as a `leader_upstreams` row (`name="massive"`, `env=NULL`) so its three tools (`search_endpoints`, `call_api`, `query_data`) are reachable via `call_data_mcp(server="massive", …)`.

### Modified Capabilities
- `external-mcp-datasource-seed`: The seed now also registers `massive` as a daas datasource — adds a `Massive` category, a `default` form with three sections (one per `mcp_massive` tool) whose `instruction` strings follow the existing `mcp=massive-mcp tool=… param=…` routing grammar, and one `massive` item in the `core` collection. The seed's owned-source set grows from five/six to include `massive`.

## Impact

- `mcp/massive-mcp/` (new): `pyproject.toml` (`requires-python>=3.12`, deps `mcp_massive @ git+…@v0.10.0`, `python-dotenv`), `server.py` (dotenv load + `execvp("mcp_massive")` + key guard), `README.md`.
- `mcp/leader-mcp/seed_massive_upstream.py` (new): idempotent upsert of the `massive` `leader_upstreams` row, `--dry-run` / `--unseed`.
- `mcp/daas-mcp/seed_external_mcps.py` (modified): `massive` source, `Massive` category, `default` form + 3 sections, `core` collection item; `OWNED_SOURCES` / `SEED_MARKER` updated.
- `.env` (gitignored): `MASSIVE_API_KEY=<user-provided value>` added.
- `mcp/daas.db`: new `leader_upstreams` row + new `sources`/`categories`/`datasource_forms`/`datasource_sections`/`datasource_collection_items` rows (seeded, not schema).
- Dependencies: `mcp_massive` (git, pinned v0.10.0) in `mcp/massive-mcp/`'s own isolated venv; no change to root or other MCP venvs.
- No `.mcp.json` change — `massive` is reached through `leader-mcp`, matching the established gateway pattern for the other ten data-fetch MCPs.
