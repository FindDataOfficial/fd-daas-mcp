# MCP Construction

## Env & Schema (unified 2025-06-26)

**Single source of truth:** `mcp/models/models.py` — one SQLAlchemy `Base`, 13 tables across all MCP domains.

**Single database:** `mcp/daas.db` — all MCPs and the dashboard read/write here.

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
| cron-mcp | `schedules`, `executions`, `tasks` |
| daas-mcp | `sources`, `daas_functions`, `daas_function_columns`, `observations` |
| scrapling | `scraw_configs` |
| dashboard | `datasources`, `datasource_columns` |
| composite-mcp | `composites`, `upstreams`, `composite_tools`, `composite_chains` |

Schema changes go in `mcp/models/models.py` first, then propagate to consumers.

### MCP Servers

| Server | Directory | DB via | Notes |
|--------|-----------|--------|-------|
| leader-mcp | `mcp/leader-mcp/` | `from models import ...` | multi-harness registry |
| cron-mcp | `mcp/cron-mcp/` | `from models import ...` | scheduler, `models.py` deleted |
| daas-mcp | `mcp/daas-mcp/` | `from models import DaasSource, ...` | source-based registry, `models.py` deleted; also hosts the process tools (LLM extraction + math indicators) relocated from the former process-mcp; `seed_massive_endpoints.py` registers Massive.com's 37 REST endpoints as `daas_functions`+columns + Economy `indicator_rules` (12 endpoints entitlement-gated); `backfill_massive.py` populates `scraw_massive_*` via a persistent `fastmcp.Client` (routes around the broken pipeline-bridge) |
| dashboard-mcp | `mcp/dashboard-mcp/` | `from models import Datasource, ...` | no inline CREATE TABLE |
| ckan-mcp | `mcp/ckan-mcp/` | inline models (ponytail) | dotenv loading added |
| cnstats-mcp | `mcp/cnstats-mcp/` | `cli_anything.daas.core.models` | dotenv loading added |
| worldbank-mcp | `mcp/worldbank-mcp/` | `cli_anything.daas.core.models` | dotenv loading added |
| akshare-mcp | `mcp/akshare-mcp/` | `cli_anything.akshare.core.models` | untouched |
| scrapling-*-mcp | `mcp/scrapling-*-mcp/` | own `init_db.py` | untouched |
| composite-mcp | `mcp/composite-mcp/` | `from models import Composite, ...` | composite MCP — curate selected tools from upstreams + chained tools; one composite per process via `COMPOSITE` env |
| hkreport-mcp | `mcp/hkreport-mcp/` | none (live HKEXnews + akshare) | HK filings + financials; 5 tools, edgartools-style; keyless |

### Deleted Files

- `mcp/leader_mcp.db` — zombie
- `mcp/daas_registry.db` — zombie
- `mcp/cron.db` — zombie
- `mcp/dashboard.db` — migrated to `daas.db`
- `mcp/cron-mcp/models.py` — moved to `mcp/models/`
- `mcp/daas-mcp/models.py` — moved to `mcp/models/`

### composite-mcp model (one composite per process)

`composite-mcp` curates a composite MCP: selected tools from multiple upstream MCP servers (proxied verbatim via `create_proxy` + a lazy `FilterTools` transform + `mount(namespace=<upstream>)`) plus chained tools (linear pipelines with `$prev`/`$step[N]` reference resolution). **One composite served per process**, selected by the `COMPOSITE` env var — to serve a second composite, add another `.mcp.json` entry pointing at the same `server.py` with a different `COMPOSITE`. Selection is persisted in `daas.db` (`composites`/`upstreams`/`composite_tools`/`composite_chains`); management tools are always present and changes apply on restart. See `openspec/changes/archive/2026-06-28-add-combine-mcp/` for the full design.
