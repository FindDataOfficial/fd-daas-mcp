# MCP Construction

> Layered architecture (rearchitect-daas-layered-mcps). The consolidated
> `fd-daas-mcp` server is the sole `.mcp.json` entry; data fetch is delegated
> down to the `fd-open-data-mcp` upstream. See `CLAUDE.md` for the skill-driven
> fetch workflow + `daas.db` schema.

## Layered architecture

Strict downward dependency. A layer never reaches up.

```
L3  user MCP compositions  (composite manifests, served in-proc on fd-daas-mcp)
L2  workflow manifests      (daas.db `workflows` table + engine, run via workflow_run)
L1  fd-daas-mcp             (consolidated infra: daas/cron/alerts/dashboard/composite/research/pdf/gateway/workflow)
L0  fd-open-data-mcp        (sole data-fetch upstream; concept-based semantic fetcher + entity master)
```

### L0 — fd-open-data-mcp (data fetch)

Sole data-fetch surface. A Python dependency sourced from the sibling
`~/finddata/fd-open-data-mcp` repo, launched from the DAAS venv as
`python -m fd_open_data_mcp.server`. Served HTTP at `:8300` (stdio fallback).
Holds the entity master (`entities`, `entity_datasource_links`) + a
concept-based semantic fetcher with ranking/failover/caching. Replaces the 11
former per-source data-fetch MCPs. Callers use
`call_data_mcp('fd-open-data-mcp', 'read', …)` directly, or
`build_workflow_from_goal` for multi-step fetches.

### L1 — fd-daas-mcp (infra)

Consolidated stdio server; one entry in repo-root `.mcp.json`; one
`fd-daas-mcp` Click CLI. The thin consolidation layer is
`fd-daas-mcp/daas/fd_daas_mcp/` (`server.py`/`registry.py`/`cli.py`/`selfcheck.py`);
each group's tool code lives in-package at `fd-daas-mcp/<group>-mcp/`. Server
and CLI both consume `registry.build()` so the surfaces cannot drift.

| Group | Dir | Concern |
|-------|-----|---------|
| gateway | `gateway-mcp/` | L0 upstream registry + call routing (former `leader` gateway half) |
| workflow | `workflow-mcp/` | manifest store + run engine (former `leader` workflow half) |
| daas | `daas-mcp/` | source/function/column catalog, entities, indicators, observations, rules, collections |
| cron | `cron-mcp/` | APScheduler schedules + task registry |
| alerts | `alerts-mcp/` | trigger rules over observation/scraw series + channel dispatch |
| dashboard | `dashboard-mcp/` | standalone-HTML dashboard registry + `dashboards/index.html` regen |
| composite | `composite-mcp/` | user MCP composition: curate tools from upstreams + embed workflows + prompt |
| research | `research-mcp/` | persisted research bundle tying collections/indicators/dashboard/pipeline + report |
| pdf | `pdf-mcp/` | optional local PDF/text vector search (sqlite-vec); gated on the extra |

Launch: `fd-daas-mcp/bin/fd-daas-mcp-server`. Selfcheck:
`fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck` (probes every
registered tool + source; target failed=0).

> The legacy `leader` group is dissolved: its gateway-routing half became
> `gateway_*`, its workflow-manifest half became `workflow_*`. Harness-registry
> / snapshot / provenance capabilities are deleted. `ask_data_crew` + the
> specialist-agent layer are removed.

### L2 — workflow manifests

Manifests live in the `workflows` table in `daas.db` (registered via
`workflow_register`, run via `workflow_run`). A manifest is an ordered list of
`fd-open-data-mcp` gateway calls (`{id, server, tool, args, on_failure}`); the
engine executes them sequentially, honoring `on_fail`, and persists per-step
results + run state. `build_workflow_from_goal` decomposes a natural-language
goal into a manifest via an LLM (falls back to a deterministic single-step
`list_concepts` manifest). Skills (`fd-daas-based-data-fetch`,
`fd-daas-fetch-data`, `fd-daas-research`) are thin shells:
parameter-gathering → `workflow_run(name, params)` → checkpoint handling.

### L3 — user MCP composition

