## 1. Data Layer

- [x] 1.1 Add `Setting` table to `mcp/models/models.py` with columns: id, scope, key, value, category (bootstrap|runtime), description, updated_at, and UniqueConstraint("scope", "key")
- [x] 1.2 Create `mcp/settings_helper.py` with `load_runtime_settings(scope)` — reads settings from daas.db, 5s cache, scope-priority: scope-specific > global > os.environ fallback

## 2. Dashboard API

- [x] 2.1 Create `dashboard/src/app/api/settings/route.ts` — PUT upserts a setting row, DELETE removes by id, bootstrap vars sync to root .env on PUT

## 3. Dashboard Page

- [x] 3.1 Create `dashboard/src/app/settings/page.tsx` — server component with ensureSeed(), BootstrapSection (amber badges), RuntimeSection (green badges), PerMcpSection (proxy overrides per MCP)
- [x] 3.2 Add Settings link to `dashboard/src/components/nav.tsx` LINKS array

## 4. MCP Integration

- [x] 4.1 Integrate `load_runtime_settings('ckan-mcp')` into `mcp/ckan-mcp/server.py` tool functions that make HTTP requests

## 5. Env Sync

- [x] 5.1 Update root `.env` comments noting settings are managed via dashboard `/settings`
