## Context

FastMCP 3.4.2 ships composition primitives: `create_proxy(config)` mounts whole upstream servers, `mcp.mount(proxy, namespace=...)` attaches them, and `Client` connects to a single upstream to `list_tools()` / `call_tool()`. Native tool filtering is **tag-based** (`include_tags` / `exclude_tags`). The user's need is **name-based** selection ("tool 1 from mcp-1, tools 4 and 5 from mcp-2"), which native filtering does not cover. combine-mcp is the name-based selection + orchestration layer on top of those primitives.

## Goals

- Curate a composite: pick named tools from multiple upstreams, persist the selection.
- Expose proxied tools verbatim (forward call, return result).
- Expose chained tools: a new tool that runs a linear pipeline of upstream calls, each step's inputs drawn from literals or the previous step's output (`$prev`).
- Multiple composites, one per running server instance (selected by env), sharing one `server.py` and one DB.

## Non-Goals

- Hot live-registration of tools without restart (v1 applies changes on next process start).
- Branching/conditional chains (linear pipelines only).
- Auth on upstreams (local stdio MCPs; remote HTTP auth added later if needed).
- Connection pooling / reconnect-backoff (single cached `Client` per upstream).
- Multi-tenant serving of several composites from one process (one composite per process; run multiple processes for multiple composites).

## Decisions

### Decision: One composite per process, selected by `COMPOSITE` env var

A single `server.py` reads `COMPOSITE=<name>` at startup and loads that composite's tools. To serve a second composite (mcp-4), add a second `.mcp.json` entry pointing at the same `server.py` with a different `COMPOSITE`. This avoids multi-tenant state inside the process while still supporting N composites from one codebase.

### Decision: Per-composite upstream definitions (denormalized)

`upstreams` rows are scoped to a composite (`composite_id` FK), not globally shared. If two composites want the same upstream, they each define their row. This is simpler than a global upstream registry + join table; normalize only if shared-upstream churn becomes real.

### Decision: Name-based selection via `create_proxy` + `Visibility` filter + `mount`

FastMCP rejects `**kwargs` tool signatures (it infers schemas from explicit params), so a plain forwarding function cannot be registered as a tool. Instead, combine-mcp uses the native composition path per upstream:

1. `proxy = create_proxy(StdioTransport(...))` — a schema-correct proxy of the whole upstream.
2. Enumerate the proxy's tools via `Client(proxy).list_tools()`, compute `unselected = all - selected`, and `proxy.add_transform(Visibility(enabled=False, names=unselected))` to hide everything not selected.
3. `combine_app.mount(proxy, namespace=<upstream_key>)` — exposes selected tools as `<upstream_key>_<tool>` (FastMCP's namespace separator is a single underscore).

This gives per-tool name control (native filtering is tag-only, not name-based, so `Visibility` by name is the mechanism), keeps upstream schemas intact, and is the same `create_proxy`/`Client` family chains use. Confirmed working in spike3.

Chains and `list_available_tools` use a raw `Client(StdioTransport(...))` per upstream (bypassing the `Visibility` filter) so a chain step may call any upstream tool, not only selected ones. `# ponytail: persistent Client per upstream opened lazily; per-call open if spawn latency is acceptable.`

### Decision: Linear pipeline chain format

```json
{"steps": [
  {"upstream": "akshare", "tool": "stock_zh_a_hist",
   "input": {"symbol": "000001", "start_date": "20250101"}},
  {"upstream": "akshare", "tool": "stock_news_em",
   "input": {}},
  {"upstream": "daas", "tool": "fetch_data",
   "input": {"close": "$step[0].close", "sentiment": "$prev.sentiment"}}
]}
```

Step inputs resolve against the list of completed step results. Two reference forms:
- `$step[N].<path>` — any prior step (N is a 0-based index).
- `$prev.<path>` — sugar for `$step[current-1].<path>` (the immediately prior step).

Anything not starting with `$step[` or `$prev.` is a literal. Resolver: split on first `.`, index = current-1 for `$prev` or N for `$step[N]`, then dot-path lookup into that step's result object. No branching, no conditionals, no retries. Fail-fast: a step error aborts the chain and surfaces the error.

The simplification boundary is *linear, no branching* — not "can only see the previous step." `$step[N]` removes the real friction case (a late step needing an early step's output without intermediate threading) at the cost of ~the same resolver code.

`# ponytail: linear pipeline; branching needs a DAG + eval engine, add when a real chain needs it.`

### Decision: Auto-prefix served tool names via mount namespace

Served proxy tools are named `<upstream>_<tool>` (FastMCP mount namespace separator) to avoid collisions (two upstreams both exposing `fetch_data` → `akshare_fetch_data` vs `daas_fetch_data`). This is native to `mount(namespace=...)` — no custom rename code.

**Alias override deferred.** A user-supplied alias that replaces the full exposed name does not compose cleanly with mount-namespace without a custom rename `Transform` (rename in `list_tools`, reverse-resolve in `get_tool`). Since namespace prefixing already prevents collisions — the only hard requirement — alias is deferred to a later change. The `composite_tools.alias` column is retained in the schema for forward compatibility but unused in v1.

`# ponytail: alias deferred; namespace prefix covers the collision-avoidance requirement. Add rename Transform when a user needs friendlier names.`

### Decision: Changes apply on restart

`add_tool` / `remove_tool` / `add_chained_tool` write DB rows; the served tool surface is rebuilt on next process start. Live registration is possible in FastMCP 3.x but adds a correctness footgun for v1.

`# ponytail: changes apply on restart; live add_tool if a workflow needs zero-downtime curation.`

### Decision: Single cached `Client` per upstream, opened lazily

One `Client` per upstream, created on first use and reused. No pool, no reconnect logic.

`# ponytail: single Client per upstream; reconnect-on-error if a flaky upstream shows up.`

## Risks / Trade-offs

- **Restart-to-apply** is a UX cost for an interactive curation flow. Acceptable for v1; the management tools still let you build the selection interactively, you just restart to serve it.
- **Linear-only chains** will not express every "compose a new ability" the user imagines. Explicit ceiling; DAG can come later without breaking the linear format (a linear chain is a degenerate DAG).
- **`Client.call_tool` result shape** for chained `$step[N]`/`$prev` resolution depends on how the upstream returns data (text content vs structured). The spike (tasks section) confirms the result is JSON-addressable before we build chain resolution around it.
- **Stdio upstream lifecycle**: each upstream is a subprocess spawned by `Client`. Many upstreams = many subprocesses per combine-mcp instance. Fine for a handful; worth noting if a composite pulls from 10+ upstreams.

## Resolved Questions

- **`list_available_tools` pagination**: substring `query` filter + `total` count, no `limit`/`offset` in v1. The real curation UX is "find the tool I want to add," which is search not browse. Returning all names (673 ≈ few KB) is fine for an LLM; `total` honors the no-silent-caps rule. Add `limit`/`offset` only when a registry is measurably slow. `# ponytail: query filter is the real UX; limit/offset add when a registry is measurably slow.`
- **`$step[N]` vs `$prev`**: do `$step[N].<path>` in v1, with `$prev.<path>` as sugar for the immediately prior step. Same resolver, removes the real friction case (late step needing an early step's output). The simplification boundary is linear/no-branch, not previous-step-only.
