## Why

`massive-mcp` (a launch shim over the upstream `mcp_massive` package) and its `leader_upstreams` row were added in the archived `2026-07-03-add-massive-mcp` change, so `massive` is already reachable through `leader-mcp`'s gateway. But the second half of that change — registering `massive` as a daas datasource so agents discover it via `list_sources` / `search_datasources` / the `core` collection — was only drafted in the working tree (`mcp/daas-mcp/seed_external_mcps.py` has uncommitted edits, and the seed has been run once against `daas.db`). The `external-mcp-datasource-seed` spec still lists only six sibling MCPs; `massive` is not in the spec, so the registration is not a contract — it is a one-off live edit that a re-seed or fresh DB could silently drop. This change formalizes `massive` as the seventh datasource in the spec and commits the seed edits so the registration is reproducible and idempotent.

## What Changes

- `mcp/daas-mcp/seed_external_mcps.py` (commit the working-tree edits): add `massive` to `OWNED_SOURCES`; add a `massive` entry to the `SOURCES` dict (label `Massive.com`, category `Massive`); add a `Massive` leaf category under the existing `Market-Data` root; add a single `default` form for `massive` with three sections — `Search-Endpoints`, `Call-API`, `Query-Data` — each carrying a `mcp=massive-mcp tool=… param=<key>=<ask-agent>` routing instruction; add one `massive` / `Search-Endpoints` item to the `core` collection.
- `openspec/specs/external-mcp-datasource-seed/spec.md` (modified): extend the purpose, requirements, and scenarios to cover `massive` as the seventh sibling MCP (six → seven), including the `Market-Data → Massive` category grouping and the three-section `default` form.
- `mcp/daas.db`: already seeded (the `massive` `sources` row, `Massive` category, `default` form + 3 sections, and `core` collection item exist). This change makes that state reproducible from the seed rather than a manual artifact.
- No new code, no schema changes, no new MCPs, no `.mcp.json` change. `massive` is reached through `leader-mcp`, identical to the other ten data-fetch MCPs.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `external-mcp-datasource-seed`: The seed now also registers `massive` as a daas datasource — the seventh sibling MCP. Adds a `Massive` category under `Market-Data`, a single `default` form with three sections (one per `mcp_massive` composable tool: `search_endpoints`, `call_api`, `query_data`) whose `instruction` strings follow the existing `mcp=massive-mcp tool=… param=…` routing grammar, and one `massive` item in the `core` collection. The spec's datasource count moves from six to seven.

## Impact

- `mcp/daas-mcp/seed_external_mcps.py` (modified, ~25 lines: `OWNED_SOURCES`, `SOURCES["massive"]`, `MASSIVE_SECTIONS`, `Massive` category entry, `core` collection item, and the `massive` branch in the seed loop + the `7c. massive default form` block).
- `openspec/specs/external-mcp-datasource-seed/spec.md` (modified: purpose + requirements + scenarios gain `massive`).
- `mcp/daas.db` (data only — no schema change; the rows already exist and are reproducible by re-running the seed).
- Verification: `uv run --directory mcp/daas-mcp python seed_external_mcps.py --dry-run` (plan), then a re-run is a no-op on row counts (idempotency), and `sqlite3 mcp/daas.db` spot-checks for the `massive` source / form / sections / `core` item.
- No dependencies change; no other MCP is touched; `massive` is called as a client, not modified.
