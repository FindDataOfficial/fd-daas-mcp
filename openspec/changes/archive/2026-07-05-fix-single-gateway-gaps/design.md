## Context

`leader-mcp-single-entry` (archived 2026-07-05) made `leader-mcp` the sole client-facing entry: `.mcp.json` has one entry, 18 upstreams are seeded, and generic `call_mcp` / `list_mcp_tools` aliases route to any upstream. End-to-end verification found two gaps:

1. **cnstats-mcp + worldbank-mcp** crash at `server.py:25` on `from cli_anything.daas.core.exceptions import DAASError` because the `daas-agent-harness` `sys.path` insertion (lines 27-32) runs *after* the import. The `cli_anything.daas` package lives in `daas-agent-harness/` (found at `daas-agent-harness/cli_anything/daas/core/exceptions.py`). The fix is a 1-block reorder per file — already applied in the working tree during verification; this change formalizes it. The sibling `ckan-mcp` (which works) took the opposite path of inlining its models with a comment "avoid cli_anything.daas dependency"; cnstats/worldbank kept the dependency, so they need the path set before the top-level import.

2. **composite-mcp** in proxied-composite mode fails through the gateway. `build_served_tools(app)` (`mcp/composite-mcp/server.py:89-129`) mounts a `create_proxy(build_transport(upstream))` per selected upstream, with a `FilterTools` Transform that filters the proxy's tools to the selected names. When leader-mcp calls `list_mcp_tools("composite-mcp")`, composite-mcp enumerates its served tools, which calls each mounted proxy's `list_tools`, which spawns the proxied upstream (akshare) as a nested stdio sub-subprocess. That nested spawn does not complete inside the running leader-mcp server context → `McpError: Connection closed`. Standalone invocation (a fresh `fastmcp.Client` script using the same `build_client` row) succeeds and lists 16 tools — so the launch config and env propagation are correct; only the in-server-context nested spawn fails. This is the same class of bug as `pipeline-bridge-cron-wiring-broken` (daas-mcp → cron-mcp).

Crucially, composite-mcp's **chained tools** already work: `make_chain_tool` (`composite_tools.py:268`) spawns the upstream per-step via `async with build_client(upstream) as client: await client.call_tool(...)` (line 286) — spawn-on-call, never at list time. So chains are not the problem; only the `create_proxy` + `mount` path for proxied tools is.

## Goals / Non-Goals

**Goals:**
- `list_mcp_tools(server="composite-mcp")` succeeds through `leader-mcp` when composite-mcp is started with `COMPOSITE=<name>` selecting a composite that mounts proxied upstreams (e.g. `COMPOSITE=example` → `akshare`). No "Connection closed".
- Listing composite-mcp's served tools does NOT spawn any upstream at list time. Upstreams are spawned only when a proxied tool is actually called (per-call `build_client`, mirroring `make_chain_tool`).
- cnstats-mcp + worldbank-mcp launch cleanly and route through `leader-mcp` (cnstats 7 tools, worldbank 5 tools) — fix already applied; this change commits it.
- A full gateway probe over all 18 upstreams returns tools for every one.

**Non-Goals:**
- Persistent client pooling for composite-mcp's proxied upstreams (per-call `build_client` stays; spawn latency is acceptable for on-demand calls — same stance as the gateway itself).
- Restoring per-tool input-schema richness in the listed output. Lazy stubs list the tool name + a forwarding description; the real schema is discoverable via `list_mcp_tools(server="akshare")` directly. (See Decision 2.)
- Fixing `scrapling-docker-mcp` — its failure is environmental (docker daemon not running on this host), not a code gap. The launch config is verified correct.
- Deprecating the `*_data_mcp` aliases.

## Decisions

### Decision 1: Replace `create_proxy` + `mount` with lazy `FunctionTool` stubs

