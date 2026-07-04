## Context

`massive-mcp` is a launch shim over the upstream `mcp_massive` v0.10.0 package, added in the archived `2026-07-03-add-massive-mcp` change. That change shipped the shim, the `MASSIVE_API_KEY` env wiring, the `massive` row in `leader_upstreams` (seeded by `mcp/leader-mcp/seed_massive_upstream.py`), and the `massive-agent` specialist agent. What it did **not** ship was the daas-datasource half: the `seed_external_mcps.py` edits and the `external-mcp-datasource-seed` spec edits that register `massive` as the seventh sibling MCP were drafted in the working tree and the seed was run once against `mcp/daas.db`, but neither was committed nor captured as an opsx change. The result is a daas registry that advertises `massive` to agents today only because of an uncommitted, unspec'd live edit — a re-seed against a fresh DB would silently drop it.

This change formalizes that working-tree state. The seed script and spec edits already exist verbatim in the working tree (97 insertions across the two files, pure additions); the `daas.db` rows already exist (sources row id=25, `Massive` category, `default` form + 3 sections, one `core` collection item). The work is to capture the delta as an opsx change so `/opsx:apply` reproduces it from HEAD and the registration becomes a contract, not an artifact.

The relevant structures (verified against `daas.db` and `leader-mcp`):
- **`sources`** table: `id, name, label, description, url, enabled, config, category_id` — the daas datasource registry. `massive` is row id=25, `category_id=19`.
- **`datasource_forms`** / **`datasource_sections`**: forms group sections under a source; each section carries an `instruction` string in the routing grammar `mcp=<mcp> tool=<tool> param=<k>=<v>`.
- **`datasource_collections`** / **`datasource_collection_items`**: the `core` collection wires `(source, section)` pairs for a baseline cross-MCP view.
- **`leader_upstreams`**: the leader-mcp gateway registry (name, transport, command, args_json, env_json, enabled). The `massive` row here is owned by `seed_massive_upstream.py` — this change does **not** touch it.

## Goals / Non-Goals

**Goals:**
- Make `massive` a first-class, spec'd daas datasource — the seventh sibling MCP in `external-mcp-datasource-seed` — discoverable via `list_sources` / `search_datasources` / `get_category_tree` / `list_collection(name="core")`.
- Reproduce the current `daas.db` `massive` state purely from re-running `seed_external_mcps.py` (no manual SQL, no one-off live edit).
- Keep the change minimal: no new code paths, no schema changes, no new MCPs, no `.mcp.json` change.

**Non-Goals:**
- Registering `massive`'s tools as `daas_functions` rows. The other live-execution MCPs (`edgar`, `yfinance`, `edinet`, `hkex`, `cnreport`) use forms+sections with routing instructions, not the `daas_functions` catalog; `massive` follows the same pattern. (Only the harness-backed MCPs — `ckan`, `cnstats`, `worldbank` — populate `daas_functions`.)
- Touching the `massive` `leader_upstreams` row or the `massive-agent` specialist agent. Those are owned by `seed_massive_upstream.py` / `seed_specialist_agents.py` and are already committed.
- Building a general "add an upstream as a daas datasource" tool. (Explicitly the third option the user declined.)
- Changing `mcp_massive` itself or bumping the pinned version.

## Decisions

### Decision 1: `massive` gets a single `default` form, one section per composable tool

`mcp_massive` v0.10.0 exposes exactly three composable tools — `search_endpoints` → `call_api` → `query_data` — not a flat function catalog. The seed mirrors the established pattern for tool-countable MCPs (`yfinance`, `cnstats`): one `default` form, with sections grouping the upstream's tools by purpose. Each section carries a `mcp=massive-mcp tool=<tool> param=<k>=<ask-agent>` routing instruction, so an agent dispatched from `search_datasources` knows exactly which `leader-mcp` gateway tool to call and which params it must supply.

**Alternatives considered:**
- *One form per tool* (3 forms): rejected — `search_endpoints`, `call_api`, `query_data` are composable steps of one API surface, not independent report types like EDGAR's `10-K` / `10-Q` / `8-K`. A single `default` form matches how `yfinance`/`cnstats` model a tool surface.
- *No form, just `daas_functions` rows*: rejected — inconsistent with the other six live-execution MCPs and would require a new population path. Live-execution MCPs advertise their surface via forms+sections, not the function catalog.

