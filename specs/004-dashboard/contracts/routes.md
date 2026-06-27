# Route Contracts: MCP Dashboard

**Feature**: 004-dashboard | **Date**: 2025-06-25

## Overview

Next.js App Router. Pages are Server Components (RSC) where possible; Client Components for ECharts and forms. API routes handle all mutations (POST/PUT/DELETE).

## Pages (App Router)

### `/` — Home
Redirects to `/databases`.

### `/databases` — Database List
- **Type**: Server Component
- **Data**: Lists all known SQLite databases (leader_mcp, cron, daas, dashboard)
- **Actions**: Click table name → `/databases/<db>/<table>`

### `/databases/[dbName]/[tableName]` — Table Browser
- **Type**: Server Component
- **Data**: Paginated rows, sortable columns
- **Query params**: `?page=1&perPage=50&sort=col&order=asc`
- **Read-only**: No edit buttons on this page

### `/cron` — Cron Dashboard
- **Type**: Server Component wrapping a Client Component for charts
- **Data**: Tasks list, schedules list, recent executions
- **Chart**: ECharts bar chart (executions per day, success vs fail) — Client Component
- **Actions**: Edit task, toggle schedule, delete task

### `/cron/tasks/[id]` — Edit Task
- **Type**: Client Component (form)
- **Fields**: command, description, timeout
- **Actions**: Save (PUT), Delete

### `/cron/schedules/[id]` — Edit Schedule
- **Type**: Client Component (form)
- **Fields**: cron expression, enabled, timezone
- **Actions**: Save (PUT), Toggle

### `/datasources` — Datasource List
- **Type**: Server Component
- **Data**: All datasources with column counts
- **Actions**: Add datasource, delete

### `/datasources/[id]` — Datasource Detail
- **Type**: Server Component
- **Data**: Datasource metadata + column list by table
- **Actions**: Edit columns, scan schema

### `/datasources/[id]/columns` — Column Editor
- **Type**: Client Component (form)
- **Data**: Editable column descriptions and types per table
- **Actions**: Save (PUT)

## API Routes

### `GET /api/databases` — List databases
```json
{
  "databases": [
    {"name": "leader_mcp", "path": "...", "tables": [...], "readonly": true}
  ]
}
```

### `GET /api/databases/[dbName]/[tableName]` — Query table rows
Query: `?page=1&perPage=50&sort=id&order=asc`
```json
{
  "columns": ["id", "name", ...],
  "rows": [...],
  "page": 1,
  "totalPages": 5,
  "totalRows": 230
}
```

### `GET /api/cron/tasks` — List all tasks
### `POST /api/cron/tasks` — Create task
Body: `{ "name": "...", "command": "...", "description": "...", "timeout": 60 }`

### `PUT /api/cron/tasks/[id]` — Update task
### `DELETE /api/cron/tasks/[id]` — Delete task (cascades to schedules)

### `GET /api/cron/schedules` — List schedules
### `PUT /api/cron/schedules/[id]` — Update schedule
### `DELETE /api/cron/schedules/[id]` — Delete schedule
### `POST /api/cron/schedules/[id]/toggle` — Toggle enabled

### `GET /api/cron/executions` — Execution history
Query: `?limit=50&scheduleId=xxx`

### `GET /api/datasources` — List datasources
### `POST /api/datasources` — Add datasource
### `GET /api/datasources/[id]` — Datasource detail
### `PUT /api/datasources/[id]` — Update datasource
### `DELETE /api/datasources/[id]` — Delete datasource

### `GET /api/datasources/[id]/columns` — List columns
### `PUT /api/datasources/[id]/columns` — Bulk update column metadata

### `GET /api/stats` — Aggregated chart data
```json
{
  "executionHistory": [
    {"date": "2025-06-25", "completed": 10, "failed": 2}
  ],
  "functionsByCategory": [
    {"category": "stock", "count": 120}
  ]
}
```

## Error Handling

- API routes return `{ "error": "message" }` with appropriate HTTP status
- 404: Next.js built-in not-found page
- 500: Error boundary in layout catches server errors
- Form validation: Return 422 with field-level errors
