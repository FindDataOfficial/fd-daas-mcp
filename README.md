# cli-anything

Skill-driven data fetch for financial, economic, and statistical data — built on [CLI-Anything](https://github.com/HKUDS/CLI-Anything).

> **What is this?** A local data platform that turns Python data libraries (`akshare`, `yfinance`, `edgar`, `edinet-tools`, `dartlab`, `world_bank_data`, `ckanapi`) into a queryable, indicator-computing, dashboard-ready store backed by a single SQLite file (`daas.db`). You can drive it through **Claude Code skills** or through a **consolidated MCP server** — both paths read/write the same database.

> **Upstream:** The `CLI-Anything/` directory is the upstream project (do not modify). Everything else in this repo is the data-fetch layer built on top of it.

> **Docs site:** The full, role-based documentation lives at `docs-site/` (MkDocs Material). Read it locally with `uv run mkdocs serve` (browses at `/DAAS/`), or build strictly with `uv run mkdocs build --strict`. See [`docs-site/README.md`](docs-site/README.md) for build/serve/deploy.

---

## Architecture

Two access paths share one SQLite database:

```
                         ┌──────────────────────────────────────────┐
   Skill path            │           daas.db (SQLite)               │
   (Claude Code skills)  │   registry · entities · indicator_rules  │
      │                  │   observations  ·  scraw_*               │
      │                  └──────────────────────────────────────────┘
      ▼                              ▲
 .claude/skills/                     │
 skill-based-data-fetch ── Python ───┘
   libs (akshare/yfinance/…)         │
      + sqlite3                      │
                                     │ MCP path
                                     │ (fd-daas-mcp server, 176 tools / 7 groups)
 .mcp.json ── fd-daas-mcp ───────────┘
              (sole entry)            alerts · composite · cron · daas
                                      dashboard · leader · pdf
```

- **Skill path** — skills call Python data libraries **directly** and read/write `daas.db` via `sqlite3`. The core fetch skill is [`skill-based-data-fetch`](.claude/skills/skill-based-data-fetch/SKILL.md). No MCP round-trip, no network beyond the library itself.
- **MCP path** — the consolidated **`fd-daas-mcp`** server is the sole entry in repo-root [`.mcp.json`](.mcp.json). It exposes **176 tools across 7 groups** behind one stdio server and one `fd-daas-mcp` Click CLI. Use it for catalog browsing, cron scheduling, alerts, dashboards, workflow orchestration, and PDF semantic search.

Both paths are first-class. Skills are simpler and offline-friendly; the MCP server is richer (scheduling, alerts, orchestration).

---

## Install & Quick Start

Requirements: Python 3.10+ and [uv](https://docs.astral.sh/uv/). `dartlab` fetches need 3.12 — run them with `uv run --python 3.12 --with dartlab ...`.

```bash
# 1. Provision the root venv (data libs are declared deps)
uv sync

# 2. Configure credentials - create a repo-root .env (keys listed in Environment Variables below)
#    At minimum: DAAS_DATABASE_URL=sqlite:///daas.db  (+ the source keys you need)
#    Scripts auto-load .env; no manual export needed.

# 3. Skill path — list the source dispatch shapes (akshare_ / yfinance_ / edgar_ / …)
uv run python .claude/skills/skill-based-data-fetch/scripts/dispatch.py

# 4. Skill path — compute an existing indicator (upserts into observations)
uv run python .claude/skills/skill-based-data-fetch/scripts/run_indicator.py SPY_ma5

# 5. Query daas.db directly (db lives at the repo root)
sqlite3 daas.db "SELECT name, datasource, op FROM indicator_rules LIMIT 10"
sqlite3 daas.db "SELECT source, COUNT(*) FROM observations GROUP BY source"

# 6. MCP path — launch / health-check the consolidated server
fd-daas-mcp/bin/fd-daas-mcp-server                       # stdio server (what .mcp.json launches)
fd-daas-mcp/.venv/bin/python -m cli_anything.fd_daas_mcp.selfcheck   # registry + tool health check
```

The Quick Start commands above have been verified against this repo: `SPY_ma5` is a real `indicator_rules` row (139 rules total), `daas.db` holds 29,579 observations across 21 sources, and the `fd-daas-mcp` registry reports 176 tools across 7 groups.

For the full architecture, conventions, and the `daas.db` schema reference, see [`CLAUDE.md`](CLAUDE.md).

---

## Project Structure

```
cli-anything/
├── .claude/skills/          # Claude Code skills (skill-based-data-fetch is the core fetch skill)
├── fd-daas-mcp/             # Consolidated MCP server — sole .mcp.json entry (176 tools, 7 groups)
│   ├── alerts-mcp/          #   alert rule engine + 7 notification channels
│   ├── composite-mcp/       #   chained-tool pipelines over upstream MCPs
│   ├── cron-mcp/            #   task + schedule registry (DB-backed)
│   ├── daas-mcp/            #   datasource/function/indicator/entity catalog + compute
│   ├── dashboard-mcp/       #   standalone-HTML dashboard registry + query
│   ├── leader-mcp/          #   CrewAI data-fetch workflow orchestration
│   ├── pdf-mcp/             #   local PDF/text semantic search (sqlite-vec) [optional]
│   ├── bin/fd-daas-mcp-server      # launcher
│   └── cli_anything/fd_daas_mcp/   # server.py / registry.py / cli.py / selfcheck.py
├── daas.db                  # Shared SQLite database (ships as a demo dataset: registry + observations + scraw_*)
├── dashboards/              # Standalone HTML dashboards (+ index.html, daas.md)
├── construction/            # Architecture docs (mcp.md)
├── CLI-Anything/            # Upstream (do not modify)
└── .env                     # DAAS_DATABASE_URL, proxy, source auth keys, LLM config, ...
```

---

## `daas.db` Data Model

One SQLite file at the path in `DAAS_DATABASE_URL` (resolved against the repo root). Tables group by role:

| Role | Tables | What they hold |
|---|---|---|
| **Registry / catalog** | `sources`, `daas_functions`, `daas_function_columns`, `entities`, `entity_datasource_links`, `indicator_rules` | Datasource/function/column catalog; stocks/countries + their source identifiers; indicator bindings (table + columns + op + params) |
| **Computed series** | `observations` | Indicator output — one `(source, function_name, indicator, date)` point per row; upserted by `run_indicator.py`. Dashboards & alerts read this. |
| **Fetched source data** | `scraw_<slug>` | Raw rows pulled by a fetch (auto-created by `upsert.py`). `observations` are computed *from* these. |
| **Collections** | `entity_collections`, `indicator_collections`, `*_items`, `*_changes` | Named groups of entities/indicators + add-in/remove-out audit log |
| **MCP operational** | `dashboards`, `alert_rules`, `alert_events`, `schedules`, `tasks`, `leader_upstreams`, `workflows`, … | Dashboard registry, alert engine, cron state, leader/workflow state |

Query it directly from the repo root: `sqlite3 daas.db "SELECT …"` (`PRAGMA foreign_keys=ON` for FK cascade).

---

## Skills (`.claude/skills/`)

Skills are plain Markdown (`SKILL.md`) + Python scripts; they use `sqlite3` directly and never call an MCP tool.

| Skill | Purpose |
|---|---|
| **`skill-based-data-fetch`** *(core)* | Resolve an entity + indicator against `daas.db`, call the Python lib directly, persist to `scraw_*` / `observations`. |
| `fd-daas-fetch-data` | Entity → coverage → indicator workflow (sqlite3 + the core scripts). |
| `fd-daas-data-fetch` | Locate the source/function for an entity+indicator, register it, install deps, run the fetch. |
| `fd-daas-indicators-creator` | Persist a fetched series to a `scraw_<slug>` table (manual refresh — no cron). |
| `fd-daas-dashboard-creator` | Build a standalone ECharts HTML dashboard + register it. |
| `fd-daas-dashboard` | Find / open / inspect existing dashboards (read-only). |
| `fd-daas-research` | Orchestrate analyze → [collection] → indicators → dashboard. |
| `fd-daas-entities-collection-creator` | Define a rule-based entity collection (declarative JSON or Python rule script). |
| `fd-daas-entities-collection` | Day-to-day entity/collection operations (list, add/remove, sync, audit). |
| `fd-daas-indicators-collection-creator` | Curate an indicator collection + export CSV/markdown with resolved scores. |
| `fd-daas-pdf` | Ingest a PDF/text into a local vector store (sqlite-vec) and search semantically. Requires the `[pdf]` extra. |
| `fd-daas-scrapling-official` | Scrape anti-bot-protected pages (Cloudflare/JS render) via Scrapling. |
| `fd-daas-visualize` | Scaffold an ECharts page in the Next.js dashboard app. |
| `fd-skill-creator`, `openspec-*` | Infra: create/optimize skills; OpenSpec change lifecycle. |

---

## MCP Tool Groups (`fd-daas-mcp`)

The consolidated server exposes **176 tools across 7 groups**. Catalog is group-level (per-tool detail via the server's own introspection / `selfcheck`).

| Group | Prefix | Purpose |
|---|---|---|
| **daas** | `daas_*` | Datasource/function/column/entity/indicator catalog, indicator compute, LLM extraction, collections, entity coverage. |
| **dashboard** | `dashboard_*` | Standalone-HTML dashboard registry (CRUD), table query, stats, index regeneration. |
| **alerts** | `alerts_*` | Alert rule engine over observation series + 7 notification channels (Telegram/Discord/Slack/Twitter/DingTalk/Feishu/WeCom). |
| **cron** | `cron_*` | DB-backed task + schedule registry; ad-hoc `run_now`; execution history. |
| **leader** | `leader_*` | CrewAI data-fetch orchestration: specialist agents, workflows, multi-step runs, model tiers. |
| **composite** | `composite_*` | Chained-tool pipelines composing upstream MCP tools into linear workflows. |
| **pdf** | `pdf_*` | Local PDF/text semantic search (sqlite-vec + sentence-transformers). Optional — gated on the `sqlite_vec` import. |

Launch: `fd-daas-mcp/bin/fd-daas-mcp-server` (stdio). Both the server and the `fd-daas-mcp` CLI consume `registry.build()`, so the two surfaces cannot drift.

---

## Environment Variables

A single repo-root `.env` holds all config; scripts and the MCP server auto-load it. (Keys marked optional are only needed for the features they enable.)

| Key | Purpose | Required? |
|---|---|---|
| `DAAS_DATABASE_URL` | `sqlite:///` URL to `daas.db` (relative resolved against repo root, or absolute). | yes |
| `HTTP_PROXY` | Outbound proxy for data libraries. | optional |
| `EDGAR_IDENTITY` | SEC EDGAR identity string (`"Name email@domain"`). | for edgar |
| `EDINET_API_KEY` | Japan EDINET document fetch key. | for edinet |
| `MASSIVE_API_KEY` | Massive.com REST API key. | for massive |
| `CKAN_PORTAL_URL` | CKAN portal base URL. | for ckan |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Shared LLM endpoint for extraction / leader fallback. | for LLM features |
| `LEADER_MODELS`, `LEADER_MODEL_HIGH/BALANCE/FAST` | Per-tier model overrides for leader-mcp. | optional |
| `ALERTS_FEISHU_WEBHOOK_URL` | Feishu webhook for the alerts channel. | for feishu alerts |
| `DASHBOARD_PORT` | Port for the dashboard app. | optional |

---

## For AI Agents

If you are an AI agent (e.g. Claude Code) operating in this repo:

- **Prefer the skill path for fetching data.** Use `skill-based-data-fetch`: resolve the entity + indicator against `daas.db` via `sqlite3`, call the Python lib directly, persist with `upsert.py` / `run_indicator.py`. The dispatch table is at `.claude/skills/skill-based-data-fetch/scripts/dispatch.py` — run `uv run python …/dispatch.py --resolve <func>` to get the call shape for a function.
- **Workflow:** resolve → fetch → persist. Resolve entity+indicator in `daas.db`; fetch via the Python lib; persist into `scraw_<slug>` (raw) or `observations` (computed indicator).
- **Use the MCP path for everything else** — catalog browsing, creating indicators/collections, cron scheduling, alerts, building/finding dashboards, PDF semantic search, multi-step data workflows. These are the `fd-daas-mcp` tools (176 across 7 groups).
- **Query `daas.db` with `sqlite3` from the repo root** (`sqlite3 daas.db "…"`). The DB lives at the repo root, not under `mcp/`. Use `PRAGMA foreign_keys=ON` for FK cascade.
- **Authoritative architecture + schema reference:** [`CLAUDE.md`](CLAUDE.md) (it has a `## daas.db` section listing every table).

---

## License

Apache 2.0 — see upstream [CLI-Anything](https://github.com/HKUDS/CLI-Anything).
