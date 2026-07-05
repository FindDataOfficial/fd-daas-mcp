## Why

Verification of the `leader-mcp-single-entry` consolidation (archived 2026-07-05) surfaced two gaps where non-leader MCPs do not route cleanly through `leader-mcp`'s gateway:

1. **`cnstats-mcp` + `worldbank-mcp`** crash at `server.py:25` on `from cli_anything.daas.core.exceptions import DAASError` because the `daas-agent-harness` `sys.path` insertion runs *after* the import. (Already fixed in the working tree during verification; this change gives that fix a tracked home and commits it.)
2. **`composite-mcp`** in proxied-composite mode (`COMPOSITE=<name>` selecting a composite that mounts upstream proxies, e.g. `example` → `akshare`) fails through `call_mcp` / `list_mcp_tools` with `McpError: Connection closed`. Root cause: `build_served_tools(app)` mounts the proxied upstream at startup; listing composite-mcp's tools spawns the proxied upstream as a nested stdio sub-subprocess (leader-mcp server → composite-mcp subprocess → proxied upstream), and nested stdio spawns do not complete inside the running leader-mcp server context. This is currently documented in the spec as a "known limitation" — this change removes the limitation.

With both fixed, all 18 seeded upstreams route through the single `leader-mcp` entry point.

## What Changes

- **cnstats-mcp + worldbank-mcp import order** (already applied in working tree): move the `_HARNESS_ROOT` `sys.path.insert(0, …)` block above the top-level `from cli_anything.daas.core.exceptions import DAASError` import in both `mcp/cnstats-mcp/server.py` and `mcp/worldbank-mcp/server.py`, so the `cli_anything.daas` package (which lives in `daas-agent-harness/`) is importable at module-load time. The in-function `cli_anything.daas.*` imports (router, models) already rely on this path being set.
- **composite-mcp lazy served-tool listing**: change `build_served_tools(app)` so that listing composite-mcp's served tools no longer spawns the proxied upstream. Tool-call forwarding still spawns the upstream on demand (per-call `fastmcp.Client`, unchanged). This decouples *enumerating* a composite's surface (cheap, DB-driven) from *invoking* a proxied tool (spawns the upstream), eliminating the eager-spawn-at-list-time path.
- **composite-mcp DB-URL resolution (the real root cause, found during implementation)**: port `_resolve_database_url` from `gateway_database.py` to `composite_database.py` so relative `DAAS_DATABASE_URL` (e.g. `sqlite:///mcp/daas.db`) resolves against the repo root. Without this, composite-mcp crashed at startup with `sqlite3.OperationalError: unable to open database file` when spawned by leader-mcp (cwd = `mcp/composite-mcp` mis-resolved the relative path) — the lazy-stub rewrite alone was insufficient because composite-mcp never started. This is the `daas-writer-relative-db-url-broken` pattern; `composite_database.py` was the last DB helper not updated.
- **Spec correction**: the `leader-mcp-data-gateway` requirement "Composite-mcp proxied-mode reachability (known limitation)" is modified — proxied-composite mode now succeeds through the gateway, and the "known limitation" framing is removed.

## Capabilities

### New Capabilities

None — no new capability folder. Both fixes tighten the existing single-gateway contract.

### Modified Capabilities

- `leader-mcp-data-gateway`: The "Composite-mcp proxied-mode reachability (known limitation)" requirement is modified — `call_mcp` / `list_mcp_tools` against `composite-mcp` started with `COMPOSITE=<name>` now succeeds (the nested-spawn failure is eliminated by lazy tool listing). The cnstats/worldbank import fix is covered by the existing "Non-leader MCPs removed from client connection" requirement (its "Data-fetch MCP still launchable by leader-mcp" scenario now holds for cnstats + worldbank too); no spec delta needed for that part.

## Impact

- **Code**:
  - `mcp/cnstats-mcp/server.py`, `mcp/worldbank-mcp/server.py` — sys.path-before-import reorder (already in working tree).
  - `mcp/composite-mcp/server.py` — `build_served_tools` rewritten to register lazy `FunctionTool` stubs (DB-driven names/schema) instead of mounting `create_proxy(...)` proxies; `FilterTools` class + `create_proxy`/`Transform`/`build_transport` imports removed.
  - `mcp/composite-mcp/composite_tools.py` — new `make_proxy_tool(key, tool_name, upstream, description)` factory (spawn-on-call, mirrors `make_chain_tool`).
  - `mcp/composite-mcp/composite_database.py` — ported `_resolve_database_url` (repo-root resolution for relative `sqlite:///` URLs) into `CompositeDatabase.__init__`.
- **Config**: no `.mcp.json` change (still 1 entry). No `leader_upstreams` change.
- **Database**: none.
- **Clients**: non-breaking — `call_mcp(server="composite-mcp", tool="akshare_<name>", …)` now works (previously failed); tool names are unchanged.
- **Verification**: a gateway probe (`list_mcp_tools`) over all 18 upstreams must return tools for every one, including composite-mcp with `COMPOSITE=example`.
