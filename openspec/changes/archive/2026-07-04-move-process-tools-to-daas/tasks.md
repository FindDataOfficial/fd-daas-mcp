## 1. Move process code into daas-mcp

- [x] 1.1 Copy `mcp/process-mcp/process_tools.py`, `indicator_tools.py`, and `process_database.py` into `mcp/daas-mcp/` (keep filenames). Verify imports (`from models import …`, `from process_database import …`, `from indicator_tools import …`) still resolve under daas-mcp's `sys.path` setup.
- [x] 1.2 Strip the `@app.tool` decorators from the moved tool functions (they will be registered daas-mcp-style via `app.tool(fn)`).
- [x] 1.3 Add the LLM-path deps to `mcp/daas-mcp/pyproject.toml`: `httpx>=0.27`, `jsonschema>=4.0`, `pypdf>=4.0`, `python-dotenv>=1.0` (pandas + sqlalchemy + fastmcp already present). Add `[tool.uv.sources] mcp-models = { path = "../models", editable = true }` if not already present.
- [x] 1.4 Add `mcp/models` to `sys.path` in `mcp/daas-mcp/server.py` if not already (it currently injects the harness root; verify the models path is also injected so `from models import …` works).
- [x] 1.5 Load `PROCESS_MODELS` / `LLM_*` env in `mcp/daas-mcp/server.py`'s dotenv block (root `.env` then per-MCP `.env` with `override=True`) — mirror process-mcp's two-stage dotenv.

## 2. Register the 19 tools on daas-mcp

