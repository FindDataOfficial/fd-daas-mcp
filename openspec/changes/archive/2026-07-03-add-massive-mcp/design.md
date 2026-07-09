## Context

The project runs ~11 MCP servers. Ten data-fetch MCPs (akshare, yfinance, edgartools, edinet, dartlab, cnreport, hkreport, ckan, cnstats, worldbank) are **removed from `.mcp.json`** and reached through `leader-mcp`'s data gateway: their stdio launch configs live in the `leader_upstreams` table (`mcp/daas.db`), and `call_data_mcp(server, tool, arguments)` / `list_data_mcp_tools(server)` spawn each one on demand via `fastmcp.Client` over a stdio transport (`gateway_database.build_client`). Each is also advertised to agents as a daas datasource via `mcp/daas-mcp/seed_external_mcps.py` — a `sources` row plus `categories` / `datasource_forms` / `datasource_sections` rows whose `instruction` strings follow the routing grammar `mcp=<name>-mcp tool=<tool> param=<k>=<v>`, plus a `core` collection. A `seed_specialist_agents.py` loop auto-creates one CrewAI specialist agent per enabled upstream.

`mcp_massive` (v0.10.0, `github.com/massive-com/mcp_massive`) is a **pre-built MCP server** — not a Python library to wrap. It is distributed as a package whose console script `mcp_massive` (entry point `mcp_massive:main`) runs a stdio MCP server. It requires Python 3.12+ and a `MASSIVE_API_KEY` env var, and exposes exactly three composable tools: `search_endpoints` (discover API endpoints + built-in functions by NL query), `call_api` (call any Massive.com REST endpoint, optionally storing results in an in-memory SQLite table), and `query_data` (run SQL — `SHOW TABLES`, `DESCRIBE`, CTEs, window functions — over stored tables). Coverage spans stocks, options, forex, crypto, futures, fundamentals, analyst ratings/news, and treasuries — a superset of yfinance's market-data scope.

