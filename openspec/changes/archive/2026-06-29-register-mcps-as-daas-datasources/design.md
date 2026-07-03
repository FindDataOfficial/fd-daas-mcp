## Context

The daas-mcp registry now has the management capability (15 CRUD tools over `sources`, `categories`, `datasource_forms`, `datasource_sections`, `datasource_collections`, `datasource_collection_items`) and all FK/cascade invariants verified. What it lacks is *content*: the only rows are the three pre-seeded macro sources (`ckan`, `cnstats`, `worldbank`) and none of them has any forms or sections. Four sibling MCPs in this repo already serve the disclosure/market data that would naturally live here: `edgartools-mcp` (SEC EDGAR), `edinet-mcp` (Japan EDINET), `yfinance-mcp` (Yahoo Finance), `cnstats-mcp` (NBS China). Today they are not discoverable through daas-mcp at all — `search_datasources(form="10-K")` returns zero. Stakeholders: agents that traverse the daas registry to plan multi-source queries; the daas-mcp owner; the four sibling MCP owners (who must agree on the section→tool naming the seed encodes).

Constraints carried in from the proposal: no schema change, no new dependency, no coupling between MCPs at import time. The seed must be re-runnable on the live `daas.db` without producing duplicates or rolling back existing rows.

## Goals / Non-Goals

**Goals:**

- Make all four sibling MCPs discoverable from the daas-mcp registry via `list_sources`, `search_datasources`, `get_category_tree`, and `list_collection`.
- Encode each MCP's natural structure honestly: real "forms" (10-K, 10-Q, doc-type-120, etc.) where the upstream library has them; one synthetic `default` form where it doesn't (function-catalog MCPs).
- Capture *which sibling-MCP tool to call for each section* as the section's `instruction` string, so an agent reading the registry knows where to route the next call.
- Make the seed idempotent — re-runnable from CI, from a fresh clone after schema-only deletion, or after partial failure.

**Non-Goals:**

- Mirroring the sibling MCPs' full function catalogs into `daas_functions` / `daas_function_columns`. This change is about the disclosure-shaped surface (forms/sections), not the function-call surface.
- Live cross-MCP invocation from daas-mcp. The seed only stores names of tools to call; the agent dispatches.
- Schema changes, new tools, new MCPs, or any change to the four sibling MCPs themselves.
- Backfilling collections beyond a single `core` baseline. Curated collections per-use-case can be added later via the existing `create_collection` / `add_to_collection` tools.

## Decisions

**Decision 1: Seed via a standalone script under daas-mcp, not via auto-discovery at server startup.**
Chose a `mcp/daas-mcp/seed_external_mcps.py` invoked manually (or from CI), over having daas-mcp `server.py` introspect sibling MCPs at boot.
Rationale: daas-mcp must remain runnable when sibling MCPs are absent (different venvs, optional installs). Boot-time discovery couples startup to whether `edgartools` / `edinet_tools` / `dartlab` are importable in daas-mcp's venv — they shouldn't have to be. A standalone script is explicit, version-controlled, idempotent, and reviewable.
Alternatives: (a) generate from each sibling MCP's `mcp.yaml` at runtime — rejected, MCPs don't currently expose form/section metadata in their yaml; (b) write a JSON manifest per MCP and have daas read them all — rejected, four scattered files vs one seed script with no benefit.

**Decision 2: Use the existing registry service, not raw SQL.**
The seed imports `RegistryService` from `mcp/daas-mcp/registry_service.py` and calls `create_category` / `create_datasource` / `add_form` / `add_section` / `create_collection` / `add_to_collection`.
Rationale: cascade rules, uniqueness constraints, and cycle checks live in the service layer; bypassing it would mean re-implementing those checks. Going through the service also exercises the same paths the live MCP tools do, so the seed doubles as an integration smoke test.

**Decision 3: Idempotency by name lookup + UPSERT-style "create-or-get".**
For every entity, the seed first looks up by natural key (`name` for category/source/collection, `(source_id, form_type)` for forms, `(form_id, section_name)` for sections) and only creates when missing. For sections whose `instruction` changes between seed versions, the seed updates the instruction in place (the only mutable field on a section).
Rationale: lets the seed be re-run after we add more sections to a form, or after editing an instruction, without ever raising `IntegrityError` and without producing stale duplicates. Avoids the pain of writing migrations for what is essentially seed data.

