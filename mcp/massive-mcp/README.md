# massive-mcp

A **launch shim** over the upstream [`mcp_massive`](https://github.com/massive-com/mcp_massive) MCP server (v0.10.0), not a hand-written server. `mcp_massive` is itself a complete MCP server distributed as a console script, so this directory just pins it and provides a uniform launch entry — matching how every other data-fetch MCP in this repo is isolated in its own `mcp/<name>-mcp/` venv.

## What it does

`server.py`:

1. Loads the unified repo-root `.env` (so `MASSIVE_API_KEY` enters the process env).
2. Fails fast with a clear message if `MASSIVE_API_KEY` is unset.
3. `os.execvp("mcp_massive", …)` — replaces its own process with the upstream server, inheriting stdio + env.

## API key

`MASSIVE_API_KEY` lives in the **repo-root `.env`** (gitignored — never committed). It is **not** stored in `leader_upstreams.env_json` or `mcp/daas.db`. `leader-mcp`'s gateway inherits its parent env to the spawned subprocess, so the key flows through with no `env_json` plumbing.

Get a key from <https://massive.com>.

## Tools (published by `mcp_massive` v0.10.0)

Three composable tools — reached through `leader-mcp`, not directly:

| Tool | Purpose |
|---|---|
| `search_endpoints` | Search API endpoints + built-in functions by natural-language query. |
| `call_api` | Call any Massive.com REST endpoint; optionally store results in an in-memory SQLite table. |
| `query_data` | Run SQL (`SHOW TABLES`, `DESCRIBE`, CTEs, window functions) over stored tables. |

```python
# Via leader-mcp's gateway:
call_data_mcp(server="massive", tool="search_endpoints",
              arguments='{"query":"aapl stock price","max_results":5}')
list_data_mcp_tools(server="massive")
```

## Run

```bash
# Uniform with the other data-fetch MCPs:
uv run --directory mcp/massive-mcp python server.py

# Offline self-check (no network, no real exec):
uv run --directory mcp/massive-mcp python server.py --selfcheck
```

## Registration

- **leader-mcp upstream**: seeded by `mcp/leader-mcp/seed_massive_upstream.py` (row `name="massive"`, `env=NULL`).
- **daas datasource**: seeded by `mcp/daas-mcp/seed_external_mcps.py` (source `massive`, category `Market-Data → Massive`, one `default` form with `Search-Endpoints` / `Call-API` / `Query-Data` sections, plus a `core` collection item).

## Notes

- Python 3.12+ (the upstream package's floor) — isolated in this MCP's own venv; uv resolves a 3.12+ interpreter automatically (same as `dartlab-mcp`).
- The upstream is experimental and could see breaking changes; the version is pinned to `v0.10.0`. Upgrade deliberately.