- [x] 2.1 In `mcp/daas-mcp/server.py`, import the 11 LLM tool functions from `process_tools` and the 8 indicator tool functions from `indicator_tools` + `server.py`'s indicator wrappers.
- [x] 2.2 Register all 19 via `app.tool(fn)` in the existing registration block (daas-mcp's plain-function style). Confirm `app` name stays `daas-mcp`.
- [x] 2.3 Verify tool count: daas-mcp now exposes 56 tools (37 existing + 19 moved). Run `python server.py` and list tools to confirm no name collisions.

## 3. Add CLI branches

- [x] 3.1 Extend the `if __name__ == "__main__":` block in `mcp/daas-mcp/server.py` to recognize `--run-rule <name>` (calls the same `_run_rule_impl`/`run_rule` path the MCP tool uses, prints JSON summary, exits 0/1) and `--run-indicator <name>` (calls `get_db().run_indicator(name)`, prints JSON, exits 0/1) before `app.run(...)`.
- [x] 3.2 Update the comment at `server.py:140` from "Mirror process-mcp's --run-rule pattern." to note the branches are now native.
- [x] 3.3 Smoke both branches: `uv run --directory mcp/daas-mcp python server.py --run-rule nonexistent` and `--run-indicator nonexistent` print JSON errors and exit 1.

## 4. Move the selfcheck

- [x] 4.1 Copy `mcp/process-mcp/selfcheck.py` to `mcp/daas-mcp/selfcheck_process.py`. Keep its temp-DB, monkeypatched-LLM, indicator-round-trip scope intact.
- [x] 4.2 Fix any import paths inside the selfcheck to match its new location (relative imports of `process_database`/`process_tools`/`indicator_tools` now resolve from the daas-mcp dir).
- [x] 4.3 Run `uv run --directory mcp/daas-mcp python selfcheck_process.py` and confirm all sections pass (indicator path offline; live `extract_text` skipped without `LLM_API_KEY`).
- [x] 4.4 Run the existing daas selfchecks (`selfcheck_collection_writer.py`, `selfcheck_pipeline.py`) to confirm no regression from the new files/deps.

## 5. Cron task-row migration script

- [x] 5.1 Create `mcp/daas-mcp/migrate_process_cron.py` that opens `mcp/daas.db` via `DAAS_DATABASE_URL`, scans `tasks.command` for rows containing `mcp/process-mcp`, and rewrites the path to `mcp/daas-mcp` (preserving the `--run-rule`/`--run-indicator` flag and argument).
- [x] 5.2 Support `--dry-run` (list affected rows, write nothing), default real run (idempotent — re-running on already-migrated rows is a no-op), and `--revert` (restore `mcp/daas-mcp` → `mcp/process-mcp` for rollback).
- [x] 5.3 Run `--dry-run` against the live `daas.db`; record the count. Run for real. Confirm `SELECT count(*) FROM tasks WHERE command LIKE '%mcp/process-mcp%'` returns 0.

## 6. Repoint the dashboard

- [x] 6.1 In `dashboard/src/app/api/process/rules/route.ts`, `dashboard/src/app/api/process/rules/[name]/route.ts`, `dashboard/src/app/api/process/indicators/route.ts`, `dashboard/src/app/api/process/indicators/[name]/route.ts`: change every `callTool('process-mcp', …)` to `callTool('daas-mcp', …)` (10 calls total).
- [x] 6.2 In `dashboard/src/app/process/server-data.ts`: change `callTool('process-mcp', 'list_models')` and `callTool('process-mcp', 'list_indicator_ops')` to `'daas-mcp'`; update the comments.
- [x] 6.3 Update the two user-facing fallback strings in `dashboard/src/app/process/rules/rule-form.tsx` and `dashboard/src/app/process/indicators/indicator-form.tsx` from "process-mcp unavailable" to "daas-mcp unavailable".
- [x] 6.4 Update comments in `dashboard/src/lib/mcp-call.ts` and `dashboard/src/lib/mcp-client.ts` that reference process-mcp.
- [x] 6.5 Run `grep -rn "process-mcp" dashboard/src` and resolve every remaining hit (should be zero functional references; route paths `/process/*` stay unchanged).

## 7. Remove process-mcp

- [x] 7.1 Remove the `process-mcp` entry from `.mcp.json`.
- [x] 7.2 Delete the `mcp/process-mcp/` directory (server.py, process_tools.py, process_database.py, indicator_tools.py, selfcheck.py, pyproject.toml, uv.lock, `__pycache__`).
- [x] 7.3 Confirm `git status` shows the deletions and no stray references remain in `mcp/process-mcp/`.

## 8. Update docs

- [x] 8.1 `CLAUDE.md`: replace the `mcp/process-mcp/` section with a "Process tools (LLM extraction + indicators)" subsection under `mcp/daas-mcp/`; update the tool list, CLI branch syntax (`mcp/daas-mcp python server.py --run-rule`/`--run-indicator`), env vars (`PROCESS_MODELS` retained), and the "daas integration" note (LLM path writes `process_results`, not `observations`).
- [x] 8.2 `construction/daas-storage.md` §6: rewrite "How process-mcp indicators write to `observations`" → "How daas-mcp indicators write to `observations`"; update the §5 `metadata` attribution line.
- [x] 8.3 `construction/mcp.md`: update the MCP inventory (remove process-mcp from the list; note its tools moved to daas-mcp).
- [x] 8.4 `mcp/models/__init__.py` and `mcp/models/models.py`: update the `# process-mcp` domain comments to `# daas-mcp (process tools)`.
- [x] 8.5 `mcp/daas-mcp/server.py` and `mcp/daas-mcp/daas_database.py`: remove/update the "Mirror process-mcp" comments (the patterns are now native or self-referential).
- [x] 8.6 `mcp/leader-mcp/`: update "mirrors process-mcp's `PROCESS_MODELS`" / "matching process-mcp" comments in `README.md`, `server.py`, `specialist_agents.py` to reference daas-mcp.
- [x] 8.7 `specs/002-ponytail-cuts/plan.md`: update the two process-mcp line items to reference their new location under `mcp/daas-mcp/` (or note they are now moot if the files moved).

## 9. End-to-end verification

- [x] 9.1 Restart `daas-mcp` (or the dashboard's MCP client) and confirm it starts with 56 tools, no import errors.
- [x] 9.2 Dashboard smoke: load `/process/rules` and `/process/indicators`; create one rule and one indicator via the forms; confirm pickers (source_table, model, op) populate from daas-mcp.
- [x] 9.3 Run the created rule and indicator from the dashboard (Run button); confirm `process_results` and `observations` rows land; confirm `invalidateDb` refreshes the pages.
- [x] 9.4 Cron smoke: register a `cron-mcp` task with `command="uv run --directory mcp/daas-mcp python server.py --run-indicator <name>"` + a near-term schedule; confirm an `Execution` row is recorded and `observations` updates.
- [x] 9.5 `grep -rn "process-mcp" mcp/ dashboard/ construction/ CLAUDE.md .mcp.json` — confirm only intentional historical/archived references remain (e.g. `openspec/changes/archive/`).
