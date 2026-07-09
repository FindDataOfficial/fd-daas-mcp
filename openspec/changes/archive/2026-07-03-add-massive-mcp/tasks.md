## 1. Scaffold the massive-mcp directory

- [x] 1.1 Create `mcp/massive-mcp/pyproject.toml` — `name="massive-mcp"`, `requires-python=">=3.12"`, `dependencies=["mcp_massive @ git+https://github.com/massive-com/mcp_massive@v0.10.0", "python-dotenv>=1.0"]`, `[build-system]` `uv_build` (mirror `mcp/dartlab-mcp/pyproject.toml`).
- [x] 1.2 Create `mcp/massive-mcp/README.md` — explain it is a launch shim over the upstream `mcp_massive` package (not a hand-written server), that `MASSIVE_API_KEY` lives in the repo-root `.env`, and that its three tools are reached via `leader-mcp` (`call_data_mcp(server="massive", …)` / `list_data_mcp_tools(server="massive")`). Note the `v0.10.0` pin and the experimental-upstream caveat.

## 2. Launch shim (server.py)

- [x] 2.1 Create `mcp/massive-mcp/server.py` that: resolves repo root via `Path(__file__).resolve().parents[2]`; `load_dotenv(root/.env)` then `load_dotenv(local/.env, override=True)` (guarded `try/except ImportError`); checks `os.environ.get("MASSIVE_API_KEY","").strip()` and, if missing, writes a clear stderr message naming the var + pointing to root `.env` and `sys.exit(1)` WITHOUT exec'ing; otherwise `os.execvp("mcp_massive", ["mcp_massive"])` so the process is replaced by the upstream server, inheriting stdio + env.
- [x] 2.2 Add a `--selfcheck` branch (mirrors `edgartools-mcp`): with no `MASSIVE_API_KEY` set, assert the shim prints the missing-key message and exits non-zero; with a dummy key in `os.environ`, assert `os.execvp` would be called (stub `os.execvp` to record the target name + argv, then assert it was `("mcp_massive", ["mcp_massive"])`). No network, no real exec.

## 3. Pre-warm venv + API key

- [x] 3.1 Run `uv sync` (or `uv run --directory mcp/massive-mcp python -c "import mcp_massive"`) in `mcp/massive-mcp/` so the isolated 3.12+ venv and the `mcp_massive` package are downloaded ahead of the first gateway call (avoids a cold-start timeout on the first `call_data_mcp`).
- [x] 3.2 Add `MASSIVE_API_KEY=<user-provided value>` to the repo-root `.env` (gitignored). Do NOT put the key in `mcp/massive-mcp/.env`, `leader_upstreams.env_json`, or any committed file. Confirm `git check-ignore .env` reports it ignored and `git ls-files .env` is empty.

## 4. leader-mcp upstream seeder

- [x] 4.1 Create `mcp/leader-mcp/seed_massive_upstream.py` mirroring `seed_upstreams.py`'s shape: load root `.env`, import `get_gateway_db` from `gateway_database`, upsert a `massive` row with `transport="stdio"`, `command="uv"`, `args=["run","--directory","<repo>/mcp/massive-mcp","python","server.py"]` (resolve `<repo>` from `Path(__file__).resolve().parents[2]`), `env=None`, `enabled=True`, `description="Massive.com financial data MCP (search_endpoints / call_api / query_data)"`. Flags `--dry-run` and `--unseed` (the latter deletes the `massive` row and prints a rollback note).
- [x] 4.2 Run `uv run --directory mcp/leader-mcp python seed_massive_upstream.py --dry-run` and confirm the planned upsert; then run without `--dry-run` and confirm `sqlite3 mcp/daas.db "select name,env_json,enabled from leader_upstreams where name='massive';"` shows `env_json` NULL and `enabled=1`.
- [x] 4.3 Run `--unseed`, confirm the row is gone, then re-run the seeder (idempotency round-trip).

## 5. Specialist agent

