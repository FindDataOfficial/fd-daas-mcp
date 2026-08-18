# DAAS - Data As a Service

Layered data platform for financial, economic, and statistical data — a single SQLite file (`daas.db`) behind a consolidated MCP server, with data fetch delegated down to the `fd-open-data-mcp` upstream.

> **What is this?** A local data platform that turns Python data libraries (`akshare`, `yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`) into a queryable, indicator-computing, dashboard-ready store backed by one SQLite file. You drive it through **Claude Code skills** (thin shells that call workflow manifests) or through the **consolidated `fd-daas-mcp` MCP server** — both paths read/write the same database.

> **Upstream:** The `fd-open-data-mcp` data-fetcher is a sibling repo at `~/finddata/fd-open-data-mcp` (cloned automatically by `install.sh`).

> **Docs site:** The full, role-based documentation lives at `docs-site/` (MkDocs Material, EN+ZH bilingual). Read it locally with `uv run mkdocs serve` (browses at `/DAAS/`), or build strictly with `uv run mkdocs build --strict`. See [`docs-site/README.md`](docs-site/README.md) for build/serve/deploy.

---

## Architecture

Strict downward dependency — a layer never reaches up.

```
L3  user MCP compositions  (composite manifests, served in-proc on fd-daas-mcp)
L2  workflow manifests      (daas.db `workflows` table + engine, run via workflow_run)
L1  fd-daas-mcp            (consolidated infra: daas/cron/alerts/dashboard/composite/research/pdf/gateway/workflow)
L0  fd-open-data-mcp       (sole data-fetch upstream; concept-based semantic fetcher + entity master)
```

- **L0 — fd-open-data-mcp** (sibling repo): the sole data-fetch surface. A concept-based semantic fetcher with ranking/failover/caching; holds the entity master (`entities`, `entity_datasource_links`). Served HTTP at `:8300` (stdio fallback). Replaces the 11 former per-source data-fetch MCPs.
- **L1 — fd-daas-mcp** (this repo): the consolidated stdio server, sole entry in repo-root [`.mcp.json`](.mcp.json). Exposes **161 tools across 9 groups** (`daas · cron · alerts · dashboard · composite · research · pdf · gateway · workflow`) behind one server and one `fd-daas-mcp` Click CLI. The thin consolidation layer is `fd-daas-mcp/daas/fd_daas_mcp/` (`server.py`/`registry.py`/`cli.py`/`selfcheck.py`); each group's tool code lives in-package at `fd-daas-mcp/<group>-mcp/`.
- **L2 — workflow manifests**: manifests live in the `workflows` table in `daas.db` (registered via `workflow_register`, run via `workflow_run`). `build_workflow_from_goal` decomposes a natural-language goal into a manifest via an LLM.
- **L3 — user MCP composition**: a composite manifest (`{name, upstreams, tools, workflows, prompt}`) curates a named MCP surface served in-proc on the consolidated server. CRUD via `composite_*_manifest`.

The fetch skills (`fd-daas-based-data-fetch`, `fd-daas-fetch-data`, `fd-daas-research`) are thin shells: parameter-gathering → `workflow_run(name, params)` → checkpoint handling. They no longer call Python data libraries directly — fetch goes down through L1→L0.

For the full architecture, conventions, and the `daas.db` schema reference, see [`CLAUDE.md`](CLAUDE.md) and [`construction/mcp.md`](construction/mcp.md).

---

## Install & Quick Start