Constraints (from `CLAUDE.md` / `construction/mcp.md`): no schema changes when existing tables suffice; `Base.metadata.create_all` for new tables (none needed here); `.env` is gitignored and is the single source for secrets (root `.env` loaded by every MCP's `server.py` via `load_dotenv`); the `leader_upstreams.env_json` column holds literal env values and `mcp/daas.db` is **tracked in git**, so secrets must never live there.

A key property of `build_client`: when an upstream row has `env=NULL`, the spawned subprocess **inherits the parent (leader-mcp) process environment** outright. leader-mcp's own `server.py` loads root `.env` via `load_dotenv`, so any var in root `.env` — including `MASSIVE_API_KEY` — is already in leader-mcp's env and flows to the spawned `mcp_massive` subprocess with no `env_json` plumbing.

## Goals / Non-Goals

**Goals:**
- Make `mcp_massive` a first-class member of the project's data-fetch MCP fleet, reached through `leader-mcp` exactly like the other ten (uniform `uv run --directory mcp/<name>-mcp …` launch, gateway + specialist agent).
- Keep `MASSIVE_API_KEY` in the gitignored root `.env` only — never in `leader_upstreams.env_json`, `daas.db`, or any committed file.
- Advertise `massive` to agents as a daas datasource (category + form/sections with routing instructions + `core` collection item), so `search_datasources` / `list_collection` surface it.
- Stay idempotent and reversible: re-runnable seeders, `--unseed` rollback, no schema migration.

**Non-Goals:**
- No hand-written FastMCP server wrapping `mcp_massive`'s library internals — it is already a server; a wrapper would be pointless indirection.
- No `.mcp.json` entry for `massive` — it is reached through `leader-mcp`, matching the established gateway-only pattern for the other ten. The `claude mcp add massive …` command from the upstream README is superseded by gateway registration.
- No new shared-schema tables, no `mcp/models/models.py` change.
- No live API call in self-checks (the key is a secret; tests stay offline).
- No auto-discovery of `mcp_massive`'s tool list into the daas seed — tool names are hard-coded constants (the 3 documented tools), matching how every other source's seed works.

## Decisions

### D1. `mcp/massive-mcp/` is a launch shim, not a hand-written server
The directory holds a `pyproject.toml` that pins `mcp_massive @ git+https://github.com/massive-com/mcp_massive@v0.10.0` and a thin `server.py` that (a) loads root `.env` via `load_dotenv` (defensive — also makes the shim runnable standalone), (b) fails fast with a clear stderr message if `MASSIVE_API_KEY` is unset, then (c) `os.execvp("mcp_massive", ["mcp_massive"])` — replacing the process with the real server, inheriting stdio and the env (including the loaded key).

- **Why:** `mcp_massive` is already a complete MCP server; writing our own FastMCP server that re-exposes its 3 tools would duplicate its transport/serialization and couple us to its internals. The shim gives a uniform `uv run --directory mcp/massive-mcp python server.py` launch (matching edinet/dartlab/cnreport/hkreport) while delegating all server behavior to the upstream package.
- **Alternative:** register the globally-installed `mcp_massive` binary directly (`command="mcp_massive"`, no `--directory`), as the upstream README's `uv tool install` + `claude mcp add` flow suggests. Rejected — not reproducible across machines (depends on a one-time global install), doesn't pin the version in the repo, and breaks the `uv run --directory` convention every other data-fetch MCP uses.
- **Alternative:** import `mcp_massive` and call `mcp_massive.main()` in-process instead of `exec`. Rejected — `main()` may install signal handlers / call `sys.exit` that interfere with the host; `execvp` is a clean full-process handoff and is faithful to "run `mcp_massive` as the server".

### D2. Pin in an isolated 3.12+ venv (dartlab precedent)
`mcp/massive-mcp/pyproject.toml` declares `requires-python = ">=3.12"` and depends on `mcp_massive` (+ `python-dotenv`). `uv run --directory mcp/massive-mcp …` syncs an isolated venv; uv resolves a 3.12+ interpreter automatically even though the project default is 3.10+.

- **Why:** `mcp_massive`'s floor is 3.12 (its `pyproject.toml`); isolating it avoids forcing 3.12 on the rest of the project. This is exactly the `dartlab-mcp` pattern (`requires-python>=3.12`, "isolated in this MCP's own venv").
- **Alternative:** add `mcp_massive` to a shared venv. Rejected — raises the floor for unrelated MCPs and risks dep conflicts.

### D3. `MASSIVE_API_KEY` in root `.env`; `leader_upstreams.env_json = NULL`
The key is added to the gitignored root `.env`. The `massive` upstream row carries `env=NULL`, so `build_client` lets the subprocess inherit leader-mcp's env, where `MASSIVE_API_KEY` already lives after leader-mcp's `load_dotenv`. The shim's own `load_dotenv` is a belt-and-suspenders fallback for standalone runs.

- **Why:** keeps the secret out of `daas.db` (tracked) and out of committed files; reuses the existing env-inheritance path already proven for the other ten (their `EDGAR_IDENTITY`, `DART_API_KEY`, `LLM_*` all flow the same way).
- **Alternative:** store `{"MASSIVE_API_KEY": "…"}` in `env_json`. Rejected — `mcp/daas.db` is committed (`M mcp/daas.db` in git status), so the key would be committed too.
- **Alternative:** a per-MCP `mcp/massive-mcp/.env` holding the key. Rejected — the project's single-source convention is root `.env`; a per-MCP file risks drift and is redundant given env inheritance.

### D4. Register the upstream via a dedicated `seed_massive_upstream.py`
A new `mcp/leader-mcp/seed_massive_upstream.py` upserts the `massive` row into `leader_upstreams` (idempotent on `name`, with `--dry-run` / `--unseed`). It does NOT extend `seed_upstreams.py`, because that script's contract is "migrate `.mcp.json` → `leader_upstreams`", and `massive` was never in `.mcp.json`.

- **Why:** self-contained, matches the seeding-script convention (`seed_upstreams.py`, `seed_specialist_agents.py`, `seed_external_mcps.py`), and avoids polluting `.mcp.json` with a transient entry that would then need removal.
- **Alternative:** add a `massive` entry to `.mcp.json` and let `seed_upstreams.py` migrate it. Rejected — the ten data-fetch MCPs were deliberately moved OUT of `.mcp.json`; adding then removing a `.mcp.json` entry is needless churn and risks a leftover entry that Claude Code would try to auto-start.
- The launch config: `name="massive"`, `transport="stdio"`, `command="uv"`, `args=["run","--directory","<repo>/mcp/massive-mcp","python","server.py"]`, `env=NULL`, `enabled=True`.

### D5. daas source: single `default` form, three composable-tool sections, `Market-Data → Massive` category
Mirroring the yfinance/cnstats pattern (single `default` form, one section per tool) rather than the edinet/cnreport per-doc-type pattern — because `mcp_massive`'s three tools are composable (search → call → query), not per-document-type. Sections:
- `Search-Endpoints` → `mcp=massive-mcp tool=search_endpoints param=query=<ask-agent>`
- `Call-API` → `mcp=massive-mcp tool=call_api param=path=<ask-agent> param=method=<ask-agent>`
- `Query-Data` → `mcp=massive-mcp tool=query_data param=sql=<ask-agent>`

Category: new leaf `Massive` (label "Massive.com") under the existing root `Market-Data` (sibling to `Global` which holds yfinance).

- **Why:** the `default`-form pattern is the established shape for "one MCP, several tools" sources; the 3 documented tools are stable in v0.10.0 and map cleanly to one section each. `Market-Data` is the right root (massive is multi-asset market data); a sibling leaf keeps yfinance and massive distinct.
- **Alternative:** enumerate `mcp_massive`'s full endpoint surface as forms. Rejected — the surface is dynamically indexed at startup from `llms.txt` and is large/changing; the 3-tool composable model is the intended entry point. An agent uses `search_endpoints` to discover endpoints, so the seed should expose `search_endpoints`, not duplicate the index.
- The `mcp=massive-mcp` instruction prefix follows the `-mcp`-suffix convention used by every other seeded source (`edgartools-mcp`, `edinet-mcp`, …); `leader_upstreams.name` is the suffix-less `massive` (matching `edgartools`/`edinet`/…). The agent bridges the two via `list_data_mcps` — same as today.

### D6. Specialist agent auto-seeded (no new code)
`seed_specialist_agents.py` already loops over enabled upstreams and creates `<upstream>-agent`. Re-running it after D4 creates `massive-agent` (non-registry branch: `list_tools_massive` + `call_data_mcp_massive`). No specialist-agent code change.

## Risks / Trade-offs

- **[Upstream is experimental]** `mcp_massive`'s README says "experimental and could be subject to breaking changes." → Pin to the `v0.10.0` tag (not a moving branch); upgrades are deliberate. The 3 documented tools are stable as of that tag.
- **[Cold-start latency]** `uv run --directory` syncs the `mcp/massive-mcp` venv on first call (downloads `mcp_massive` + deps). The upstream README warns this can exceed a 30s connection timeout for `uvx`/`uv run --with`. → leader-mcp launches upstreams **on demand** (not at Claude Code startup), so a slow first call does not block startup; subsequent calls reuse the synced venv. Apply step pre-runs `uv sync` in `mcp/massive-mcp/` so the first gateway call is warm.
- **[Tool-surface drift]** If a future `mcp_massive` version renames `search_endpoints`/`call_api`/`query_data`, the daas section instructions break. → Pin to v0.10.0; `list_data_mcp_tools(server="massive")` lets the agent discover the live tool list, and the routing-grammar requirement still holds (a renamed tool is still a valid `tool=` token, just not pre-documented).
- **[Secret leakage]** The API key must not be committed. → Key lives only in gitignored root `.env` (`.gitignore` lines 9–12 exclude `.env`/`.env.*`); seeders reference `$MASSIVE_API_KEY`/`<ask-agent>`, never the literal; `env_json=NULL`. Verified: `git ls-files .env` returns nothing.
- **[Python 3.12 floor]** Hosts without a 3.12+ interpreter cannot run the shim. → uv fetches a managed 3.12+ interpreter for the isolated venv (no system-python change); dartlab already depends on this.
- **[daas seed order]** `seed_external_mcps.py` is extended; a partial run could leave a `massive` source with no forms. → The seed's existing get-or-create + transactional per-source commit pattern already handles this; idempotent re-run completes the set.

## Migration Plan

**Apply (forward):**
1. Create `mcp/massive-mcp/{pyproject.toml,server.py,README.md}`.
2. `uv sync` in `mcp/massive-mcp/` (pre-warm the venv so the first gateway call isn't slow).
3. Add `MASSIVE_API_KEY=<user-provided value>` to root `.env`.
4. `uv run --directory mcp/leader-mcp python seed_massive_upstream.py` (upserts the `massive` `leader_upstreams` row).
5. `uv run --directory mcp/leader-mcp python seed_specialist_agents.py` (creates `massive-agent`).
6. `DAAS_DATABASE_URL="sqlite:///$(pwd)/mcp/daas.db" uv run --directory mcp/daas-mcp python seed_external_mcps.py` (seeds the `massive` source + category + form/sections + `core` item).
7. Smoke check: `list_data_mcps()` returns `massive`; `list_data_mcp_tools(server="massive")` returns the 3 tools (requires the key set).

**Rollback:**
1. `seed_external_mcps.py --unseed` (removes only the `massive` daas rows it owns + the `Massive` category leaf).
2. `seed_massive_upstream.py --unseed` (removes the `leader_upstreams` row).
3. `seed_specialist_agents.py --unseed` (or manually delete `massive-agent`).
4. Remove the `MASSIVE_API_KEY` line from `.env`.
5. `rm -rf mcp/massive-mcp/`.

## Open Questions

- None blocking. (The user's pasted `claude mcp add massive …` command is the upstream's install reference; this design supersedes it with gateway-only registration, consistent with the other ten data-fetch MCPs. If direct Claude-Code-side registration is later desired, it can be added as a separate `.mcp.json` entry without touching this design.)