- [x] 5.1 Run `uv run --directory mcp/leader-mcp python seed_specialist_agents.py` (no code change — the existing loop auto-creates one `<upstream>-agent` per enabled upstream). Confirm a `massive-agent` row exists (non-registry branch: `list_tools_massive` + `call_data_mcp_massive`).

## 6. daas datasource seed (extend seed_external_mcps.py)

- [x] 6.1 In `mcp/daas-mcp/seed_external_mcps.py`: add `"massive"` to `OWNED_SOURCES`; add a `massive` entry to `SOURCES` with `label="Massive.com"`, `description="Multi-asset financial data (stocks, options, forex, crypto, futures, fundamentals, analyst news, treasuries) via the mcp_massive 3-tool composable API (search_endpoints → call_api → query_data)."` , `url="https://massive.com"`, `category="Massive"`.
- [x] 6.2 Add `("Massive", "Massive.com", "Market-Data")` to `CATEGORIES` (new leaf under the existing `Market-Data` root, sibling to `Global`).
- [x] 6.3 Add a `MASSIVE_SECTIONS` list of three `(section_name, instruction)` tuples following the routing grammar: `("Search-Endpoints", "mcp=massive-mcp tool=search_endpoints param=query=<ask-agent>")`, `("Call-API", "mcp=massive-mcp tool=call_api param=path=<ask-agent> param=method=<ask-agent>")`, `("Query-Data", "mcp=massive-mcp tool=query_data param=sql=<ask-agent>")`. Wire it into the seed body as a single `default` form (mirror the `YFINANCE_SECTIONS` / `cnstats` code path: one `default` form, three sections via `goc_form` + `goc_section`).
- [x] 6.4 Add `("massive", "Search-Endpoints")` to `CORE_ITEMS` so the `core` collection gains one `massive` entry.
- [x] 6.5 Run `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py --dry-run` and confirm `massive` + `Massive` category + `default` form + 3 sections + 1 core item are planned.
- [x] 6.6 Run the seed (no `--dry-run`); then verify via `dashboard-mcp` / direct sqlite: `list_sources` includes `massive`; `list_forms(source_name="massive")` returns exactly one `default` form with 3 sections; each section's `instruction` matches the routing grammar; `get_category_tree()` shows `Market-Data → Massive` containing `massive` and `Market-Data → Global` still containing `yfinance`; `list_collection(collection_name="core")` includes exactly one `massive` item.
- [x] 6.7 Re-run the seed (idempotency); confirm row counts in `sources`/`categories`/`datasource_forms`/`datasource_sections`/`datasource_collection_items` are unchanged and exit status is 0.

## 7. Smoke checks (gateway round-trip)

- [x] 7.1 Via `leader-mcp`, call `list_data_mcps()` and confirm `massive` is listed.
- [x] 7.2 Call `list_data_mcp_tools(server="massive")` and confirm it returns `search_endpoints`, `call_api`, `query_data` (requires `MASSIVE_API_KEY` set in root `.env`).
- [x] 7.3 Call `call_data_mcp(server="massive", tool="search_endpoints", arguments='{"query":"aapl stock price","max_results":5}')` and confirm a non-error JSON result is returned (live API call; skip if offline, but record the skip).

## 8. Rollback verification

- [x] 8.1 Run `uv run --directory mcp/daas-mcp python seed_external_mcps.py --unseed`; confirm `massive` is gone from `sources`, its `default` form + 3 sections are gone, the `Massive` leaf category is gone from `get_category_tree()`, `Market-Data → Global` + `yfinance` are intact, the `core` collection no longer has a `massive` item, and `ckan`/`cnstats`/`worldbank` are still present.
- [x] 8.2 Run `uv run --directory mcp/leader-mcp python seed_massive_upstream.py --unseed`; confirm `massive` is gone from `leader_upstreams` and `list_data_mcps(include_disabled=True)` no longer returns it.
- [x] 8.3 Re-run both seeders to restore the `massive` rows (forward-again).
