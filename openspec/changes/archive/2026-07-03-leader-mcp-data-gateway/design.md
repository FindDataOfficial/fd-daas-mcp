## Context

Today Claude Code and the dashboard connect **directly** to every MCP server via `.mcp.json`. Ten of those are pure data-fetch MCPs — `akshare`, `yfinance`, `edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank` — contributing ~60+ live-data tools to the client's tool surface, each spawned as a separate stdio subprocess at client startup. The client (or the user) must know which server + tool serves each data request.

`leader-mcp` already exposes registry **metadata** tools (`search_functions`, `get_function_detail`, `list_harnesses`, …) over a FastMCP stdio server, and ships a `LeaderCrew` (CrewAI) that routes metadata questions — but it never executes live data calls. CrewAI is **not** currently in `leader-mcp`'s `pyproject.toml`; `leader_crew.py` imports it lazily and falls back to a direct router when unavailable.

The cross-MCP call primitive this gateway needs already exists in the repo:
- `mcp/combine-mcp/combine_database.py` → `build_transport(upstream)` + `build_client(upstream)` build a `fastmcp.Client` over a `StdioTransport` (or `StreamableHttpTransport`) from a config dict, opened per call via `async with client:`.
- The in-flight `add-cron-mcp-data-fetch` change reuses the same primitive for scheduled fetches.

So this change adds a new gateway + CrewAI router in `leader-mcp` over an already-proven primitive. Constraints: single shared `.env`, single `mcp/daas.db`, shared schema package `mcp/models/`, no Alembic (guarded `ALTER TABLE` / `create_all` only), CrewAI requires Python <3.14 (leader-mcp is 3.11+ — fine).

## Goals / Non-Goals

**Goals:**
- `leader-mcp` is the single client-facing entry point for live data from the 10 data-fetch MCPs.
- A CrewAI agent manages access: takes a NL data request, finds the right upstream+tool via the existing registry tools, calls it via `fastmcp.Client`, returns the data.
- Also expose deterministic gateway tools (`call_data_mcp`, `list_data_mcp_tools`, `list_data_mcps`) for callers that already know the server+tool.
- Upstream launch configs live in `daas.db` (not `.mcp.json`), seeded from the current `.mcp.json` entries so nothing is lost.
- Remove the 10 data-fetch MCPs from `.mcp.json`. The MCP servers themselves stay on disk, launched on demand by `leader-mcp`.

