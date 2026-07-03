## 1. Schema & model

- [x] 1.1 Add `LeaderUpstream` model to `mcp/models/models.py` (columns: `id` PK, `name` unique, `transport` default `stdio`, `command`, `args_json` (JSON list), `env_json` nullable (JSON dict), `cwd` nullable, `enabled` default `1`, `description` nullable, `created_at`, `updated_at`). Reuse the shared `Base`.
- [x] 1.2 Verify `Base.metadata.create_all` creates `leader_upstreams` in `mcp/daas.db` on next leader-mcp startup (no Alembic). Confirm via `dashboard-mcp.query_table(database="daas", table="leader_upstreams")` returns empty rows.

## 2. Gateway database layer

- [x] 2.1 Create `mcp/leader-mcp/gateway_database.py`: a singleton `GatewayDatabase` with CRUD — `upsert_upstream`, `get_upstream(name)`, `list_upstreams(include_disabled)`, `delete_upstream(name)`, `set_enabled(name, enabled)`. Use `DAAS_DATABASE_URL`, set `PRAGMA foreign_keys=ON` per connection, resolve relative `sqlite:///` against repo root (mirror `process-mcp`).
- [x] 2.2 Add a `build_client(upstream_row)` helper in `gateway_database.py` that mirrors `combine_database.build_client` → `Client(StdioTransport(command, args, env, cwd))`. Open per call; caller does `async with`.

## 3. FastMCP client gateway tools

- [x] 3.1 Create `mcp/leader-mcp/gateway_tools.py` with `list_data_mcps(include_disabled: bool = False) -> dict` — returns enabled upstreams (name + description + transport) from `leader_upstreams`.
- [x] 3.2 Add `list_data_mcp_tools(server: str) -> dict` — builds a client from the `server` row, `async with client:`, calls `await client.list_tools()`, returns `{"server", "tools": [{name, description}]}`. Return `{"error": ...}` for unknown/disabled upstream or subprocess failure.
- [x] 3.3 Add `call_data_mcp(server: str, tool: str, arguments: str = "{}") -> dict` — `json.loads(arguments)`, `async with client:`, `await client.call_tool(tool, kwargs)`, return the upstream's result. Return `{"error": ...}` for invalid JSON, unknown/disabled upstream, unknown tool, or execution error. Ensure the subprocess is torn down in all paths.
- [x] 3.4 Make the three tools sync-callable from FastMCP (FastMCP tool functions can be sync wrappers around `asyncio.run` of the async core; keep the async core reusable for `data_crew.py`).

## 4. CrewAI DataCrew + fallback router

- [x] 4.1 Create `mcp/leader-mcp/data_crew.py` with `DataCrew` class: `ask(question, verbose=True) -> dict`. Try `_ask_with_crewai`; on `ImportError`/exception log and fall back to `_ask_direct`.
- [x] 4.2 `_ask_with_crewai`: build a Manager agent (routes NL → `(server, tool, arguments)` using registry tools + `list_data_mcps`) and a DataFetcher agent (calls `call_data_mcp`). Hierarchical `Crew`, single `Task`. Return the `call_data_mcp` result dict (raw upstream JSON, not a prose summary).
- [x] 4.3 `_ask_direct`: deterministic router — keyword/regex over the question, use `search_functions`/`list_harnesses` to map to an upstream+tool+arguments, then call `call_data_mcp`. Return `{"error": "could not route", "available": [...]}` if no match.
- [x] 4.4 Add `ask_data_crew(question: str) -> dict` FastMCP tool wrapper in `gateway_tools.py` that instantiates `DataCrew` and returns `crew.ask(question)`.

## 5. Management tools

- [x] 5.1 Add `add_data_mcp(name, transport="stdio", command, args=None, env=None, cwd=None, enabled=True, description=None) -> dict` to `gateway_tools.py` — upserts via `GatewayDatabase`. Returns the stored row.
- [x] 5.2 Add `remove_data_mcp(name: str) -> dict` and `get_data_mcp(name: str) -> dict` to `gateway_tools.py`.

