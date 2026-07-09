# Plan: Rename combine-mcp → composite-mcp

## Why
"combine" is generic and disconnected from the code's own vocabulary, which calls these things *composites* everywhere (`create_composite`, `COMPOSITE` env, `Composite` table, `composite_tools` / `composite_chains` tables). Renaming to `composite-mcp` aligns the MCP name with its internals.

## What does NOT need migrating
- **DB tables** are already generically named (`composites`, `upstreams`, `composite_tools`, `composite_chains`) — no schema or data migration.
- **The `example` composite row** in `daas.db` references its akshare upstream by absolute path, not by MCP name; `COMPOSITE=example` env still resolves. Survives the rename untouched.

## Scope

### A. Code (required for it to keep working)
1. Rename directory `mcp/combine-mcp/` → `mcp/composite-mcp/`
2. Rename files: `combine_database.py` → `composite_database.py`, `combine_tools.py` → `composite_tools.py`
3. Update imports in `server.py`, `composite_tools.py`, `selfcheck.py`, `seed_example.py`
4. `pyproject.toml`: `name = "composite-mcp"`, update `[tool.setuptools] py-modules` list
5. `server.py`: logger name `logging.getLogger("composite-mcp")`, `FastMCP(name="composite-mcp")`, docstrings
6. Rename Python identifiers in `composite_database.py` + all callers:
   - `CombineDatabase` → `CompositeDatabase`
   - `_combine_db` → `_composite_db`
   - `get_combine_db` → `get_composite_db`
   - `reset_combine_db` → `reset_composite_db`
   - Callers: `server.py`, `composite_tools.py`, `seed_example.py`, `selfcheck.py`
7. `.mcp.json`: key `combine-mcp` → `composite-mcp`; `--directory .../mcp/combine-mcp` → `.../mcp/composite-mcp`

### B. Permission allowlists (so the renamed server stays approved)
8. `.claude/settings.local.json`: `mcp__combine-mcp` → `mcp__composite-mcp`; `combine-mcp` → `composite-mcp` in `enabledMcpjsonServers`
9. `dashboard/.claude/settings.local.json`: same `enabledMcpjsonServers` rename

### C. Live docs & live spec
10. `CLAUDE.md` (3 refs): line 42 mention, line 167 section header `### mcp/composite-mcp/ — Composite MCP`, line 177 run-from-within path
11. `construction/mcp.md` (4 refs): table rows, section header, body
12. `construction/daas-storage.md` (1 ref)
13. `openspec/specs/combine-mcp-server/` → `openspec/specs/composite-mcp-server/`: rename dir + update the `mcp/combine-mcp/server.py` path inside `spec.md`

### D. In-flight branch plan
14. `specs/002-ponytail-cuts/plan.md` (4 refs: items 3, 26, 65, 75): update `combine-mcp` → `composite-mcp`, `seed_example.py`/`selfcheck.py` paths. (These items are about code-quality fixes — hardcoded paths, speculative guards, inlining `build_client()` — not the rename. I update only the name references, not conflate the two pieces of work.)

### E. Cross-MCP comment mirrors (consistency only)
15. `mcp/cnreport-mcp/cnreport_database.py:5` — "Mirrors combine_database.py" → "Mirrors composite_database.py"
16. `mcp/leader-mcp/gateway_database.py:3` — same
17. `mcp/models/models.py:140, 728` — 2 comments
18. `mcp/models/__init__.py:38` — 1 comment
19. `mcp/scrapling-uv-mcp/scripts/register.py:13` — comment
20. `mcp/scrapling-docker-mcp/scripts/register.py:13` — comment

### F. Leave alone — historical archives (immutable)
- `openspec/changes/archive/**` — all archived change records, including `archive/2026-06-28-add-combine-mcp/`. These describe what was true at the time; rewriting them rewrites history. (Many of them mention combine-mcp as the provenance of the `fastmcp.Client` cross-MCP-call pattern — that historical reference stays.)

## Verification
1. `cd mcp/composite-mcp && uv run python selfcheck.py` — confirms imports, proxy forwarding, chain `$prev`/`$step[N]` resolution, fail-fast, and resolver unit checks pass against a temp DB.
2. `uv run --directory mcp/composite-mcp python seed_example.py` — confirms the seeder still runs (idempotent on the existing `example` composite).
3. `grep -rn "combine" mcp/composite-mcp/` — expect zero hits in code/identifiers (prose mentions of "combine" in comments are fine if any remain, but there shouldn't be).
4. Tool surface change: after an MCP-client restart, tools become `mcp__composite-mcp__*` (cannot verify from within this session without a restart; selfcheck proves the server boots and serves).

## Out of scope
- Fixing the hardcoded `/Users/chengsishi/...` paths in `seed_example.py` — that's ponytail-cuts item 3, separate from this rename. Preserved as-is.
- The `CombineDatabase` → `CompositeDatabase` class rename is in scope (item 6) for consistency.