**Non-Goals:**
- Not modifying the data-fetch MCP servers themselves — they are called as clients, verbatim.
- Not mounting upstream tools verbatim into `leader-mcp`'s surface (that is `combine-mcp`'s job). `leader-mcp` exposes a small, stable tool surface and calls upstreams dynamically.
- Not scheduling fetches (that is `add-cron-mcp-data-fetch`'s job). This gateway is on-demand only.
- Not touching `cron-mcp`, `daas-mcp`, `dashboard-mcp`, `combine-mcp`, `process-mcp`, `scrapling-*-mcp` — they stay in `.mcp.json`.

## Decisions

### Decision 1: Gateway lives inside `leader-mcp`, not a new MCP
Reuse `leader-mcp`'s existing FastMCP server, its registry tools (for routing), and its CrewAI scaffolding. A new MCP would duplicate the registry-tool imports and add another stdio entry to `.mcp.json` — the opposite of consolidating.
- *Alternative*: a new `gateway-mcp`. Rejected — duplicates `leader-mcp`'s role as orchestrator and fragments the tool surface.

### Decision 2: Upstream configs stored in `daas.db` (`leader_upstreams` table), not a JSON file
Matches `combine-mcp`'s `upstreams`-in-`daas.db` pattern and the project's "single database" rule. CRUD-able via management tools (`add_data_mcp`/`remove_data_mcp`/`get_data_mcp`), survives restarts, queryable via `dashboard-mcp.query_table`.
- *Alternative*: a `leader_upstreams.json` file. Simpler, but not tool-editable, diverges from the project's DB-backed-config convention (combine-mcp, daas-mcp), and cannot be inspected from the dashboard. Rejected.

### Decision 3: `fastmcp.Client` opened **per call**, not a persistent pool
Directly reuse `combine_database.build_client`'s shape: build a `Client(StdioTransport(...))` and `async with client:` around the call. Data fetch is not a hot path; spawn latency (~hundreds of ms) is acceptable for on-demand queries. Per-call open avoids orphaned subprocesses and stale-tool-list drift.
- *Alternative*: a persistent client pool keyed by upstream. Premature now; can be added later if spawn latency hurts. The `build_client` docstring already flags this ("persistent client if spawn latency matters").

### Decision 4: CrewAI `DataCrew` with a deterministic direct-router fallback
`data_crew.py` mirrors `leader_crew.py`: try CrewAI; on `ImportError`/error, fall back. The CrewAI crew is a Manager + DataFetcher: Manager reads the NL request, uses registry tools to identify the upstream+tool+arguments, delegates the actual call. The fallback router does the same mapping with keyword/regex heuristics over the registry. Both paths terminate in `call_data_mcp(server, tool, arguments)` — one execution primitive, two routing strategies.
- *Alternative*: CrewAI-only. Rejected — `crewai` is heavy, py<3.14-pinned, and not currently installed; a hard dependency would break `leader-mcp` for anyone who hasn't installed it. The fallback keeps the gateway working and matches the existing `LeaderCrew` pattern.

### Decision 5: Small stable tool surface, dynamic upstream calls (not verbatim mount)
`leader-mcp` exposes 4 gateway tools (`list_data_mcps`, `list_data_mcp_tools`, `call_data_mcp`, `ask_data_crew`) + 3 management tools (`add_data_mcp`, `remove_data_mcp`, `get_data_mcp`). Upstream tools are **not** mounted into `leader-mcp`'s surface; they are called dynamically via `call_data_mcp`. This keeps the client-facing surface small and stable regardless of how many tools the upstreams expose.
- *Alternative*: mount all upstream tools verbatim (`combine-mcp` style, `<server>_<tool>`). Rejected — that would re-flatten ~60+ tools back into the client surface, defeating the consolidation goal.

### Decision 6: `seed_upstreams.py` migrates `.mcp.json` → `leader_upstreams`, then `.mcp.json` is edited to remove the entries
Two steps, deliberately separate: (1) `seed_upstreams.py` reads the 10 data-fetch entries from `.mcp.json` and idempotently upserts them into `leader_upstreams` (so the launch config is preserved in DB before any removal); (2) the `.mcp.json` file edit removes those entries. `--dry-run` plans; `--unseed` removes the rows and prints the `.mcp.json` snippet for rollback. The current `.mcp.json` data-fetch entries carry **no `env`** (only `combine-mcp` has `env`), so the seed carries no env — but the `leader_upstreams.env_json` column exists for future per-upstream env overrides (e.g. `EDGAR_IDENTITY`, `EDINET_API_KEY`) if dotenv loading is ever insufficient.

### Decision 7: Two upstream tool shapes — direct tools vs registry-dispatch tools
`call_data_mcp(server, tool, arguments)` calls whatever *tool* the upstream exposes. The 10 upstreams split into two shapes:
- **Purpose-built MCPs** (`edgartools`, `edinet`, `dartlab`, `cnreport`, `hkreport`, `ckan`, `cnstats`, `worldbank`) expose **direct per-operation tools** (`get_company`, `list_filings`, `get_financials`, …) — `call_data_mcp(server, "get_company", '{"ticker_or_cik":"AAPL"}')` works directly.
- **Registry-based MCPs** (`yfinance`, `akshare`) expose a **single dispatch tool** (`call_yfinance_function` / `call_akshare_function`) that takes a function `name` + `params_json` — so `ticker_history` is a *function name argument*, not a tool. The call is `call_data_mcp("yfinance", "call_yfinance_function", '{"name":"ticker_history","params_json":"{\"symbol\":\"AAPL\",\"period\":\"1mo\"}"}')`.

The DataCrew router (both CrewAI and direct fallback) must know which shape each upstream has: for registry-based upstreams it routes via the dispatch tool; for purpose-built upstreams it calls the direct tool. This is encoded as a small per-upstream shape map in `data_crew.py`. The gateway itself (`call_data_mcp`) stays shape-agnostic — it just calls the named tool.

## Risks / Trade-offs

- **[CrewAI heavy dep, py<3.14 pin]** → `crewai` is an optional extra; the direct-router fallback means the gateway works without it. Documented in `pyproject.toml` and `data_crew.py`.
- **[Per-call stdio spawn latency]** → acceptable for on-demand data fetch. If it hurts, add a persistent client (the `build_client` docstring already anticipates this). No silent degradation.
- **[Upstream subprocess orphans on error]** → every call uses `async with client:`, which tears down the subprocess on exit/exception. No daemon lifecycle to manage.
- **[BREAKING: clients lose direct access to data-fetch MCPs]** → migration guide in `tasks.md`; the 4 gateway tools cover all call patterns (`call_data_mcp` is a strict superset of direct access). `seed_upstreams --unseed` restores the `.mcp.json` snippet for rollback.
- **[Tool discovery drift between registry and live upstream]** → `list_data_mcp_tools` is **live** (calls the upstream), so it always reflects the upstream's current tools. The registry (`search_functions`) is metadata-only and may lag; the CrewAI router uses registry for routing but `call_data_mcp` for execution, so a stale registry entry degrades routing, not execution.
- **[Env/identity propagation]** → data-fetch MCPs load root `.env` themselves via dotenv (existing behavior); leader-mcp launching them via stdio does not change that. `leader_upstreams.env_json` is a future escape hatch, not required for parity.
- **[CrewAI + chromadb/pydantic-v1 install friction]** → pin `crewai` to a version known to work on 3.11–3.13; if install fails, the fallback router still serves the gateway. Document the pin in `pyproject.toml`.

## Migration Plan

1. **Add the gateway code** (`gateway_tools.py`, `data_crew.py`, `gateway_database.py`, model, server wiring, `seed_upstreams.py`). No `.mcp.json` change yet — `leader-mcp` still connects directly.
2. **Install `crewai`** in the `leader-mcp` venv (`uv pip install crewai`); verify import. If it fails, the fallback router is exercised instead.
3. **Seed**: `uv run --directory mcp/leader-mcp python seed_upstreams.py --dry-run` → review → run for real. Verify `leader_upstreams` has 10 rows.
4. **Verify gateway tools** against a live upstream: `call_data_mcp("yfinance", "ticker_history", '{"symbol":"AAPL","period":"1mo"}')` and `ask_data_crew("get AAPL 1-month price history")`.
5. **Edit `.mcp.json`**: remove the 10 data-fetch MCP entries. Restart the client. Confirm `leader-mcp` (and the non-data-fetch MCPs) still connect.
6. **Rollback** (if needed): `seed_upstreams.py --unseed` prints the `.mcp.json` snippet to restore; re-add the entries and restart.

## Open Questions

- Exact removal list: the 10 named above are the default. Confirm whether `akshare-mcp` (registry-based, like yfinance) should also be routed — proposal assumes **yes**.
- Should `ask_data_crew` return raw upstream JSON or a CrewAI-synthesized natural-language summary? Default: raw JSON (deterministic, tool-friendly); the CrewAI agent's synthesis is the *routing* step, not the *format* step.
