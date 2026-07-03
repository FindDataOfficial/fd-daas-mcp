## 1. Spike (de-risk before building)

- [x] 1.1 Confirm FastMCP 3.4.2 `Client` can connect to a local stdio MCP (e.g. akshare-mcp) from config `{command, args}`, call `list_tools()`, and `call_tool(name, args)` returning a JSON-addressable result. ~10 lines, throwaway script.
- [x] 1.2 Confirm a generated function registered via `app.add_tool` can forward a call through a cached `Client` and return the upstream result to the MCP client.
- [x] 1.3 Document the exact result shape of `call_tool` (text content? structured?) so `$step[N]`/`$prev` resolution in chains is built against reality.

## 2. Schema (mcp/models/ first)

- [x] 2.1 Add `Composite` model: `id, name (unique), description, created_at`.
- [x] 2.2 Add `Upstream` model: `id, composite_id (FK), key, transport (stdio|http), command, args (JSON), url, env (JSON)`.
- [x] 2.3 Add `CompositeTool` model: `id, composite_id (FK), upstream_key, tool_name, alias (nullable)`.
- [x] 2.4 Add `CompositeChain` model: `id, composite_id (FK), name, description, steps (JSON)`.
- [x] 2.5 Reinstall `mcp/models/` (`pip install -e mcp/models`); confirm tables create in `daas.db`.

## 3. Database layer

- [x] 3.1 `combine_database.py` — CRUD for composites, upstreams, composite_tools, composite_chains. Mirror `leader_database.py` structure.
- [x] 3.2 Loader: given a composite name, return its upstreams + selected tools + chains.
- [x] 3.3 `build_client(upstream)` / `build_transport(upstream)` — fresh Client per call (chains + list_available_tools); proxy tools use create_proxy's own client.

## 4. Management tools

- [x] 4.1 `list_composites()` / `create_composite(name, description)`.
- [x] 4.2 `add_upstream(composite, key, transport, command, args, url, env)` / `remove_upstream` / `list_upstreams`.
- [x] 4.3 `list_available_tools(composite, upstream_key, query?)` — live `Client.list_tools()`, substring filter on name (case-insensitive), returns `{tools, total}`.
- [x] 4.4 `add_tool(composite, upstream_key, tool_name, alias)` / `remove_tool` / `list_composite_tools`.
- [x] 4.5 `add_chained_tool(composite, name, description, steps)` / `remove_chained_tool` / `list_chained_tools`.

## 5. Served tool builders

- [x] 5.1 Per-upstream proxy wiring: `create_proxy(transport)` + lazy `FilterTools(Transform)` (keeps only selected names) + `combine_app.mount(proxy, namespace=upstream_key)`. Lazy filter avoids startup enumeration/asyncio.
- [x] 5.2 `make_chain_tool(name, steps, upstreams_by_key)` — runs steps sequentially, resolves `$step[N].<path>` and `$prev.<path>` (sugar for `$step[current-1]`) vs literals, fail-fast.
- [x] 5.3 Startup wiring: read `COMPOSITE` env, load rows, mount filtered proxies + register chained tools on the app.

## 6. Server entry + config

- [x] 6.1 `server.py` — FastMCP stdio, dotenv from root then local (mirror daas-mcp/leader-mcp), register management tools + built served tools, `app.run(transport="stdio")`.
- [x] 6.2 `pyproject.toml` — `fastmcp>=2.0`, `sqlalchemy>=2.0`, `python-dotenv`, depends on `models` package.
- [x] 6.3 Add `.mcp.json` entry for one example composite (`COMPOSITE=example`); seed `example` composite in `daas.db` via `seed_example.py`.

## 7. Self-check

- [x] 7.1 `selfcheck.py` — creates a composite, adds akshare upstream + tool, confirms proxy forwards and returns `.data`. Plus end-to-end subprocess smoke test (15 tools, proxy + management calls).
- [x] 7.2 Self-check: 3-step chain confirms `$step[0]`/`$prev` resolver (unit) + fail-fast on a bad tool name.

## 8. Docs

- [x] 8.1 Update `CLAUDE.md` MCP section with combine-mcp entry (entry, db, models, key files, run-from-within note).
- [x] 8.2 Note in `construction/mcp.md` the new tables and the one-composite-per-process model.
