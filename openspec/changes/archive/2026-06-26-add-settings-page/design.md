## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Dashboard /settings                        │
│                                                              │
│  ┌─ Bootstrap Section ───────────────────────────────────┐  │
│  │ DAAS_DATABASE_URL = sqlite:///mcp/daas.db              │  │
│  │   → Write to settings table + sync to .env file        │  │
│  │   ⚠️ Restart required: all MCPs + dashboard            │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ Runtime Section (scope: global) ──────────────────────┐  │
│  │ HTTP_PROXY  = http://proxy:8080      [Edit] [Live ✅]  │  │
│  │ HTTPS_PROXY = http://proxy:8080      [Edit] [Live ✅]  │  │
│  │ CKAN_URL    = https://data.gov/api/3/ [Edit] [Live ✅]  │  │
│  │   → Write to settings table only                        │  │
│  │   ✅ Immediate effect on next MCP tool call              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ Per-MCP Overrides ───────────────────────────────────┐  │
│  │ daas-mcp    HTTP_PROXY = socks5://special:1080  [Edit] │  │
│  │ ckan-mcp    HTTP_PROXY = (inherited from global) [Edit]│  │
│  │ akshare-mcp HTTP_PROXY = (inherited from global) [Edit]│  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Data Model

### New Table: `settings` (in `mcp/models/models.py`)

```python
class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_setting_scope_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(64), nullable=False, index=True, default="global")
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False, default="")
    category = Column(String(16), nullable=False, default="runtime")  # 'bootstrap' | 'runtime'
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

### Seed Data (from existing .env files)

| scope | key | category | source |
|-------|-----|----------|--------|
| `global` | `DAAS_DATABASE_URL` | `bootstrap` | root `.env` |
| `global` | `DASHBOARD_PORT` | `bootstrap` | root `.env` |
| `global` | `HTTP_PROXY` | `runtime` | root `.env` |
| `global` | `HTTPS_PROXY` | `runtime` | root `.env` |
| `global` | `NO_PROXY` | `runtime` | root `.env` |
| `global` | `CKAN_URL` | `runtime` | root `.env` (`CKAN_PORTAL_URL`) |

### Known MCP Scopes

`global`, `daas-mcp`, `cron-mcp`, `leader-mcp`, `ckan-mcp`, `cnstats-mcp`, `worldbank-mcp`, `akshare-mcp`, `dashboard-mcp`, `scrapling-uv-mcp`, `scrapling-docker-mcp`

## Component Design

### Dashboard: `src/app/settings/page.tsx` (Server Component)

```
page.tsx
├── ensureSeed()        — seed settings from .env files on first load
├── BootstrapSection    — table of bootstrap vars with amber badges
├── RuntimeSection      — table of runtime vars with green badges  
└── PerMcpSection       — per-MCP cards showing proxy overrides
```

Data flow: `page.tsx` reads `settings` table via `getDb('daas')` → passes to sections as props.

### Dashboard: `src/app/api/settings/route.ts` (API Route)

```
PUT  /api/settings          — upsert a setting row
DELETE /api/settings?id=X   — delete a setting row
```

- Bootstrap vars: after DB write, sync the key=value to root `.env`
- Runtime vars: DB write only
- Returns `{ok: true}` or `{error: "..."}`

### Dashboard: Client Component for Edit Forms

Ponytail: no separate client component file. Use a simple `<form>` with `action` pointing to the API route, plus `useRouter().refresh()` on submit. Avoids adding a state management pattern.

### MCP: `mcp/settings_helper.py`

```python
"""Shared runtime settings loader for MCP servers.

Usage in any MCP tool that makes HTTP requests:

    from settings_helper import load_runtime_settings
    load_runtime_settings('my-mcp-name')  # reads DB, sets os.environ
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv

_cache = {"ts": 0, "ttl": 5}  # 5-second cache

def _get_db_url():
    ROOT = Path(__file__).resolve().parent
    load_dotenv(ROOT / ".env")
    return os.environ.get("DAAS_DATABASE_URL", "sqlite:///mcp/daas.db")

def load_runtime_settings(scope: str = "global"):
    """Load runtime settings from daas.db, with scope priority.
    
    For each runtime key, checks: scope-specific → global → os.environ fallback.
    Cached for 5 seconds to avoid DB hits on every tool call.
    """
    now = time.time()
    if now - _cache["ts"] < _cache["ttl"]:
        return  # cache hit
    
    import sqlite3
    db_url = _get_db_url()
    db_path = db_url.replace("sqlite:///", "")
    
    conn = sqlite3.connect(db_path)
    try:
        # Load global settings
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE scope='global' AND category='runtime'"
        ).fetchall()
        for key, value in rows:
            if value:  # only override if has a value
                os.environ[key] = value
        
        # Load scope-specific overrides
        if scope != "global":
            rows = conn.execute(
                "SELECT key, value FROM settings WHERE scope=? AND category='runtime'",
                (scope,)
            ).fetchall()
            for key, value in rows:
                if value:
                    os.environ[key] = value
    finally:
        conn.close()
    
    _cache["ts"] = now
```

### MCP Integration: `ckan-mcp/server.py`

Only `ckan-mcp` makes direct HTTP calls (`ckanapi.RemoteCKAN`). Add at top of each tool function:

```python
@app.tool
def search_packages(query: str, ...):
    load_runtime_settings('ckan-mcp')  # ensure proxy/CKAN_URL are current
    CKAN_URL = os.environ.get("CKAN_URL", "https://data.gov.uk")
    ckan = ckanapi.RemoteCKAN(CKAN_URL)
    ...
```

Other MCPs (`worldbank-mcp`, `cnstats-mcp`) use `requests` but don't currently make outbound calls — they read local DB. They can add `load_runtime_settings()` later if they start making HTTP requests.

### Bootstrap Sync: Writing .env Files

```
PUT /api/settings with category='bootstrap'
  │
  ├─ 1. Write to settings table (sql.js)
  ├─ 2. Read root .env file (fs.readFileSync)
  ├─ 3. Replace the matching KEY= line (regex: ^KEY=.*$)
  ├─ 4. Write back .env (fs.writeFileSync)
  └─ 5. Return {ok: true, restartRequired: true}
```

Simple regex replacement — ponytail approach. If the key doesn't exist in .env, append it.

## Route Design

| Route | Method | Purpose |
|-------|--------|---------|
| `/settings` | GET | Page: view all settings |
| `/api/settings` | PUT | Upsert a setting |
| `/api/settings` | DELETE | Delete a setting (or clear override) |

## Key Decisions

1. **DB as runtime source of truth, .env as bootstrap fallback** — MCPs read runtime settings from DB on each call; .env only provides the initial DB path
2. **Scope-based overrides with fallback** — per-MCP settings override global; global overrides os.environ
3. **5-second cache on `load_runtime_settings()`** — prevents DB hits on every tool call; 5s is fine because settings changes are rare
4. **Bootstrap vars written to BOTH DB and .env** — DB for dashboard visibility, .env for MCP startup
5. **Only ckan-mcp integrates initially** — it's the only MCP making actual HTTP calls; others are DB-local