**Chosen**: Rewrite `build_served_tools(app)` to register each selected proxied tool as a `FunctionTool` (via `app.add_tool`) instead of mounting a `create_proxy`. Each stub:
- Is named `<upstream_key>_<tool_name>` (the served name, unchanged from today's namespace pattern).
- Takes a single `arguments` parameter (JSON object as a string, mirroring `call_data_mcp` / `make_chain_tool`'s forwarding shape).
- On call, does `async with build_client(upstream) as client: result = await client.call_tool(tool_name, json.loads(arguments))` and returns the result — exactly the proven pattern from `make_chain_tool`.

**Rationale**: This is the minimal change that makes listing lazy. `app.add_tool` registers a tool whose name/description are known at registration time (from the DB `CompositeTool` rows via `list_composite_tools`) — no upstream spawn needed to enumerate. The upstream is spawned only when the stub is called, via the same `build_client` path that already works for chains. The pattern is proven in the same file (`make_chain_tool`).

**Alternatives considered**:
- Override `FilterTools.list_tools` to return synthetic `Tool` objects from `self.keep` without calling the upstream's `list_tools`. Rejected: fastmcp's `Transform.list_tools(tools)` receives the already-fetched upstream tool list — the fetch (and spawn) happens before the transform runs, so the transform cannot prevent it. Short-circuiting would require reaching inside the proxy's client, which is more invasive than replacing the mount.
- Persistent client pool that keeps the proxied upstream warm. Rejected: doesn't fix the *first* list-tools call (which spawns and fails in the server context); only amortizes subsequent calls. The nested-spawn-in-server-context failure is the root cause.
- Drop `COMPOSITE` env from the seeded config (run management-only through the gateway). Rejected as the primary fix: it sacrifices the composite's proxied tools and chains (the whole point of selecting a composite), and is redundant with the lazy-stub fix. Kept as a documented fallback if the stub approach hits an unforeseen blocker.

### Decision 2: Lazy stubs use a permissive `arguments` schema, not the upstream's real schema

**Chosen**: Each stub declares a single `arguments: str` (JSON object) parameter and a description like `"Proxied tool '<tool_name>' on upstream '<key>'. Call with a JSON object of the upstream tool's arguments."` The real per-parameter schema is NOT fetched at registration time.

**Rationale**: Fetching the real schema requires spawning the upstream (the very thing we're eliminating). A permissive schema keeps listing spawn-free. The shape matches `call_data_mcp(server, tool, arguments)` and `make_chain_tool`, so callers already understand the `arguments` JSON convention. The real schema remains discoverable via `list_mcp_tools(server="akshare")` (which spawns akshare directly — fine, that's a direct one-hop spawn, not nested).

**Alternatives considered**:
- Fetch the schema lazily on first call and cache it, re-registering the tool. Rejected: re-registering tools at runtime after server start is fragile in FastMCP; the cache invalidation adds complexity for a UX nicety.
- Store the schema in the DB at `add_tool` time (spawn once when a tool is selected, persist the schema). Deferred: a follow-up could enrich `CompositeTool` rows with a cached `input_schema` column populated at selection time. Non-goal for this change; the permissive schema is enough to fix the routing gap.

### Decision 3: cnstats/worldbank fix is a sys.path reorder, not a dependency change

**Chosen**: Move the `_HARNESS_ROOT = os.path.join(...); sys.path.insert(0, _HARNESS_ROOT)` block above the `from cli_anything.daas.core.exceptions import DAASError` line. No `pyproject.toml` change, no new dependency.

**Rationale**: `cli_anything.daas` is the daas-agent-harness package, already on disk at `<repo>/daas-agent-harness/`. The harness isn't a published package; the existing convention across the project's MCPs is `sys.path.insert` for it. ckan-mcp avoided the dependency by inlining models; cnstats/worldbank use the harness's `SourceRouter`/`models` at call time (in-function imports at lines 69/106/126/156/191/228/257), so they need the path set — just earlier.

**Alternatives considered**:
- Inline `DAASError` and the models (mirror ckan-mcp). Rejected: cnstats/worldbank use `SourceRouter` and several models in-function; inlining all of them is a larger change than a 1-block reorder, with no functional benefit.
- Add `daas-agent-harness` as an editable dep in cnstats/worldbank `pyproject.toml`. Rejected: the harness isn't packaged for install; `sys.path.insert` is the project convention.

### Decision 4: composite-mcp DB-URL resolution (the real root cause, found during implementation)

**Chosen**: Port `_resolve_database_url` from `gateway_database.py` to `composite_database.py`, and use it in `CompositeDatabase.__init__` so relative `sqlite:///` URLs (e.g. `sqlite:///mcp/daas.db`) are resolved against the repo root before being passed to `create_engine`.

**Rationale**: Implementation of Decisions 1-2 (lazy stubs) alone did NOT fix the gateway failure — `list_mcp_tools("composite-mcp")` still returned "Connection closed". Capturing composite-mcp's stderr (via a temporary `bash -c '... 2>/tmp/...log'` wrapper around the upstream command) revealed the real crash: `sqlite3.OperationalError: unable to open database file` in SQLAlchemy's `connect`. composite-mcp's `build_served_tools` calls `get_composite_db().load_composite(...)`, which opens `mcp/daas.db`; `composite_database.py` read `DAAS_DATABASE_URL` from env but passed relative URLs straight to `create_engine`, which resolves them against the process cwd. leader-mcp spawns composite-mcp with cwd = `mcp/composite-mcp` (via `uv run --directory`), so `sqlite:///mcp/daas.db` resolved to `mcp/composite-mcp/mcp/daas.db` (nonexistent) → startup crash → "Connection closed". This is the same class of bug as `daas-writer-relative-db-url-broken` (which already fixed daas_database.py + dashboard db.ts); `composite_database.py` was never updated. (Management-only mode worked because `build_served_tools` returns early without touching the DB when `COMPOSITE` is unset — which is also why the earlier isolation pointed at the proxy mount instead of the DB.)

**Why both fixes are kept**: Decision 1-2 (lazy stubs) removes the eager akshare spawn at list time (a real efficiency + correctness improvement — listing is now DB-driven and never spawns upstreams). Decision 4 (DB-URL) makes composite-mcp actually start under the gateway. Both are required for proxied-composite mode to route through `leader-mcp`.

**Alternatives considered**:
- Set an absolute `DAAS_DATABASE_URL` in composite-mcp's `leader_upstreams` env. Rejected: fragile (breaks if the repo moves), and doesn't fix composite-mcp when run standalone/locally without that env. The repo-root resolution is the project-wide pattern.
- Set `cwd` in the upstream config to the repo root. Rejected: `uv run --directory` already pins composite-mcp's cwd to its own dir for venv resolution; overriding cwd would break `uv run`'s venv discovery. The DB-URL resolution is the correct layer to fix this.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Lazy stubs lose per-parameter schema in `list_mcp_tools` output (callers see `arguments: str` not the real params) | Documented in Decision 2; real schema available via direct `list_mcp_tools(server="akshare")`. A follow-up could cache schemas in the DB at `add_tool` time. |
| A proxied tool whose upstream tool signature changes after selection would still forward (stale name) | The stub calls by name at call time; an unknown-tool error surfaces from the upstream as a clear `is_error` result. Acceptable. |
| `build_client` per proxied call re-spawns the upstream every call (no pooling) | Same stance as the gateway and `make_chain_tool` today; spawn latency is acceptable for on-demand calls. Pooling is a documented future non-goal. |
| Renaming the spec requirement ("known limitation" → removed) requires archive-time REMOVED+ADDED or MODIFIED | MODIFIED with the full updated block; header text matches the archived requirement exactly. Verified against `openspec/specs/leader-mcp-data-gateway/spec.md`. |
| cnstats/worldbank fix is already in the working tree (uncommitted) | Tasks.md marks these as "applied during verification; verify + commit". No re-implementation needed. |

## Migration Plan

1. **cnstats/worldbank** (already applied): verify `git diff mcp/cnstats-mcp/server.py mcp/worldbank-mcp/server.py` shows the sys.path-before-import reorder. Re-run `list_mcp_tools(server="cnstats")` and `list_mcp_tools(server="worldbank")` through the gateway to confirm 7 and 5 tools.
2. **composite-mcp lazy stubs**: rewrite `build_served_tools` to register `FunctionTool` stubs (per Decision 1). Keep `make_chain_tool` unchanged (already lazy). Keep management tools + `register_ui_tools` unchanged.
3. Verify `list_mcp_tools(server="composite-mcp")` succeeds through the gateway with `COMPOSITE=example` set, returning the management + UI + proxied + chain tool names (no spawn at list time).
4. Verify a proxied tool call works: `call_mcp(server="composite-mcp", tool="akshare_<tool>", arguments='{}')` spawns akshare and returns its result.
5. Run the full 18-upstream probe; expect 18/18 to list tools (composite-mcp proxied mode now green; scrapling-docker still gated on docker daemon — environmental, not a code gap).
6. Update the spec (MODIFIED requirement) to remove the "known limitation" framing.
7. Commit cnstats/worldbank + composite-mcp changes together.

**Rollback**: revert the `build_served_tools` rewrite to restore `create_proxy` + `mount` (proxied mode fails through the gateway again, as documented). cnstats/worldbank reorder can stay (it's a pure bug fix).

## Open Questions

1. Should the lazy stubs expose the upstream's real schema by caching it in the `CompositeTool` row at `add_tool` time? — Deferred (Decision 2). Revisit if callers need per-parameter discovery through composite-mcp.
2. Should `scrapling-docker-mcp` be moved to a persistent sidecar to avoid the per-call docker cold-start? — Out of scope; the docker daemon must be running regardless.
3. Is there value in a composite-mcp self-check that asserts listing doesn't spawn upstreams (e.g., by asserting no `Starting MCP server` log line during `list_tools`)? — Lean yes; add to `selfcheck.py` if cheap.