### Decision 2: Section params use `<ask-agent>` for everything the agent must supply

`Search-Endpoints` → `param=query=<ask-agent>`; `Call-API` → `param=path=<ask-agent> param=method=<ask-agent>`; `Query-Data` → `param=sql=<ask-agent>`. This matches the routing grammar already used by every other seeded section (e.g. `edinet`'s `param=doc_type=<ask-agent>`, `cnreport`'s `param=source=<ask-agent>`). The seed does not pre-bind any massive param to a literal value, because every call's query/path/method/sql is request-specific.

### Decision 3: Category placement is `Market-Data → Massive`

`massive` is multi-asset market data (stocks, options, forex, crypto, futures, fundamentals, treasuries). It sits under the existing `Market-Data` root as a new `Massive` leaf, sibling to `Global` (which holds `yfinance`). This keeps the two-level category tree consistent: `Market-Data` groups cross-asset / global market-data sources; `Filings` groups per-jurisdiction disclosure; `Macro` groups statistical indicators.

**Alternative considered:** a new top-level `Multi-Asset` root — rejected as over-segmentation for a single source.

### Decision 4: `core` collection gets one `massive` / `Search-Endpoints` item

The `core` collection is the baseline cross-MCP view. Adding `("massive", "Search-Endpoints")` makes `massive` reachable from `list_collection(name="core")` and uses `Search-Endpoints` as the entry point (an agent searches endpoints, then `call_api` / `query_data` follow). One item mirrors the single-item contribution of `hkex` and `cnreport` to `core`.

### Decision 5: Formalize, do not re-implement

The seed script edits and spec edits already exist in the working tree (uncommitted). This change captures them as an opsx delta (proposal + design + specs + tasks) so `/opsx:apply` reproduces them from HEAD. The `daas.db` rows already exist from a prior seed run; `tasks.md` verifies idempotency (a re-run is a no-op on row counts) rather than re-creating them.

## Risks / Trade-offs

- **[Risk] The `daas.db` rows exist but the seed script that produces them is uncommitted.** → Mitigation: this change commits the seed script; `tasks.md` verifies a re-run is a no-op (idempotency is already a spec requirement) so committed-script + re-run == current DB state.
- **[Risk] `mcp_massive` is pinned to v0.10.0; if its tool surface changes, the hard-coded section names (`Search-Endpoints` / `Call-API` / `Query-Data`) and tool names (`search_endpoints` / `call_api` / `query_data`) drift from reality.** → Mitigation: the version is pinned in `mcp/massive-mcp/pyproject.toml`; the README flags "upgrade deliberately." A future bump would require re-checking the three sections here.
- **[Risk] `--unseed` of daas does not unseed the `massive` `leader_upstreams` row (owned by a different seed).** → Accepted trade-off: the two seeds are independent. After a daas `--unseed`, `massive` is simply not advertised as a datasource until re-seeded; the gateway still launches it fine. No cross-seed coupling is introduced.
- **[Trade-off] No `daas_functions` rows for `massive`** means `search_functions` / `get_function_detail` will not return `massive` tools. Accepted — consistent with the other six live-execution MCPs; the forms+sections path is the discovery surface for this class of MCP.

## Migration Plan

1. `/opsx:apply` merges the specs delta into the canonical `openspec/specs/external-mcp-datasource-seed/spec.md` (already matches the working tree, so this is a no-op on the file content) and confirms the `seed_external_mcps.py` edits are in place.
2. Verify the seed is idempotent against the current `daas.db`: re-run `seed_external_mcps.py` and confirm row counts are unchanged.
3. Commit `seed_external_mcps.py` + the spec together so the seed and its contract land in one revision.

**Rollback:** `uv run --directory mcp/daas-mcp python seed_external_mcps.py --unseed` removes the `massive` rows (source, `default` form, 3 sections, `core` item, `Massive` category leaf) without touching `ckan`/`cnstats`/`worldbank`. Revert the seed-script + spec commits to restore HEAD. The `massive` `leader_upstreams` row and `massive-agent` survive a daas-only rollback (they are owned by `seed_massive_upstream.py` / `seed_specialist_agents.py`).

## Open Questions

_None._ The working tree already reflects the intended end state; this change only formalizes it.