A composite manifest (`{name, upstreams, tools, workflows, prompt}`) curates a
named MCP surface served in-proc on the consolidated `fd-daas-mcp` server.
`workflows` embeds NAMES of registered L2 workflow manifests (each served as
one lazy tool); `prompt` becomes the composite's system prompt. CRUD via
`composite_create_manifest`/`_update`/`_delete`/`_list_manifests`. The
scaffold skill `fd-coding-mcp-creator` interviews the user → writes a manifest
→ registers → selfchecks. See `openspec/changes/rearchitect-daas-layered-mcps/`.

## Test suite

Offline pytest suite at `fd-daas-mcp/tests/` — registry invariants,
`<group>_<tool>` namespacing, cross-group collisions, leaf-module isolation,
cron APScheduler suppression, per-core-group tool invocation, CLI
generation/invocation, selfcheck, composite manifest CRUD + serving, and the
optional `pdf` group. Run from the repo root:

```bash
fd-daas-mcp/.venv/bin/python -m pytest fd-daas-mcp/tests
```

## Env & schema

**Single source of truth:** `fd-daas-mcp/models/models.py` — one SQLAlchemy
`Base`, all tables across the MCP domains.

**Single database:** `daas.db` — every group reads/writes here (path in
`DAAS_DATABASE_URL`; relative `sqlite:///` paths resolve against repo root;
`PRAGMA foreign_keys=ON` for FK cascade, `PRAGMA journal_mode=WAL` +
`busy_timeout=10000` on every singleton engine to dodge "database is locked").

**Single env file:** repo-root `.env` — `DAAS_DATABASE_URL`, `HTTP_PROXY`,
`EDGAR_IDENTITY`, `EDINET_API_KEY`, `LLM_*`/`LEADER_MODEL*` (workflow planner),
`ALERTS_FEISHU_WEBHOOK_URL`, `DASHBOARD_PORT`, `CKAN_PORTAL_URL`. Scripts load
`.env` automatically; `fd-daas-mcp/.env` is empty (leader scripts must load
the repo-root `.env` first to hit the live `daas.db`).

Schema table domains (see `CLAUDE.md` for the full table list):

| Domain | Tables |
|--------|--------|
| gateway | `gateway_upstreams` |
| workflow | `workflows`, `workflow_runs`, `workflow_run_steps` |
| daas | `sources`, `daas_functions`, `daas_function_columns`, `entities`, `entity_datasource_links`, `indicator_rules`, `observations`, `rules`, `process_results`, `entity_collections*`, `indicator_collections*`, `researches` |
| cron | `schedules`, `executions`, `tasks` |
| alerts | `alert_rules`, `alert_events` |
| dashboard | `dashboards` |
| composite | `composites`, `upstreams`, `composite_tools`, `composite_chains` |
| pdf | `pdf_documents`, `pdf_meta`, `pdf_chunks` (+ `pdf_chunks_vec` `vec0`) |

Schema changes go in `fd-daas-mcp/models/models.py` first, then propagate to
consumers.

## Unified Rules Engine

> Replaces the former `process_rules` table. See
> `openspec/changes/unify-rule-tools/`.

**`rules` table** (`name` UNIQUE, `rule_type` ∈ {json, script, position, llm},
`target` ∈ {entity_ids, indicator_names, rows}, `config_json`, `enabled`).
Entity + indicator collections reference a rule via a nullable `rule_id` FK
(ON DELETE SET NULL); `process_results.rule_id` FK->`rules.id` (ON DELETE
CASCADE).

**`RuleEngine`** (`fd-daas-mcp/daas-mcp/rule_engine.py`) `evaluate(rule,
session, db_url, limit)` dispatches on `rule_type`: `json` declarative entities
filter; `script` path-based importlib `members(ctx)` (ctx: read-only `query`,
`http_get`, `llm`); `position` CSS/xpath/regex/json-path extraction; `llm`
natural-language extraction via shared `process_tools.extract_text`.

Tools (`daas_*`): `daas_create_rule`/`list_rules`/`get_rule`/`update_rule`/
`delete_rule`/`test_rule` (dry-run)/`run_rule` (persist). Collection sync:
`daas_sync_entity_collection` / `daas_sync_indicator_collection` evaluate the
attached rule and diff. Skill: `fd-daas-rules-creator`.
