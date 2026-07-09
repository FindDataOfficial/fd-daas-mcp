## Why

`process-mcp` and `daas-mcp` both read/write the same `mcp/daas.db`, share the same `models` package, and mirror each other's database plumbing (relative-URL resolution, `PRAGMA foreign_keys`, identifier guard, `--run-*` CLI branches for cron). Keeping them separate doubles the surface area for no architectural benefit: two `.mcp.json` entries, two stdio processes, two selfchecks, and a "daas-traceability exemption" that exists only because the indicator path lives outside daas-mcp. Folding process-mcp's 19 tools into daas-mcp collapses the duplication, removes one MCP from the registry, and makes `observations` writes native to daas-mcp instead of an exempted cross-MCP write.

## What Changes

- **MOVE** all 19 process-mcp tools onto `daas-mcp`:
  - LLM extraction (11): `list_models`, `list_source_tables`, `create_rule`, `list_rules`, `get_rule`, `update_rule`, `delete_rule`, `run_rule`, `extract_text`, `extract_image`, `extract_file`
  - Math indicators (8): `list_indicator_ops`, `create_indicator`, `list_indicators`, `get_indicator`, `update_indicator`, `delete_indicator`, `run_indicator`, `calculate`
- **MOVE** the two cron CLI branches onto daas-mcp's `server.py` arg parser: `--run-rule <name>` and `--run-indicator <name>` (alongside the existing `--fetch-item` / `--register-cron` / `--unregister-cron` / `--sync-cron`).
- **MOVE** the implementation files into `mcp/daas-mcp/`: `process_tools.py`, `indicator_tools.py`, and the process-owned parts of `process_database.py` (rule/result/indicator CRUD + `run_indicator` + `observations` upsert + source-table discovery). The `ProcessDatabase` singleton merges into daas-mcp's `Database` (or is kept as a thin companion class sharing the daas engine).
- **KEEP** the three owned tables — `process_rules`, `process_results`, `indicator_rules` — unchanged in `daas.db` (no rename, no schema change). The ORM classes in `mcp/models/models.py` stay; only their owning MCP changes.
- **KEEP** the `PROCESS_MODELS` env-var name (avoids breaking existing `.env` files; it still names the LLM registry for the extraction path).
- **DELETE** `mcp/process-mcp/` entirely (server, tools, db, selfcheck, pyproject, uv.lock). **BREAKING** for any caller that spawns `process-mcp` by name.
- **REMOVE** the `process-mcp` entry from `.mcp.json`. **BREAKING** for any external client registered against it.
- **REPOINT** the dashboard: 12 `callTool('process-mcp', …)` calls across 6 API routes + `server-data.ts` switch to `'daas-mcp'`; update 2 user-facing "process-mcp unavailable" strings and a handful of comments.
- **MIGRATE** any existing `cron-mcp` task rows whose `command` points at `mcp/process-mcp` to point at `mcp/daas-mcp` (data-dependent; the daas-mcp `--run-rule`/`--run-indicator` branches keep the same CLI shape).
- **UPDATE** docs: rewrite the `mcp/process-mcp/` section of `CLAUDE.md` into a `process tools` subsection under `mcp/daas-mcp/`; update `construction/daas-storage.md` §6 attribution; refresh "mirrors process-mcp" comments in leader-mcp, daas-mcp, and `mcp/models/`.

## Capabilities

### New Capabilities

- `daas-llm-extraction`: The 11 LLM-extraction tools (multi-model registry via `PROCESS_MODELS`, chunked map-reduce `extract_text`, vision `extract_image`, file `extract_file`, persisted `*_rule` CRUD with incremental `run_rule`) now exposed by `daas-mcp`. Includes the `--run-rule` cron CLI branch.
- `daas-indicators`: The 8 deterministic-math indicator tools (fixed op catalog, `*_indicator` CRUD, full-recompute `run_indicator` → `observations` upsert, ad-hoc `calculate`) now exposed by `daas-mcp`. Includes the `--run-indicator` cron CLI branch.

### Modified Capabilities

- `process-mcp-server`: All requirements REMOVED — tools and `--run-rule` branch relocate to `daas-llm-extraction`. The spec is emptied (process-mcp no longer exists).
- `process-mcp-indicators`: All requirements REMOVED — tools and `--run-indicator` branch relocate to `daas-indicators`. The spec is emptied.
- `process-dashboard-ui`: The `/process/rules` and `/process/indicators` pages' backing API routes now proxy to `daas-mcp` instead of `process-mcp`; the "server unavailable" fallback strings and picker calls update accordingly. (UI shape unchanged.)
- `leader-mcp-data-gateway`: The requirement listing `process-mcp` among non-data-fetch MCPs that stay in `.mcp.json` is updated to remove `process-mcp`.

## Impact

- **`mcp/daas-mcp/`** — gains `process_tools.py`, `indicator_tools.py`, merged database code, 19 new `app.tool()` registrations, 2 new CLI branches; `pyproject.toml` gains `httpx`, `jsonschema`, `pypdf`, `python-dotenv` (pandas + sqlalchemy + fastmcp already present). Tool count 37 → 56.
- **`mcp/process-mcp/`** — deleted.
- **`mcp/models/`** — no schema change; domain comments in `__init__.py` / `models.py` updated from "process-mcp" to "daas-mcp (process tools)".
- **`.mcp.json`** — `process-mcp` entry removed.
- **`dashboard/`** — 6 API route files + `server-data.ts` repointed; 2 UI strings + ~6 comments updated. No route-path or component-structure change.
- **`mcp/daas.db`** — no schema change. Existing `cron-mcp` `tasks` rows referencing `mcp/process-mcp` need their `command` column rewritten to `mcp/daas-mcp` (one-shot migration; covered in tasks).
- **`CLAUDE.md`**, **`construction/daas-storage.md`**, **`construction/mcp.md`** — section rewrites/attribution updates.
- **`openspec/specs/process-mcp-server/`**, **`openspec/specs/process-mcp-indicators/`** — emptied (requirements relocated).
- **Dependencies** — daas-mcp gains `httpx`/`jsonschema`/`pypdf` (LLM path only; indicator path adds nothing new). No new transitive risk; these are already used by cnreport-mcp.
- **Self-checks** — process-mcp's `selfcheck.py` content moves into `mcp/daas-mcp/selfcheck_process.py` (or merges into the existing daas selfcheck); the indicator round-trip and injection-guard cases are preserved.
