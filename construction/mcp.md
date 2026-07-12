# MCP Construction

> **STALE (replace-fetch-stack-with-skills):** the MCP servers described below
> (`fd-daas-mcp` and all `mcp/*-mcp/` upstreams) are **removed**. Data fetch is
> now skill-driven: skills call Python data libraries directly and read/write
> `daas.db` via `sqlite3`. `.mcp.json` is empty. See `CLAUDE.md` for the current
> architecture and `.claude/skills/skill-based-data-fetch/`. The schema tables
> described below (`sources`, `daas_function_columns`, `observations`, etc.)
> still exist in `daas.db` and are valid - only the MCP *access* layer is gone.

## Env & Schema (unified 2025-06-26)

**Single source of truth:** `mcp/models/models.py` — one SQLAlchemy `Base`, 13 tables across all MCP domains.

**Single database:** `daas.db` — all MCPs and the dashboard read/write here.

**Single env file:** `.env` (project root) — `DAAS_DATABASE_URL`, proxy, CKAN portal, dashboard port.

### Env Loading

Every MCP `server.py` loads:

```python
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")                       # root first
load_dotenv(Path(__file__).parent / ".env", override=True)  # local overrides
```

Root `.env` sets defaults. Per-MCP `.env` overrides only what needs to differ (database for testing, different proxy, etc.).

### Schema Package

`mcp/models/` — installable `pyproject.toml` package. Each MCP depends on it:

```bash
cd mcp/<name>-mcp && pip install -e ../models
```

```python
from models import Base, Function, Schedule, Task, Datasource, ...
```

**Table domains:**

| Domain | Tables |
|--------|--------|
| leader-mcp | `functions`, `function_columns`, `data_snapshots` |
| cron-mcp | `schedules`, `executions`, `tasks`, `cron_data_jobs`, `cron_fetch_results` |
| daas-mcp | `sources`, `daas_functions`, `daas_function_columns`, `observations` |
| scrapling | `scraw_configs` |
| dashboard | `datasources`, `datasource_columns` |
| composite-mcp | `composites`, `upstreams`, `composite_tools`, `composite_chains` |

Schema changes go in `mcp/models/models.py` first, then propagate to consumers.

### MCP Servers

> **Consolidated into `fd-daas-mcp`** (2026-07-11): `alerts-mcp`, `composite-mcp`, `cron-mcp`, `leader-mcp`, `daas-mcp`, and `dashboard-mcp` are consolidated into the single `fd-daas-mcp` server (the sole `.mcp.json` entry). Their tools are the canonical client-facing surface, invoked as `mcp__fd-daas-mcp__<group>_<tool>` / `fd-daas-mcp <group> <tool>`. The table below remains a schema/provenance record; each `mcp/*-mcp/` dir + selfcheck stays on disk as an importable module host.

| Server | Directory | DB via | Notes |
|--------|-----------|--------|-------|
| leader-mcp | `mcp/leader-mcp/` | `from models import ...` | multi-harness registry |
| cron-mcp | `mcp/cron-mcp/` | `from models import ...` | scheduler, `models.py` deleted; cross-MCP data fetch via `fastmcp.Client` over `.mcp.json` (`mcp_client.py` + `fetch_runner.py`); `schedules.data_job_id` guarded ALTER + `PRAGMA foreign_keys=ON` for `ON DELETE SET NULL` |
| daas-mcp | `mcp/daas-mcp/` | `from models import DaasSource, ...` | source-based registry, `models.py` deleted; also hosts the process tools (LLM extraction + math indicators) relocated from the former process-mcp; `seed_massive_endpoints.py` registers Massive.com's 37 REST endpoints as `daas_functions`+columns + Economy `indicator_rules` (12 endpoints entitlement-gated); `backfill_massive.py` populates `scraw_massive_*` IN-PROCESS via the `mcp_massive` package (no subprocess - the massive group is folded into fd-daas-mcp); `fetch_data` dispatches `<source>_<func>` calls -> in-process via `fd-world` for `akshare_`/`worldbank_`/`ckan_`/`cnstats_`/`wbdata_`, and by shelling out to `uv run --directory fd-<source> fd-<source> call … --json` for the `dartlab_`/`edgar_`/`edinet_`/`yfinance_` CLI harnesses; `seed_external_mcps.py` marks each datasource's section `instruction` as CLI-routed/in-process (`cli=<source> function=<source>_<func>` -> `fetch_data`); the `mcp=` routing kind is removed (all data-fetch upstreams folded in-process); dartlab added under `Filings -> KR-DART` |
| dashboard-mcp | `mcp/dashboard-mcp/` | `from models import Datasource, ...` | no inline CREATE TABLE |
| ckan-mcp | `mcp/ckan-mcp/` | inline models (ponytail) | dotenv loading added |
| cnstats-mcp | `mcp/cnstats-mcp/` | `cli_anything.world.core.models` | dotenv loading added |
| worldbank-mcp | `mcp/worldbank-mcp/` | `cli_anything.world.core.models` | dotenv loading added |
| akshare-mcp | `mcp/akshare-mcp/` | `cli_anything.akshare.core.models` | untouched |
| scrapling-*-mcp | `mcp/scrapling-*-mcp/` | own `init_db.py` | untouched |
| composite-mcp | `mcp/composite-mcp/` | `from models import Composite, ...` | composite MCP — curate selected tools from upstreams + chained tools; one composite per process via `COMPOSITE` env |