Requirements: Python 3.10+ and [uv](https://docs.astral.sh/uv/). `dartlab` fetches need 3.12 — run them with `uv run --python 3.12 --with dartlab ...`.

One-click install (clones DAAS + upstreams, provisions venvs, inits `daas.db`, localizes `.mcp.json`):

```bash
curl -fsSL https://raw.githubusercontent.com/FindDataTechnology/fd-daas-mcp/master/install.sh | sh
```

Env overrides: `DAAS_DEST` (default `~/code/DAAS`), `DAAS_BRANCH`, `FINDDATA_HOME` (default `~/finddata`). Manual steps below.

```bash
# 1. Provision the root venv (data libs are declared deps)
uv sync

# 2. Provision the database - creates daas.db (full schema + dep-free starter
#    catalog of sources). DAAS_DATABASE_URL is OPTIONAL: unset, it defaults to
#    ./daas.db (writable cwd) or ~/.fd-daas-mcp/daas.db. Set it only to relocate.
fd-daas-mcp/.venv/bin/fd-daas-mcp init       # one-shot provision + seed
fd-daas-mcp/.venv/bin/fd-daas-mcp doctor      # read-only health check (path, schema, row counts)

# 3. Configure credentials - create a repo-root .env for the source keys you need
#    (listed in Environment Variables below). Scripts auto-load .env; no manual export.

# 4. Compute an existing indicator (upserts into observations)
uv run python .claude/skills/fd-daas-based-data-fetch/scripts/run_indicator.py SPY_ma5

# 5. Query daas.db directly (db lives at the resolved DAAS_DATABASE_URL, default ./daas.db)
sqlite3 daas.db "SELECT name, datasource, op FROM indicator_rules LIMIT 10"
sqlite3 daas.db "SELECT source, COUNT(*) FROM observations GROUP BY source"

# 6. Launch / health-check the consolidated server
fd-daas-mcp/bin/fd-daas-mcp-server                       # stdio server (what .mcp.json launches)
fd-daas-mcp/.venv/bin/python -m daas.fd_daas_mcp.selfcheck   # registry + tool health check (target: failed=0)

# 7. Run a workflow manifest (L2 — the fetch path goes L1→L0)
fd-daas-mcp/.venv/bin/python -c "
from daas_mcp_workflow_tools import workflow_run   # or via the MCP tool
print(workflow_run('fetch-and-persist', params_json='{\"entity\":\"SPY\",\"indicator\":\"ma5\"}'))
"
```

The Quick Start commands above have been verified against this repo: `SPY_ma5` is a real `indicator_rules` row, and the `fd-daas-mcp` registry reports **161 tools across 9 sources** (`failed=0, skipped_optional=1` for the optional `pdf` group).

---

## Project Structure

```
daas/
├── .claude/skills/          # Claude Code skills (fd-daas-based-data-fetch is the core fetch shell)
├── fd-daas-mcp/             # Consolidated MCP server — sole .mcp.json entry (161 tools, 9 groups)
│   ├── alerts-mcp/          #   alert rule engine + 7 notification channels
│   ├── composite-mcp/       #   user MCP composition (curate tools + embed workflows + prompt)
│   ├── cron-mcp/            #   task + schedule registry (DB-backed)
│   ├── daas-mcp/            #   datasource/function/indicator/entity catalog + compute + rules
│   ├── dashboard-mcp/       #   standalone-HTML dashboard registry + query
│   ├── gateway-mcp/         #   L0 upstream registry + call routing (former leader gateway half)
│   ├── workflow-mcp/        #   manifest-based multi-step data workflows (former leader workflow half)
│   ├── pdf-mcp/             #   local PDF/text semantic search (sqlite-vec) [optional]
│   ├── research-mcp/        #   persisted research bundle (collections + indicators + dashboard + report)
│   ├── bin/fd-daas-mcp-server      # launcher
│   └── daas/fd_daas_mcp/   # server.py / registry.py / cli.py / selfcheck.py
├── daas.db                  # Shared SQLite database (ships as a demo dataset: registry + observations + scraw_*)
├── dashboards/              # Standalone HTML dashboards (+ index.html, daas.md)
├── construction/            # Architecture docs (mcp.md — layered L0/L1/L2/L3)
└── .env                     # DAAS_DATABASE_URL, proxy, source auth keys, LLM config, ...
```

---

## `daas.db` Data Model

One SQLite file at the path in `DAAS_DATABASE_URL` (relative `sqlite:///` paths resolve against repo root; `PRAGMA foreign_keys=ON` for FK cascade, `PRAGMA journal_mode=WAL` + `busy_timeout=10000` to dodge "database is locked"). Tables group by role:

| Role | Tables | What they hold |
|---|---|---|
| **Registry / catalog** | `sources`, `daas_functions`, `daas_function_columns`, `entities`, `entity_datasource_links`, `indicator_rules` | Datasource/function/column catalog; stocks/countries + their source identifiers; indicator bindings (table + columns + op + params) |
| **Computed series** | `observations` | Indicator output — one `(source, function_name, indicator, date)` point per row; upserted by `run_indicator.py`. Dashboards & alerts read this. |
| **Fetched source data** | `scraw_<slug>` | Raw rows pulled by a fetch (auto-created by `upsert.py`). `observations` are computed *from* these. |
| **Collections + rules** | `entity_collections*`, `indicator_collections*`, `rules`, `process_results` | Named groups of entities/indicators + add-in/remove-out audit log; the unified `rules` store (json/script/position/llm) drives membership + LLM extraction |
| **MCP operational** | `dashboards`, `alert_rules`, `alert_events`, `schedules`, `tasks`, `gateway_upstreams`, `workflows`, `workflow_runs`, `workflow_run_steps`, `composites`, `researches` | Dashboard registry, alert engine, cron state, gateway/workflow/composite/research state |

Query it directly from the repo root: `sqlite3 daas.db "SELECT …"`.

---

## Skills (`.claude/skills/`)

Skills are plain Markdown (`SKILL.md`) + Python scripts. The fetch skills are thin shells that gather parameters and call `workflow_run` — they no longer call Python data libraries directly (fetch goes L1→L0).

| Skill | Purpose |
|---|---|
| **`fd-daas-based-data-fetch`** *(core fetch shell)* | Resolve an entity + indicator against `daas.db`, then `workflow_run(name, params)` to fetch via fd-open-data-mcp and persist to `scraw_*` / `observations`. |
| `fd-daas-fetch-data` | Entity → coverage → indicator workflow (sqlite3 + the core scripts). |
| `fd-daas-research` | Orchestrate analyze → [collection] → indicators → dashboard → persist as a `research` bundle + markdown report. |
| `fd-daas-brainstorm` | Clarify a research goal via dialogue → `daas-doc/research/<plan>.md` (no `daas.db` state). |
| `fd-daas-indicators-creator` | Persist a fetched series to a `scraw_<slug>` table (manual refresh — no cron). |
| `fd-daas-dashboard-creator` | Build a standalone ECharts HTML dashboard + register it. |
| `fd-daas-dashboard` | Find / open / inspect existing dashboards (read-only). |
| `fd-daas-entities-collection-creator` / `fd-daas-entities-collection` | Define a rule-based entity collection / day-to-day collection operations. |
| `fd-daas-indicators-collection-creator` | Curate an indicator collection + export CSV/markdown with resolved scores. |
| `fd-daas-rules-creator` | Author a unified rule (json/script/position/llm), attach to a collection, dry-run, sync. |
| `fd-daas-pdf` | Ingest a PDF/text into a local vector store (sqlite-vec) and search semantically. Requires the `[pdf]` extra. |
| `fd-daas-scrapling-official` | Scrape anti-bot-protected pages (Cloudflare/JS render) via Scrapling. |
| `fd-daas-skill-creator` / `fd-daas-skill-review` | Create/optimize and review/test daas skills. |
| `fd-coding-mcp-creator` | Scaffold a user MCP composition (L3): interview → manifest → register → selfcheck. |
| `fd-coding-skill-creator`, `fd-coding-daas-*`, `openspec-*` | Infra: create/optimize skills, reset/scraw/datasource builders, OpenSpec change lifecycle. |

---

## MCP Tool Groups (`fd-daas-mcp`)

The consolidated server exposes **161 tools across 9 groups** (`failed=0, skipped_optional=1` for the optional `pdf` group). Catalog is group-level (per-tool detail via the server's own introspection / `selfcheck`).

| Group | Prefix | Tools | Purpose |
|---|---|---|---|
| **daas** | `daas_*` | 87 | Datasource/function/column/entity/indicator catalog, indicator compute, LLM extraction, collections, entity coverage, unified rules. |
| **dashboard** | `dashboard_*` | 11 | Standalone-HTML dashboard registry (CRUD), table query, stats, index regeneration. |
| **alerts** | `alerts_*` | 10 | Alert rule engine over observation series + 7 notification channels (Telegram/Discord/Slack/Twitter/DingTalk/Feishu/WeCom). |
| **cron** | `cron_*` | 13 | DB-backed task + schedule registry; ad-hoc `run_now`; execution history. |
| **composite** | `composite_*` | 16 | User MCP composition (L3): curate tools from upstreams + embed workflows + prompt. |
| **research** | `research_*` | 9 | Persisted research bundle tying collections/indicators/dashboard/pipeline + markdown report. |
| **gateway** | `gateway_*` | 7 | L0 upstream registry CRUD + call routing to `fd-open-data-mcp` (former `leader` gateway half). |
| **workflow** | `workflow_*` | 8 | Manifest-based multi-step data fetches: register/run/resume/inspect (former `leader` workflow half). |
| **pdf** | `pdf_*` | — | Local PDF/text semantic search (sqlite-vec + sentence-transformers). Optional — gated on the `sqlite_vec` import. |

> The legacy `leader` group is dissolved: its gateway-routing half became `gateway_*`, its workflow-manifest half became `workflow_*`. Harness-registry / snapshot / provenance capabilities are deleted.

Launch: `fd-daas-mcp/bin/fd-daas-mcp-server` (stdio). Both the server and the `fd-daas-mcp` CLI consume `registry.build()`, so the two surfaces cannot drift.

---

## Environment Variables

A single repo-root `.env` holds all config; scripts and the MCP server auto-load it. (Keys marked optional are only needed for the features they enable.)

| Key | Purpose | Required? |
|---|---|---|
| `DAAS_DATABASE_URL` | `sqlite:///` URL to `daas.db` (relative resolved against repo root, or absolute). Optional: unset, defaults to `./daas.db` (writable cwd) or `~/.fd-daas-mcp/daas.db`. Run `fd-daas-mcp init` to provision. | optional |
| `HTTP_PROXY` | Outbound proxy for data libraries. | optional |
| `EDGAR_IDENTITY` | SEC EDGAR identity string (`"Name email@domain"`). | for edgar |
| `EDINET_API_KEY` | Japan EDINET document fetch key. | for edinet |
| `CKAN_PORTAL_URL` | CKAN portal base URL. | for ckan |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Shared LLM endpoint for extraction / workflow planner. | for LLM features |
| `LEADER_MODELS`, `LEADER_MODEL_HIGH/BALANCE/FAST` | Per-tier model overrides for the workflow planner (`build_workflow_from_goal`). Names retained; only descriptive label is "workflow planner". | optional |
| `ALERTS_FEISHU_WEBHOOK_URL` | Feishu webhook for the alerts channel. | for feishu alerts |
| `DASHBOARD_PORT` | Port for the dashboard app. | optional |

---

## For AI Agents

If you are an AI agent (e.g. Claude Code) operating in this repo:

- **Fetch data through the workflow path.** Use `fd-daas-based-data-fetch`: resolve the entity + indicator against `daas.db` via `sqlite3`, then `workflow_run(name, params)` — the manifest routes the fetch down through `gateway_call` → `fd-open-data-mcp` (L0) and persists into `scraw_<slug>` / `observations`. For multi-step fetches, `build_workflow_from_goal` emits a manifest.
- **Workflow:** resolve → fetch (via L0) → persist. Resolve entity+indicator in `daas.db`; fetch via the gateway; persist into `scraw_<slug>` (raw) or `observations` (computed indicator).
- **Use the MCP server for everything else** — catalog browsing, creating indicators/collections/rules, cron scheduling, alerts, building/finding dashboards, PDF semantic search, composite authoring, research bundles. These are the `fd-daas-mcp` tools (161 across 9 groups).
- **Query `daas.db` with `sqlite3` from the repo root** (`sqlite3 daas.db "…"`). Use `PRAGMA foreign_keys=ON` for FK cascade.
- **Authoritative architecture + schema reference:** [`CLAUDE.md`](CLAUDE.md) (it has a `## daas.db` section listing every table) and [`construction/mcp.md`](construction/mcp.md) (the layered L0/L1/L2/L3 reference).

---

## License

Apache 2.0.
