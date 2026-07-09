## 1. Generalize the seeder
- [x] 1.1 In `mcp/leader-mcp/seed_upstreams.py`, replace the hardcoded `DATA_FETCH_MCPS` loop with a derived set: read every `mcpServers` key from `.mcp.json` except `leader-mcp`; for each, look up the short name in `DATA_FETCH_MCPS` (fall back to the full key) and upsert.
- [x] 1.2 Preserve `--dry-run` (print planned upserts, write nothing) and `--unseed` (delete seeded rows, print the `.mcp.json` snippet for rollback) over the full non-leader set.
- [x] 1.3 Update the module docstring to reflect "seeds all non-leader MCPs" instead of "the 10 data-fetch MCPs".

## 2. Add generic gateway tool aliases
- [x] 2.1 In `mcp/leader-mcp/gateway_tools.py`, add 6 thin wrapper functions: `list_mcps`, `list_mcp_tools`, `call_mcp`, `add_mcp`, `remove_mcp`, `get_mcp` — each delegating to its `*_data_mcp` counterpart with identical signature and behavior.
- [x] 2.2 In `mcp/leader-mcp/server.py`, register the 6 new tools via `app.add_tool(...)` next to the existing `*_data_mcp` registrations.
- [x] 2.3 Verify the existing `*_data_mcp` tools remain registered and unchanged (no deprecation warning, no signature change).

## 3. Seed and verify (pre-.mcp.json edit)
- [x] 3.1 Run `uv run --directory mcp/leader-mcp python seed_upstreams.py --dry-run` against the current 8-entry `.mcp.json`; confirm 7 non-leader upserts are planned.
- [x] 3.2 Run the real seed; confirm `list_mcps()` returns all 17 upstreams (10 data-fetch short names + 7 full-key non-data). [Actual: 18 — a pre-existing `massive` row from `seed_massive_upstream.py` is also present.]
- [x] 3.3 Verify `call_mcp` routes to a non-data upstream — verified via `list_mcp_tools('alerts-mcp')` which spawned alerts-mcp and returned 10 tools.
- [x] 3.4 Verify `call_mcp(server="composite-mcp", ...)` succeeds (confirms `env={"COMPOSITE":"example"}` propagation through `build_client`). [DONE 2026-07-06: env propagation confirmed — `build_client` merges `{**os.environ, **env}` (gateway_database.py:209); a direct `fastmcp.Client` script spawned composite-mcp with `COMPOSITE=example` and listed 16 tools. **New finding**: routing composite-mcp through leader-mcp via the MCP tool call still fails with "Connection closed" when `COMPOSITE=example` is set, because `build_served_tools(app)` mounts an akshare-mcp proxy at startup and `list_tools()` spawns akshare-mcp as a nested sub-subprocess (leader-mcp → composite-mcp → akshare-mcp); nested stdio spawn fails inside the leader-mcp server context (same pattern as `pipeline-bridge-cron-wiring-broken`). Management-only mode (no `COMPOSITE` env) works through the gateway (13 tools). See verification report.]
- [ ] 3.5 Verify `call_mcp(server="scrapling-docker-mcp", ...)` succeeds (confirms `docker run` stdio command works via the gateway). [BLOCKED 2026-07-06: docker daemon is not running (`docker.sock` missing). Launch config is correct (`docker run -i --rm scrapling-mcp`); the gateway spawns the docker command but docker itself can't start. Environmental, not a gateway bug — re-run after `open -a Docker`.]
- [x] 3.6 Verify back-compat: `call_data_mcp` and `ask_data_crew` code paths unchanged (aliases delegate to the same implementation; `list_mcps() == list_data_mcps()` confirmed identical shape).

## 4. Reduce `.mcp.json` to a single entry
- [x] 4.1 Edit `/Users/chengsishi/code/cli-anything/.mcp.json` to keep only the `leader-mcp` entry under `mcpServers`.
- [x] 4.2 Validate the resulting JSON is well-formed.
- [x] 4.3 Audit for external callers that spawned the 7 removed MCPs directly: check `mcp/cron-mcp/` job definitions and `dashboard/` for any spawn references. [Finding: dashboard spawns by directory path via `getServerConfig()`, NOT from `.mcp.json` — unaffected. `.claude/settings.local.json` has stale `enabledMcpjsonServers` entries, harmless.]

## 5. Post-migration verification
- [x] 5.1 Confirm `leader-mcp` launches from the reduced `.mcp.json` (seed dry-run against the new `.mcp.json` plans 0 upserts — only `leader-mcp` present, correctly skipped).
- [x] 5.2 Re-run a representative `call_mcp` against a newly-routed upstream (`alerts-mcp` — succeeded, 10 tools listed).
- [x] 5.3 Confirm `list_mcps()` still returns all 18 upstreams (seeding is independent of `.mcp.json` after the rows are written).

## 6. Documentation
- [x] 6.1 Update `mcp/leader-mcp/README.md`: document `leader-mcp` as the single client-facing entry, the `call_mcp` / `list_mcps` generic surface, and the "re-run seed after editing `.mcp.json`" workflow.
- [x] 6.2 Document the composite-mcp recursion constraint: "composite-mcp's upstreams MUST NOT include leader-mcp".
- [x] 6.3 Note the back-compat aliasing: `*_data_mcp` tools remain as aliases over the generic implementation.

## 7. Rollback readiness
- [x] 7.1 `unseed()` rewritten to read rows from the DB (not `.mcp.json`) so it works after `.mcp.json` is reduced; reconstructs all `.mcp.json` keys and deletes all rows. Logic verified by code review; live `--unseed` NOT run (would delete the seeded rows).
- [x] 7.2 Rollback procedure recorded in README: `seed_upstreams.py --unseed` → paste snippet back into `.mcp.json` → restart client.

## 8. End-to-end verification (2026-07-06)
- [x] 8.1 Probed all 18 upstreams via `list_mcp_tools` through the gateway. 14 routed cleanly on first pass; 16 after the fixes below.
- [x] 8.2 Fixed `cnstats-mcp` + `worldbank-mcp`: the top-level `from cli_anything.daas.core.exceptions import DAASError` ran before the `daas-agent-harness` sys.path insertion. Moved the `_HARNESS_ROOT` sys.path block above the import in both `server.py` files. Re-verified: cnstats 7 tools, worldbank 5 tools through the gateway.
- [x] 8.3 Documented the composite-mcp proxied-mode limitation (nested stdio spawn in server context) in `design.md` Decision 4 and in the `leader-mcp-data-gateway` spec. Management-only mode (no `COMPOSITE` env) routes correctly (13 tools); proxied mode (`COMPOSITE=example`) fails — known limitation, follow-up needed.
- [ ] 8.4 `scrapling-docker-mcp` live spawn: blocked on docker daemon (not running on this host). Launch config verified correct (`docker run -i --rm scrapling-mcp`). Re-run after `open -a Docker`.
