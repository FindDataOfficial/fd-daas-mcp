# fd-daas-mcp test suite

The consolidated `fd-daas-mcp` server (8 tool groups, 157 tools) is covered by
an **offline-runnable** pytest suite under `fd-daas-mcp/tests/`. This doc is the
human-readable index: how to run it, what it covers, the offline constraint, and
how optional extras are stubbed. It is the `daas-doc/` artifact required by the
`fd-daas-mcp-test-suite` spec (change `daas-skills-and-mcp-overhaul`).

## How to run

From the repo root, using the project venv:

```bash
fd-daas-mcp/.venv/bin/python -m pytest fd-daas-mcp/tests
```

- pytest config is anchored in `fd-daas-mcp/pyproject.toml`
  (`[tool.pytest.ini_options]`: `testpaths=["tests"]`, `pythonpath=["."]`,
  `addopts="-p no:logfire -p no:pytest_logfire"`). pytest discovers this config
  when invoked on `fd-daas-mcp/tests` from the repo root.
- `conftest.py` points `DAAS_DATABASE_URL` at a throwaway temp SQLite file so
  no test (and no import-time `init_db()`) ever touches the real `daas.db`, and
  resets the registry build cache before/after every test.
- Expected result: **green, ~5-6s, no network** (see Offline constraint below).

Manual invariant entry point (same logic as the pytest selfcheck test):

```bash
fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck
```

## What is covered (test file -> requirement)

| Test file | Asserts |
| --- | --- |
| `test_registry.py` | `registry.build()` returns `>= 155` tools; all six core groups present; known cross-group collisions present as bare names in 2+ groups; `<group>_<tool>` namespacing; `leaf_isolation_check()` resolves distinct files; **no APScheduler thread** after build (cron suppression). |
| `test_registration_report.py` | Report has `registered`/`failed`/`skipped_optional`; every core group registers `>= 1` tool; `failed` contains no core-group tool; registered count == `len(build())`; an absent optional group is `skipped_optional` not `failed`; `note_failed` surfaces `app.tool` failures. |
| `test_core_group_tools.py` | **Every core group has at least one tool invoked through its registered handler** (not only counted in the report): alerts `list_channels`, cron `list_db_tasks`, composite `list_composites`, daas `list_sources`, dashboard `list_databases`, gateway `list_data_mcps` - each returns a JSON-serializable structured result. |
| `test_cli.py` | The CLI generates a subcommand per registered tool; groups match the registry; malformed/missing args exit 2; `--json` prints structured output; non-JSON prints str; async tools are awaited (`click.testing.CliRunner`, no live MCP transport). |
| `test_selfcheck.py` | The selfcheck invariants run green as a pytest assertion (`run_invariants()` returns OK, has six checks, tool-count meets baseline) - the **same** `run_invariants()` the manual `python -m ...selfcheck` entry calls, so the two cannot drift. |
| `test_pdf_optional.py` | `pdf` is an optional group gated on `sqlite_vec`; it is `skipped_optional` when the dep is absent and registered when present; the six-core-groups + `len(tools) >= 155` assertions hold regardless. |
| `test_rule_engine.py` / `test_rule_tools.py` | The unified rule engine (`json`/`script`/`position`/`llm`) and the `daas_*` rule tools (CRUD, dry-run, `target='rows'` LLM extraction cursor, validation). |
| `test_entity_collection_sync.py` / `test_indicator_collection_sync.py` | Rule-based collection sync (`daas_sync_entity_collection` / `daas_sync_indicator_collection`): add/remove membership, idempotence, manual-collection no-op, rule-id precedence, CLI subcommands. |
| `test_run_indicator_eviction.py` | `daas_run_indicator` still works after the registry's source-module eviction (the handler stays callable). |
| `test_research_tools.py` | `research_*` tools: CRUD round-trip, `create_missing`, component validation, `generate_report` (file + column + regenerate), `delete` cascade (owned pipeline + cron removed; shared collections/rules preserved), `refresh` orchestration, `add/remove_component`. |
| `test_alert_tools.py` | `alerts_*` tools: alert-rule CRUD round-trip; `run_rule` fires + writes an `alert_events` row (notification dispatch stubbed to a capturer); cooldown (no refire within the window) + no-fire (condition false writes no event). |
| `test_cron_tools.py` | `cron_*` tools: schedule CRUD, pause/resume `enabled` toggle, `run_now` writes an execution row + `list_executions` filtering, DB-task create/list/delete. APScheduler's import-time `load_schedules()` + per-job functions are stubbed (no `BackgroundScheduler` thread); `run_now` runs a stub registry task (no subprocess). |
| `test_composite_tools.py` | `composite_*` tools: composite create/list, upstream + tool add/remove, served-name derivation (`<key>_<tool>`), chained-tool add/remove with `_validate_steps` rejecting malformed/control-flow steps. No live upstream subprocess. |
| `test_dashboard_tools.py` | `dashboard_*` tools: register/get/list/search/update/delete (upsert by slug), `index.html` + `daas.md` regeneration on register/delete (redirected to a tmp dir), `query_table` rows + `limit`/`offset` pagination. |
| `test_workflow_engine.py` | workflow manifest validation + engine execution: register/get/list/update/delete, run/resume/inspect, `$params`/`$steps`/`$env` interpolation, `on_failure` abort/continue/checkpoint. No live gateway subprocess. |