## 6. Server wiring & deps

- [x] 6.1 Register the 7 new tools in `mcp/leader-mcp/server.py` (`list_data_mcps`, `list_data_mcp_tools`, `call_data_mcp`, `ask_data_crew`, `add_data_mcp`, `remove_data_mcp`, `get_data_mcp`) via `app.add_tool(...)`.
- [x] 6.2 Update `mcp/leader-mcp/pyproject.toml`: add `crewai` as an optional extra (`[project.optional-dependencies] crew = ["crewai"]`), and add `gateway_tools`, `data_crew`, `gateway_database` to `[tool.setuptools] py-modules`.
- [x] 6.3 `uv pip install -e ".[crew]"` in `mcp/leader-mcp/.venv`; verify `python -c "import crewai"` succeeds. If it fails, note the pin needed and proceed (fallback router covers it).

## 7. Seed script

- [x] 7.1 Create `mcp/leader-mcp/seed_upstreams.py`: read `.mcp.json` from repo root, filter to the 10 data-fetch MCP names (`akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank`), map each entry to a `leader_upstreams` row (command/args/cwd/env), upsert idempotently via `GatewayDatabase`.
- [x] 7.2 Add `--dry-run` (print planned upserts, write nothing) and `--unseed` (delete the 10 rows, print the `.mcp.json` snippet for rollback) flags. Make it runnable via `uv run --directory mcp/leader-mcp python seed_upstreams.py`.
- [x] 7.3 Run `--dry-run`, review the 10 planned rows, then run for real. Confirm `list_data_mcps(include_disabled=True)` returns 10 entries.

## 8. Tests & self-check

- [x] 8.1 Create `mcp/leader-mcp/selfcheck_gateway.py` (or extend existing tests): exercise `add_data_mcp` → `list_data_mcps` → `list_data_mcp_tools` → `call_data_mcp` round-trip against a stub upstream (or `edgartools` `get_company`/`yfinance` `list_categories` if live). Use a temp DB.
- [x] 8.2 Add a test for `ask_data_crew` fallback path (force `ImportError`) asserting it still returns data via `_ask_direct` + `call_data_mcp`.
- [x] 8.3 Add a test for error paths: unknown upstream, disabled upstream, invalid JSON arguments, unknown tool.
- [x] 8.4 Run `uv run --directory mcp/leader-mcp python -m pytest -v` (or the project's test runner) and confirm green.

## 9. Migration: remove data-fetch MCPs from `.mcp.json`

- [x] 9.1 Verify the gateway end-to-end before any removal: `call_data_mcp("edgartools", "get_company", '{"ticker_or_cik":"AAPL"}')` and `ask_data_crew("get AAPL 1-month price history")` both return data.
- [x] 9.2 Edit `.mcp.json`: delete the 10 data-fetch MCP entries (`akshare-mcp`, `yfinance-mcp`, `edgartools-mcp`, `edinet-mcp`, `dartlab-mcp`, `cnreport-mcp`, `hkreport-mcp`, `ckan-mcp`, `cnstats-mcp`, `worldbank-mcp`). Keep `leader-mcp`, `cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `combine-mcp`, `process-mcp`.
- [x] 9.3 Restart the MCP client; confirm `leader-mcp` reconnects and `list_data_mcps()` still returns the 10 upstreams (configs now come from `leader_upstreams`, not `.mcp.json`).
- [x] 9.4 Re-verify a live fetch through the gateway post-removal: `call_data_mcp("yfinance", "list_categories", "{}")`.

## 10. Docs

- [x] 10.1 Update `CLAUDE.md` `mcp/leader-mcp/` section: document the new gateway tools, the `leader_upstreams` table, `seed_upstreams.py`, the `crewai` optional extra, and that the 10 data-fetch MCPs are now reached via `leader-mcp` (not `.mcp.json`).
- [x] 10.2 Note the breaking change + rollback (`seed_upstreams.py --unseed`) in the change summary.
