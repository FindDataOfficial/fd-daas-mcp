# Design: Unify Env and Schema

**Change**: `unify-env-and-schema` | **Date**: 2025-06-26

## Architecture

```
cli-anything/
├── .env                              ← all shared config lives here
├── mcp/
│   ├── models/                       ← NEW: single truth package
│   │   ├── pyproject.toml
│   │   ├── __init__.py               # from mcp.models.models import *
│   │   └── models.py                 # one Base, all tables
│   ├── daas.db                       ← the ONE database
│   ├── leader-mcp/
│   │   ├── .env                      ← overrides only (e.g. :memory: for tests)
│   │   ├── unified_models.py         # re-exports from mcp.models (back compat)
│   │   └── leader_database.py        # DAAS_DATABASE_URL
│   ├── cron-mcp/
│   │   ├── .env
│   │   ├── models.py                 ← DELETED
│   │   └── database.py              # DAAS_DATABASE_URL
│   ├── daas-mcp/
│   │   ├── .env
│   │   ├── models.py                 ← DELETED
│   │   └── daas_database.py          # DAAS_DATABASE_URL
│   ├── dashboard-mcp/
│   │   ├── .env
│   │   └── server.py                 # from mcp.models import Datasource...
│   ├── ckan-mcp/.env
│   ├── cnstats-mcp/.env
│   └── worldbank-mcp/.env
└── dashboard/
    ├── .env.local                    # Next.js native, reads DAAS_DATABASE_URL
    └── src/lib/db.ts                 # no CREATE TABLE, reads DAAS_DATABASE_URL
```

## Env Loading Order

```
┌────────────────────────────┐
│ .env (project root)         │  load_dotenv(root) first
│ DAAS_DATABASE_URL=          │
│   sqlite:///mcp/daas.db     │
│ HTTP_PROXY=                 │
│ HTTPS_PROXY=                │
│ CKAN_PORTAL_URL=            │
└──────────┬─────────────────┘
           │
           ▼
┌────────────────────────────┐
│ mcp/leader-mcp/.env         │  load_dotenv(local, override=True) second
│ # DAAS_DATABASE_URL=        │  only uncomment to override
│ #   sqlite:///:memory:      │
└────────────────────────────┘
           │
           ▼
    os.environ["DAAS_DATABASE_URL"]  ← final value
```

Every MCP `server.py` starts with:

```python
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # mcp/
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)
```

## mcp/models/ Package

### pyproject.toml

```toml
[project]
name = "mcp-models"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["sqlalchemy>=2.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

### models.py — One Base, Multiple Domains

Tables with different schemas for the same concept stay separate (e.g. `DaasFunction` vs `Function`). No forced unification.

```
┌─────────────────────────────────────────────────────────┐
│ Base = declarative_base()                                │
│                                                         │
│ ── leader-mcp domain ──                                 │
│ Function         (harness, command, category, ...)       │
│ FunctionColumn   (column_name, column_type, ...)         │
│ DataSnapshot     (function_id FK, params_json, ...)      │
│                                                         │
│ ── cron-mcp domain ──                                   │
│ Schedule         (name, cron_expr, task_name, ...)       │
│ Execution        (schedule_id, status, output, ...)      │
│ Task             (name, command, timeout, ...)           │
│                                                         │
│ ── daas-mcp domain ──                                   │
│ DaasSource       (name, label, url, config, ...)         │
│ DaasFunction     (source_id FK, name, label, ...)        │
│ DaasFunctionColumn (function_id FK, name, type, ...)     │
│ Observation      (source, function_name, indicator, ...) │
│ ScrawConfig      (url, name, columns_json, ...)          │
│                                                         │
│ ── dashboard domain ──                                  │
│ Datasource       (name, db_type, connection_string, ...) │
│ DatasourceColumn (datasource_id FK, table_name, ...)     │
└─────────────────────────────────────────────────────────┘
```

### Dependencies

Each MCP that uses models adds to its `pyproject.toml`:

```toml
[tool.uv.sources]
mcp-models = { path = "../models", editable = true }
```

```bash
cd mcp/leader-mcp && uv pip install -e ../models
```

## Env Var Consolidation

| Before (per MCP) | After (all subsystems) |
|---|---|
| `LEADER_MCP_DATABASE_URL` | `DAAS_DATABASE_URL` |
| `CRON_MCP_DATABASE_URL` | `DAAS_DATABASE_URL` |
| `DATABASE_URL` (daas-mcp) | `DAAS_DATABASE_URL` |
| `DAAS_REGISTRY_DB` (daas-mcp) | `DAAS_DATABASE_URL` |
| `DASHBOARD_DB_DIR` (dashboard + dashboard-mcp) | `DAAS_DATABASE_URL` |
| `CKAN_DATABASE_URL` | `DAAS_DATABASE_URL` |

## Dashboard Changes

### db.ts — Remove CREATE TABLE

Before: `initDashboardDb()` defines `datasources` + `datasource_columns` tables inline.

After: Tables already exist in `daas.db` (created by `mcp/models` via any MCP that calls `Base.metadata.create_all()`). Dashboard just connects.

```typescript
// Before
const DB_DIR = process.env.DASHBOARD_DB_DIR || path.join(process.cwd(), '..', 'mcp');

// After
const DB_PATH = process.env.DAAS_DATABASE_URL?.replace('sqlite:///', '')
  || path.join(process.cwd(), '..', 'mcp', 'daas.db');
```

### schema.ts — Mirror Comment

Keep the interface definitions (TypeScript needs them), but add a header comment:

```typescript
/**
 * TypeScript mirrors of mcp/models/models.py tables.
 * Schema changes MUST be made in mcp/models/models.py first,
 * then reflected here.
 */
```

### seed.ts

Update to read `DAAS_DATABASE_URL` and target only the single `daas.db`.

## Cleanup

| File | Reason |
|------|--------|
| `mcp/leader_mcp.db` | Orphan — no code references it since leader-mcp switched to `daas.db` |
| `mcp/daas_registry.db` | Orphan — daas-mcp will use `daas.db` |
| `mcp/cron.db` | Orphan — cron-mcp already points to `daas.db` |
| `mcp/custom_path.db` | Unknown origin |
| `mcp/dashboard.db` | Migrate `datasources` + `datasource_columns` into `daas.db` |
| `mcp/cron-mcp/models.py` | Moved into `mcp/models/models.py` |
| `mcp/daas-mcp/models.py` | Moved into `mcp/models/models.py` |
| `.mcp.json` `env` blocks | Servers read `.env` themselves now |