## Offline constraint

The suite runs to green **with no network access** and **without resolving
optional extras from PyPI**:

- It exercises the always-on core surface (`alerts`/`cron`/`composite`/`daas`/
  `dashboard`/`gateway`/`research`/`workflow`) against a throwaway temp SQLite DB.
- Optional extras (the `[pdf]` extra = `sentence-transformers` +
  `sqlite-vec` + `pdfplumber`, `scrapling`, `firecrawl`, `mcp_massive`) are
  **never installed by the suite**. The `pdf` group is gated on `sqlite_vec`; if
  the extra is absent the group is recorded as `skipped_optional` (INFO, not a
  failure) and the six-core-groups + tool-count assertions still hold.
- No test makes a network call. The per-core-group listing tools invoked by
  `test_core_group_tools.py` are env/filesystem/DB reads only.

## How optional extras are stubbed

- `pdf` is loaded by `registry.build()` only when `sqlite_vec` imports
  (`registry._can_import`). When absent it is skipped; `test_pdf_optional.py`
  also injects a fake optional source (`fake_optional_source` fixture) to assert
  the `skipped_optional` path deterministically, and monkeypatches the dep check
  to assert the `registered` path.
- `pdf`-specific behavior (ingest/dedup/search/CRUD) is exercised with
  `sentence_transformers` and `sqlite-vec` stubbed (no model download, no
  extension load, no network) per the spec - covered when the `[pdf]` extra is
  installed; the core suite does not require it.

## Per-group behavioral coverage & stubbing (alerts/cron/composite/dashboard/gateway)

Beyond the "≥1 tool invoked per core group" bar in `test_core_group_tools.py`,
the five groups that previously lacked dedicated behavioral tests now have one
test module each that calls the group's tool handlers directly against the
throwaway DB and asserts return shape + DB side-effects (mirroring
`test_rule_tools.py` / `test_research_tools.py`). Each group's one live
side-effect is stubbed/suppressed so the suite stays offline:

- **alerts** — notification dispatch (`notifiers.registry.send`, imported into
  `engine` as `_channel_send`) is monkeypatched to a capturing no-op; the series
  a rule evaluates is seeded into the throwaway `observations` table.
- **cron** — APScheduler's import-time `load_schedules()` (which would start a
  `BackgroundScheduler` thread) and `shutdown_scheduler` are patched to no-ops
  **before** `server` is imported, mirroring the consolidation registry's
  `suppress=True` path; the per-job functions (`add/remove/pause/resume
  _schedule_job`) are monkeypatched on the `server` namespace. `run_now` is left
  real so `execute_task` writes a genuine `executions` row, but the task it runs
  is a stub registered in the in-process registry (no subprocess).
- **composite** — only the config-curating management tools are exercised; the
  live upstream subprocess/transport (`build_client`/`build_transport`) and
  proxy/chain execution are never invoked.
- **dashboard** — `index.html`/`daas.md` regeneration writes to a per-test
  `tmp_path` (the module-level `_DASH_DIR` is monkeypatched) so regeneration is
  exercised for real without writing to the repo.
- **gateway** — the live upstream HTTP/subprocess client (`gateway_database.build_client`) is never invoked; only the SQLite-backed upstream-registry CRUD is exercised. `dashboard`'s `server.py` is loaded under a unique module name (importlib) because cron's test already occupies `sys.modules["server"]`.

Each module cleans up the rows it creates (prefixed `zz_test_`) so the shared
throwaway DB stays clean across the session.

## Refactor notes

No server/registry code refactor was required to reach green - the pre-existing
suite already covered registry/namespacing/collisions/leaf-isolation/scheduler-
suppression/CLI/selfcheck/pdf, the per-core-group handler-invocation gap was
closed additively by `test_core_group_tools.py`, and the per-group behavioral
gap (alerts/cron/composite/dashboard/gateway) was closed additively by the five
`test_<group>_tools.py` modules added in change `add-daas-mcp-group-tests`. The
`fd-daas-mcp/daas/fd_daas_mcp/` consolidation layer and the `<group>-mcp/`
production modules are unchanged by this change; if a new test surfaces a
handler defect, the defect is recorded as a separate finding (the test is not
accompanied by an inline fix, so this stays a pure-coverage change).
