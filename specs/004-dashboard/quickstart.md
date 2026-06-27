# Quickstart: MCP Dashboard

**Feature**: 004-dashboard | **Date**: 2025-06-25

## Prerequisites

- Node.js 20+
- Existing MCP databases at `mcp/leader_mcp.db`, `mcp/cron.db`, `mcp/daas.db`

## Setup

```bash
# 1. Create Next.js project
cd /path/to/cli-anything
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir --no-import-alias

# 2. Install deps
cd dashboard
npm install better-sqlite3 echarts echarts-for-react
npm install -D @types/better-sqlite3 vitest @testing-library/react @testing-library/jest-dom

# 3. Set DB path (optional, defaults to ../mcp/)
echo 'DASHBOARD_DB_DIR=../mcp' > .env.local

# 4. Run dev server
npm run dev
# → http://localhost:3000
```

## Validation Scenarios

### 1. Database Viewer (Read-Only)

1. Open `http://localhost:3000/databases`
2. **Expected**: Database cards listed (leader_mcp, cron, daas, dashboard) with table counts
3. Click on `leader_mcp` → `functions`
4. **Expected**: Paginated data table. Sortable column headers. No edit buttons.

### 2. Cron Task Management (CRUD)

1. Open `http://localhost:3000/cron`
2. **Expected**: Task list (left), schedule list (right), ECharts execution history chart (bottom)
3. Click "Edit" on a task → `/cron/tasks/<id>`
4. **Expected**: Form with command, description, timeout fields
5. Change description, click Save
6. **Expected**: Redirect to /cron, toast "Task updated"
7. Toggle a schedule → **Expected**: enabled status flips, toast confirmation
8. Delete a task → **Expected**: confirmation dialog, then removed from list

### 3. Datasource Management

1. Open `http://localhost:3000/datasources`
2. Click "Add Datasource"
3. Fill: name="test_db", type="sqlite", connection="mcp/test.db"
4. **Expected**: New datasource appears in list
5. Click on it → detail page with "Scan Schema" button
6. Click "Scan Schema" → columns populate from SQLite introspection
7. Edit a column description, save → toast confirmation
8. Delete datasource → removed from list

### 4. ECharts Visualization

1. Open `http://localhost:3000/cron`
2. **Expected**: Execution history bar chart renders (success green, fail red)
3. Hover over bar → tooltip shows date + counts
4. Window resize → chart resizes responsively

### 5. Dashboard Page Skill

```bash
# Trigger the skill
/dashboard-page
```

1. Skill prompts: "Page name?" → "stock_overview"
2. Skill prompts: "SQL query?" → "SELECT category, COUNT(*) as count FROM functions GROUP BY category"
3. Skill prompts: "Chart type?" → "pie"
4. Skill prompts: "Database?" → "leader_mcp"
5. **Expected**: Generated files:
   - `src/app/stock-overview/page.tsx` (Server Component)
   - `src/app/stock-overview/chart.tsx` (Client Component, ECharts pie)
   - `src/api/stock-overview/route.ts` (data endpoint)
6. Open `http://localhost:3000/stock-overview`
7. **Expected**: Pie chart showing function count by category

## Running Tests

```bash
cd dashboard
npx vitest run
# Expected: 12-18 tests passing (API routes + components)
```
