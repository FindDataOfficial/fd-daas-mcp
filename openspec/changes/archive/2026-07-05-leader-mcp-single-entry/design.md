## Context

`leader-mcp` already ships a working data gateway ([gateway_tools.py](file:///Users/chengsishi/code/cli-anything/mcp/leader-mcp/gateway_tools.py), [gateway_database.py](file:///Users/chengsishi/code/cli-anything/mcp/leader-mcp/gateway_database.py)) that launches upstream MCPs on demand via `fastmcp.Client` over stdio and stores their launch config in the `leader_upstreams` table. The archived spec `leader-mcp-data-gateway` proved the pattern for the 10 data-fetch MCPs but explicitly required the 7 non-data MCPs (`cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`) to remain as direct `.mcp.json` entries. This change reverses that boundary so `leader-mcp` becomes the single client-facing entry point.

The gateway machinery needs no structural change — `build_client` already accepts arbitrary stdio commands (including `docker run`), `leader_upstreams` already has the `env_json` / `cwd` columns needed for `composite-mcp`'s `env={"COMPOSITE":"example"}`, and the `*_data_mcp` tools already work for any upstream row. The work is: broaden the seeder, add generic tool aliases, edit `.mcp.json`, document the recursion constraint.

## Goals / Non-Goals

**Goals:**
- `.mcp.json` contains exactly one entry: `leader-mcp`.
- Every other MCP in the project is reachable via `call_mcp(server=..., tool=..., arguments=...)`.
- Existing callers of `*_data_mcp` tools (`ask_data_crew`, crewai-data-workflow, `add-ai-chat` dashboard route) require zero code changes.
- Seeding is idempotent and reversible (`--unseed` restores the original `.mcp.json` snippet).

**Non-Goals:**
- Persistent client pooling — per-call `async with build_client(row)` stays (spawn latency is acceptable for on-demand calls; the existing comment in `gateway_database.py` notes a persistent client can be added later if needed).
- Deprecating the `*_data_mcp` tool names — they remain as aliases indefinitely; a future change can deprecate them with a warning.
- Migrating MCPs that are not in `.mcp.json` today (e.g. `trading-mcp`, `models/` — these are not client-facing entries; leave alone).
- Adding a recursion-depth guard for nested gateways — documented constraint, no code enforcement.

## Decisions

### Decision 1: Add generic `*_mcp` aliases; keep `*_data_mcp` as back-compat

**Chosen**: Add `list_mcps`, `list_mcp_tools`, `call_mcp`, `add_mcp`, `remove_mcp`, `get_mcp` as thin wrappers over the existing `*_data_mcp` functions. Both sets remain registered in `server.py`.

**Rationale**: Non-breaking. `ask_data_crew` and the crewai-data-workflow call `call_data_mcp` by name; the `add-ai-chat` dashboard spawns `leader-mcp` only (no tool-name dependency). The `*_data_mcp` names are misleading for non-data upstreams like `cron-mcp` / `alerts-mcp`, so the generic names become the documented surface for new callers.

**Alternatives considered**:
- Rename in place — breaks every existing caller; high blast radius for zero functional gain.
- Keep `*_data_mcp` only — works, but the names actively mislead anyone routing a `cron-mcp` or `alerts-mcp` call through `call_data_mcp`.

### Decision 2: Data-fetch MCPs keep short names; non-data MCPs use full `.mcp.json` keys

**Chosen**: `seed_upstreams.py` keeps the existing `DATA_FETCH_MCPS` mapping (`yfinance-mcp` → `yfinance`) for the 10 data-fetch MCPs, and adds the 7 non-data MCPs using their full `.mcp.json` keys as `name` (`cron-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`, `daas-mcp`, `dashboard-mcp`, `composite-mcp`, `alerts-mcp`).

**Rationale**: `ask_data_crew` and the crewai-data-workflow look up upstreams by short name (`yfinance`, `edgartools`, …). Changing those to full keys would break the crew. The 7 non-data MCPs have no existing gateway callers, so full keys are safe and avoid inventing a new short-name mapping table.

**Alternatives considered**:
- Strip `-mcp` suffix from all entries — loses the existing 10-name mapping (which uses non-trivial names like `edgartools` not `edgar-tools`) and risks collisions.
- Use full keys for all 17 — breaks `ask_data_crew` immediately.

### Decision 3: Migration order is seed → verify → edit `.mcp.json` → verify

**Chosen**: Generalize `seed_upstreams.py` first, run it against the current 8-entry `.mcp.json`, verify `call_mcp` works for one data + one non-data upstream, THEN edit `.mcp.json` down to `leader-mcp` only, then re-verify.

**Rationale**: If `.mcp.json` is edited before seeding, every `call_mcp` to a non-data upstream fails until the seed runs — a window of broken access. Seed-then-edit keeps the system functional throughout, and the verification step catches any env-propagation issue (e.g. `composite-mcp`'s `COMPOSITE=example`) before the direct entry is removed.

**Alternatives considered**:
- Edit-then-seed — simpler ordering but creates the broken-access window.
- Big-bang single commit — loses the ability to bisect if something breaks.

### Decision 4: No code guard for `composite-mcp` recursion; document the constraint

**Chosen**: `composite-mcp` is itself a gateway. Nesting `leader-mcp → composite-mcp → <upstream>` is allowed in principle and works when composite-mcp is invoked as a standalone process, but **does not work when composite-mcp is routed through `leader-mcp`'s gateway in its proxied-composite mode** (see Verification Finding below). No recursion-depth env var or runtime check is added. The constraint ("composite-mcp's upstreams MUST NOT include `leader-mcp`") is documented in `leader-mcp/README.md`.

**Rationale**: A code guard adds complexity for a hypothetical risk. The disjoint-upstreams invariant is true today and easy to audit. If composite-mcp ever gains a `leader-mcp` upstream, the loop would manifest as a spawn-time hang (not silent corruption) and be caught immediately.

**Verification Finding (2026-07-06)**: Routing composite-mcp through `call_mcp` / `list_mcp_tools` **fails with "Connection closed" when a `COMPOSITE` env var selects a composite that mounts proxied upstreams** (e.g. `COMPOSITE=example`, which proxies `akshare`). Root cause: `build_served_tools(app)` mounts the proxied upstream at startup (`server.py:129`); listing composite-mcp's tools then spawns the proxied upstream as a nested stdio sub-subprocess (leader-mcp server → composite-mcp subprocess → akshare sub-subprocess), and nested stdio spawns do not complete inside the running leader-mcp server context — the same class of bug as the `pipeline-bridge-cron-wiring-broken` finding (daas-mcp → cron-mcp). Isolated by config swap: `python server.py` + no `COMPOSITE` env → 13 management tools list cleanly through the gateway; restoring `COMPOSITE=example` (under either `python server.py` or `fastmcp run`) → fails again. So the trigger is the proxy mount, not the launcher.

**Supported workaround**: composite-mcp's **management-only mode** (no `COMPOSITE` env) routes through `leader-mcp` correctly (13 tools: `list_composites`, `create_composite`, `add_upstream`, `render_stock_summary`, …). For the `example` composite's proxied `akshare` tools, call `akshare` directly via `call_mcp(server="akshare", ...)`. A real fix (persistent client pool in composite-mcp, or leader-mcp-side nested-spawn handling) is deferred to a follow-up change.

**Alternatives considered**:
- Add a `LEADER_RECURSION_DEPTH` env var — over-engineering for a one-hop nesting.
- Exclude `composite-mcp` from the migration — sacrifices the single-entry-point goal and leaves a second client-facing MCP.

### Decision 5: Generic aliases live in `gateway_tools.py`, not a new file

**Chosen**: Add the 6 alias functions at the bottom of `gateway_tools.py`, register them in `server.py` next to the existing `*_data_mcp` registrations.

**Rationale**: Aliases are 2-line wrappers (`return list_data_mcps(include_disabled=include_disabled)`). A separate `gateway_aliases.py` would be indirection for indirection's sake.

**Alternatives considered**:
- New `gateway_aliases.py` module — unnecessary file, splits the gateway surface for no benefit.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Spawn latency on first `call_mcp` to `scrapling-docker-mcp` (docker image pull) | Document in README; the image is already pulled on this machine (it's in `.mcp.json` today). Pre-warm is a non-goal. |
| `composite-mcp` recursion if its upstreams ever include `leader-mcp` | Documented invariant; disjoint today; a loop would hang at spawn time and be obvious. |
| External scripts that spawn the 7 MCPs directly break | Audit `cron-mcp` job definitions and any `dashboard/` spawn calls before editing `.mcp.json`. `add-ai-chat` already spawns only `leader-mcp`. |
| `env` propagation for `composite-mcp` (`COMPOSITE=example`) | `build_client` already merges `env_json` with `os.environ`; verify in the post-seed check. |
| `ask_data_crew` crew routes only know the 10 data-fetch short names | Unchanged — the crew's knowledge is data-fetch-only by design; non-data MCPs are reached via direct `call_mcp`, not the crew. |
| Forgetting to re-run seed after adding a new MCP to `.mcp.json` | Seed is idempotent and cheap; document "run seed after editing `.mcp.json`" in the README. |

## File Structure

```
mcp/leader-mcp/
├── gateway_tools.py        # +6 generic alias functions (list_mcps, call_mcp, …)
├── seed_upstreams.py        # DATA_FETCH_MCPS dict → derived "all keys except leader-mcp"
├── server.py                # +6 app.add_tool() registrations for the generic aliases
└── README.md                # document single-entry-point usage + recursion constraint

.mcp.json                    # reduced from 8 entries to 1 (leader-mcp only)
```

No new files. No database schema change (`leader_upstreams` already has `env_json`, `cwd`, `transport`, `command`, `args_json`).

## Dependencies

No new dependencies. `fastmcp.Client`, `StdioTransport`, and SQLAlchemy are already in `leader-mcp`'s `pyproject.toml`.

## Migration Plan

1. Generalize `seed_upstreams.py` to derive the seed set from `.mcp.json` (all keys except `leader-mcp`), keeping the `DATA_FETCH_MCPS` short-name mapping for the 10 data-fetch MCPs.
2. Run `uv run --directory mcp/leader-mcp python seed_upstreams.py --dry-run` against the current 8-entry `.mcp.json`; confirm 7 planned upserts (the 10 data-fetch MCPs are already seeded from a prior run, so they'll show as updates).
3. Run the real seed; verify `list_mcps()` returns all 17 upstreams.
4. Add the 6 generic alias functions to `gateway_tools.py`; register them in `server.py`.
5. Verify `call_mcp(server="cron-mcp", tool="list_jobs", arguments='{}')` and `call_mcp(server="composite-mcp", ...)` succeed (the latter confirms `env` propagation).
6. Edit `.mcp.json` to keep only `leader-mcp`.
7. Re-verify a representative call to each of the 7 newly-routed upstreams.
8. Update `mcp/leader-mcp/README.md` with the single-entry-point usage and the composite-mcp recursion constraint.
9. Rollback path: `seed_upstreams.py --unseed` prints the `.mcp.json` snippet to restore direct connection.

## Open Questions

1. Should `list_mcps()` eventually also surface `leader-mcp` itself (as a self-referential entry)? — Lean no: `leader-mcp` is the entry point, not an upstream; surfacing it would invite accidental self-calls.
2. Should the `*_data_mcp` aliases emit a deprecation warning in a future change? — Defer; revisit once all internal callers migrate to `*_mcp` names.
3. Should the seed run automatically on `leader-mcp` startup if `leader_upstreams` is empty? — Lean no: startup side-effects are surprising for an MCP server; keep seeding explicit.