### CLI Harnesses (data-fetch, shelled out by daas-mcp `fetch_data`)

> **BREAKING (data-fetch-mcps-to-cli)**: the `dartlab-mcp`/`edgartools-mcp`/`edinet-mcp`/`yfinance-mcp` servers are **removed**; their data surface moved to CLI harnesses fetched via `daas-mcp fetch_data("<source>_<func>", '{…}')`. `ask_data_crew`/`call_data_mcp`/specialist-agent/`composite-mcp` callers targeting those four upstream names no longer work - use `fetch_data` instead. Remaining data-fetch upstreams: `akshare`/`cnreport`/`ckan`/`cnstats`/`worldbank` (+ `massive`).

| Harness | Dir | Package / Script | Wraps | Functions | Auth | Notes |
|---------|-----|------------------|-------|-----------|------|-------|
| yfinance (canonical) | `fd-yfinance/` | `cli_anything.yfinance` / `fd-yfinance` | `yfinance` | `yfinance_*` (curated) | none | reused as-is; daas datasource `yfinance` (id 22) + entities; replaces `yfinance-mcp` |
| dartlab | `fd-dartlab/` | `cli_anything.dartlab` / `fd-dartlab` | `dartlab` (KR DART + US EDGAR) | `dartlab_company_panel`, `dartlab_panel_search`, `dartlab_list_filings`, `dartlab_get_credit`, `dartlab_analyze`, `dartlab_scan` (6) | KEYLESS; optional `DART_API_KEY` | `requires-python>=3.12`; daas datasource `dartlab` + KR/US entities (`ticker`); replaces `dartlab-mcp` |
| edgar | `fd-edgar/` | `cli_anything.edgar` / `fd-edgar` | `edgar` (EdgarTools, SEC) | `edgar_get_company`, `edgar_list_filings`, `edgar_get_filing`, `edgar_get_financials`, `edgar_get_insider_trades` (5) | `EDGAR_IDENTITY` required | daas datasource `edgar` (id 20) + US entities (`ticker`, CIK alias); replaces `edgartools-mcp` |
| edinet | `fd-edinet/` | `cli_anything.edinet` / `fd-edinet` | `edinet_tools` (Japan EDINET) | `edinet_search_entities`, `edinet_get_entity`, `edinet_list_documents`, `edinet_get_document`, `edinet_supported_doc_types` (5) | `EDINET_API_KEY` (only `list_documents`/`get_document`) | daas datasource `edinet` (id 21) + JP entities (EDINET code); replaces `edinet-mcp` |

Each harness is a standalone uv project (own venv), loaded into `daas.db` via `.trae/skills/fd-daas-data-fetch/references/<source>.registry.json` + `load_registry_json.py`. `daas-mcp fetch_data("<source>_<func>", '{…}')` shells out to `uv run --directory fd-<source> fd-<source> call <func> k=v --json`.

### Deleted Files

- `mcp/leader_mcp.db` — zombie
- `mcp/daas_registry.db` — zombie
- `mcp/cron.db` — zombie
- `mcp/dashboard.db` — migrated to `daas.db`
- `mcp/cron-mcp/models.py` — moved to `mcp/models/`
- `mcp/daas-mcp/models.py` — moved to `mcp/models/`

### composite-mcp model (one composite per process)

`composite-mcp` curates a composite MCP: selected tools from multiple upstream MCP servers (proxied verbatim via `create_proxy` + a lazy `FilterTools` transform + `mount(namespace=<upstream>)`) plus chained tools (linear pipelines with `$prev`/`$step[N]` reference resolution). **One composite served per process**, selected by the `COMPOSITE` env var — to serve a second composite, add another `.mcp.json` entry pointing at the same `server.py` with a different `COMPOSITE`. Selection is persisted in `daas.db` (`composites`/`upstreams`/`composite_tools`/`composite_chains`); management tools are always present and changes apply on restart. See `openspec/changes/archive/2026-06-28-add-combine-mcp/` for the full design.
