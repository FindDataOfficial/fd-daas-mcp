# Dashboard Construction

## Architecture

Next.js 15 + sql.js (WASM) — reads `daas.db` directly. No API server, no `CREATE TABLE` statements.

## Env

```bash
# dashboard/.env.local
DAAS_DATABASE_URL=sqlite:///../mcp/daas.db
```

All env flows from root `.env`. Dashboard resolves the DB path from `DAAS_DATABASE_URL` by stripping the `sqlite:///` prefix.

## Schema

**Schema is managed by `mcp/models/models.py`.** The dashboard does NOT define tables.

`dashboard/src/lib/schema.ts` holds TypeScript interfaces as mirrors. When a schema changes, update `mcp/models/models.py` first, then reflect here.

## Key Files

| File | Role |
|------|------|
| `src/lib/db.ts` | sql.js connection, query helpers. No `CREATE TABLE`. |
| `src/lib/schema.ts` | TS type mirrors of `mcp/models/models.py` |
| `src/lib/seed.ts` | Populates `datasources` + `datasource_columns` in `daas.db` |
| `src/app/datasources/page.tsx` | Datasource list page |
| `src/app/datasources/[id]/columns/page.tsx` | Column metadata editor |
| `src/app/databases/[dbName]/[tableName]/page.tsx` | Table browser |
| `src/app/cron/page.tsx` | Cron management |
| `src/components/` | Shared UI: nav, data-table, echarts-wrapper |

## Key Decisions

- **Direct sql.js access** — not through dashboard-mcp MCP tools. Faster, simpler, no network hop. Schema truth stays in `mcp/models/models.py`.
- **No `dashboard.db`** — `datasources` and `datasource_columns` live in `daas.db`.
- **No `initDashboardDb()`** — tables created by `Base.metadata.create_all()` via any MCP that imports `mcp.models`.
