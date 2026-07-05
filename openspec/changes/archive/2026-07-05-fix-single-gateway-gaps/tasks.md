## 1. cnstats-mcp + worldbank-mcp import-order fix (already applied)
- [x] 1.1 In `mcp/cnstats-mcp/server.py`, move the `_HARNESS_ROOT` `sys.path.insert(0, …)` block above the `from cli_anything.daas.core.exceptions import DAASError` import. [Applied during leader-mcp-single-entry verification.]
- [x] 1.2 Same reorder in `mcp/worldbank-mcp/server.py`. [Applied during leader-mcp-single-entry verification.]
- [x] 1.3 Verify both launch cleanly: `cd mcp/cnstats-mcp && uv run python server.py < /dev/null` and `cd mcp/worldbank-mcp && uv run python server.py < /dev/null` exit 0 with "Starting MCP server".
- [x] 1.4 Verify through the gateway: `list_mcp_tools(server="cnstats")` → 7 tools; `list_mcp_tools(server="worldbank")` → 5 tools.
- [ ] 1.5 Commit the two `server.py` changes (currently uncommitted in the working tree). [Deferred — pending user confirmation.]

## 2. composite-mcp lazy served-tool listing + DB-URL fix
- [x] 2.1 In `mcp/composite-mcp/server.py`, rewrite `build_served_tools(app)`: instead of `proxy = create_proxy(build_transport(upstream)); proxy.add_transform(FilterTools(selected)); app.mount(proxy, namespace=key)`, register one `FunctionTool` stub per selected tool via `app.add_tool`. Each stub is named `<upstream_key>_<tool_name>`, takes a single `arguments: str` (JSON object) parameter, and forwards via `async with build_client(upstream) as client: result = await client.call_tool(tool_name, json.loads(arguments))` (mirror `make_chain_tool`'s pattern).
- [x] 2.2 Build the stub factory in `composite_tools.py` (`make_proxy_tool(key, tool_name, upstream, description=None) -> FunctionTool`). Reuses the existing `build_client` import.
- [x] 2.3 `make_chain_tool` unchanged (already spawn-on-call). Management tools + `register_ui_tools` unchanged.
- [x] 2.4 Served tool names preserved: stubs named `<upstream_key>_<tool_name>` (e.g. `akshare_list_categories`).
- [x] 2.5 `FilterTools` class deleted; `create_proxy`/`Transform`/`build_transport`/`Sequence` imports removed from `server.py`.
- [x] 2.6 **DB-URL fix (the real root cause)**: composite-mcp crashed at startup with `sqlite3.OperationalError: unable to open database file` because `composite_database.py` did NOT resolve relative `DAAS_DATABASE_URL` against the repo root (unlike `gateway_database._resolve_database_url`). When leader-mcp spawned composite-mcp with cwd=composite-mcp dir (via `uv run --directory`), `sqlite:///mcp/daas.db` mis-resolved to `mcp/composite-mcp/mcp/daas.db`. Ported `_resolve_database_url` to `composite_database.py` and used it in `CompositeDatabase.__init__`. This is the `daas-writer-relative-db-url-broken` pattern. (Found via stderr capture — the lazy-stub rewrite alone was insufficient; composite-mcp never started.)

## 3. Verify composite-mcp through the gateway
- [x] 3.1 With `COMPOSITE=example` set, `list_mcp_tools(server="composite-mcp")` succeeds and returns 16 tools (12 management + 1 UI + 3 proxied stubs). No akshare spawn during the list call (listing is DB-driven via lazy stubs).
- [x] 3.2 Called a proxied tool through the gateway: `call_mcp(server="composite-mcp", tool="akshare_list_categories", arguments='{}')` spawned akshare on demand and returned `{"total_categories":0,"categories":[]}`.
- [x] 3.3 Standalone spawn works: `COMPOSITE=example uv run --directory mcp/composite-mcp python server.py < /dev/null` exits 0.
- [x] 3.4 `uv run --directory mcp/composite-mcp python selfcheck.py` → "ALL SELF-CHECKS PASSED", exit 0.
- [ ] 3.5 Optional: add an assertion to `selfcheck.py` that listing a composite with selected proxied tools does not spawn the upstream. [Skipped — not cheap (requires intercepting subprocess spawns); the live gateway test in 3.1/3.2 already confirms spawn-free listing + on-demand spawn.]

## 4. Full gateway probe + spec
- [x] 4.1 Ran `list_mcp_tools` across all 18 upstreams through `leader-mcp`. **17/18 return tools** (composite-mcp proxied mode now green). `scrapling-docker-mcp` remains gated on the docker daemon (environmental, not a code gap; launch config verified correct).
- [x] 4.2 `openspec validate fix-single-gateway-gaps` passes; the `leader-mcp-data-gateway` spec delta (REMOVED "known limitation" + ADDED the fixed requirement) is correct.
- [ ] 4.3 Commit composite-mcp changes (with the cnstats/worldbank changes from 1.5, or as a follow-up commit). [Deferred — pending user confirmation.]