**Decision 4: Section `instruction` is a structured one-liner naming the upstream MCP tool and its key argument.**
Format: `mcp=<mcp-name> tool=<tool-name> param=<key>=<value>` — e.g. `mcp=edgartools-mcp tool=get_filing param=form=10-K`. For sections that need agent-supplied input (e.g. a ticker), the instruction names the parameter without binding it: `mcp=edgartools-mcp tool=get_filing param=form=10-K param=ticker=<ask-agent>`.
Rationale: a free-form sentence ("call get_filing on edgartools") is harder for an agent to parse reliably; a tiny key=value grammar makes routing deterministic. Not introducing a separate column avoids schema change.

**Decision 5: Function-catalog MCPs (yfinance, cnstats) get a single `default` form whose sections mirror their top categories.**
yfinance has no filing-shaped concept — it's `Ticker(symbol).<method>()`. cnstats is similar (`call_cnstats_function`). Modeling each tool as a separate form would explode the form table and miscommunicate intent (a form is a *thing being filed*, not a *function*).
Rationale: keeps the form/section semantics honest for the filing-shaped MCPs (edgar, edinet) while giving function-catalog MCPs a uniform shape — one form per source, sections grouping their tools. Future use-cases that want richer modeling can add forms later; the schema permits it.

**Decision 6: Category tree is shallow (2 levels) and grouped by purpose × region.**
Top-level: `Filings`, `Market-Data`, `Macro`. Second level: `US-SEC`, `JP-EDINET`, `Global`, `China`. Each datasource is attached to exactly one leaf category.
Rationale: deeper trees lure us into modeling we don't have data for. Two levels comfortably split the four MCPs and leave headroom for the next four (KRX/dartlab-mcp → `Filings → KR-DART`; combine-mcp → not a datasource, doesn't go here).

## Risks / Trade-offs

- [Risk] The hand-curated section list for 10-K / 10-Q / EDINET doc types drifts from what the upstream libraries actually parse. → Mitigation: section `instruction` strings name the upstream tool by name, so when an agent calls and gets `tool not found`, the failure is loud at use time, not silent at seed time. Treat the seed as a living document; bump and re-run when sibling MCPs change tool names.
- [Risk] Sibling MCPs rename tools (e.g. `get_filing` → `fetch_filing`) and instructions silently lie. → Mitigation: ship a `--verify` mode in the seed that, for each section instruction, checks the named tool exists on the named MCP via that MCP's `mcp.yaml` (a JSON read, no MCP boot needed). Optional follow-up; this change only ships the seed plus naming convention.
- [Risk] The seed is re-run against a `daas.db` where someone has manually renamed `cnstats` (the existing row). Lookup-by-name then creates a second `cnstats` row. → Mitigation: rare edge case; the registry service already rejects duplicate `name`. The seed treats this as fatal and prints which row collides — manual fix is one `update_datasource` call.
- [Trade-off] Seeding by script (not by Alembic-style migration) means rolling back is a manual `DELETE` rather than a versioned down-migration. Acceptable because the existing daas-mcp schema lifecycle is also script-driven (`Base.metadata.create_all` + ad-hoc guarded ALTERs), so introducing migrations *only* for seed data would be inconsistent.
- [Trade-off] Encoding tool routing in a free-text `instruction` column rather than a typed foreign-key adds a parse step at agent time but avoids a schema change. A future spec can introduce a `tool_routings` table if instruction parsing turns out to be the bottleneck; nothing in this change forecloses that.

## Migration Plan

1. Land this change (proposal/design/specs/tasks reviewed).
2. Run `uv run python mcp/daas-mcp/seed_external_mcps.py` against the live `mcp/daas.db`. Idempotent — safe even if partially populated.
3. Verify with `list_sources`, `get_category_tree`, `search_datasources(form="10-K")`, `list_collection(name="core")`.
4. Rollback if needed: `python mcp/daas-mcp/seed_external_mcps.py --unseed` removes only rows the seed itself owns (looked up by the same natural keys), leaving the pre-existing `ckan`/`cnstats`/`worldbank` rows and any user-added rows intact.
5. After two weeks of stability, archive the change with `openspec archive`.

## Open Questions

- Should the `cnstats` row already in `sources` keep its current `label` / `description` / `url` (set by the daas seed), or be overwritten to match what `cnstats-mcp` reports? — Default: keep existing fields; only add `category_id`, form, and sections. Re-open if the existing label is wrong.
- Do we want `get_filing` sections in EDGAR to enumerate every Item 1 through Item 15, or stop at the ones that are typically the agent's target (1A, 7, 7A, 8)? — Default: full enumeration; agents can filter via `search_datasources(section=...)`.
