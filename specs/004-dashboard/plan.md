# Implementation Plan: MCP Dashboard

**Branch**: `004-dashboard` | **Date**: 2025-06-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-dashboard/spec.md`

## Summary

Build a web-based dashboard to manage MCP databases (leader_mcp.db, cron.db). Features: (1) read-only database viewer for all SQLite databases, (2) CRUD management for cron tasks/schedules, (3) datasource & column metadata tables, (4) a skill to scaffold new ECharts-powered dashboard pages.

Technical approach: Next.js 15 App Router with TypeScript, better-sqlite3 for direct SQLite access, Tailwind CSS, and ECharts via echarts-for-react. Lives at repo root as `dashboard/`.

## Technical Context

**Language/Version**: TypeScript 5.x, Node.js 20+
**Primary Dependencies**: next, react, better-sqlite3, echarts, echarts-for-react, tailwindcss
**Storage**: SQLite via better-sqlite3 (reads existing: leader_mcp.db, cron.db, daas.db; new: dashboard.db)
**Testing**: vitest + @testing-library/react (or playwright for E2E)
**Target Platform**: Web browser (local dev server `next dev`, optional Docker later)
**Project Type**: Web application (Next.js App Router + API Routes)
**Performance Goals**: Sub-second page loads for <1000 records; RSC streaming for large tables
**Constraints**: Read-only on existing MCP databases, writes only to dashboard.db and cron.db (via API routes)
**Scale/Scope**: Single admin user, ~5 pages, ~10 database tables total

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Spec-Kit First | ✅ PASS | Following spec-kit workflow: plan → tasks → implement |
| II. Test-Driven | ✅ PASS | vitest for API routes, component tests with testing-library |
| III. Bilingual Docs | ✅ PASS | README and spec will have zh versions |
| IV. Continuous Improvement | ✅ PASS | Builds on existing MCP infrastructure |
| V. Minimum Viable Complexity | ✅ PASS | Next.js App Router over heavier full-stack frameworks; SQLite over Postgres; no separate backend |

## Project Structure

### Documentation (this feature)

```text
specs/004-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API route contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
dashboard/                    # Next.js 15 App Router
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
├── postcss.config.mjs
├── src/
│   ├── app/
│   │   ├── layout.tsx         # Root layout (sidebar nav)
│   │   ├── page.tsx           # Home → redirect to /databases
│   │   ├── globals.css        # Tailwind + base styles
│   │   ├── databases/
│   │   │   ├── page.tsx       # Database list (server component)
│   │   │   └── [dbName]/
│   │   │       └── [tableName]/
│   │   │           └── page.tsx  # Table browser (server component)
│   │   ├── cron/
│   │   │   ├── page.tsx       # Cron dashboard (ECharts + task/schedule lists)
│   │   │   ├── tasks/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx  # Edit task form
│   │   │   └── schedules/
│   │   │       └── [id]/
│   │   │           └── page.tsx  # Edit schedule form
│   │   └── datasources/
│   │       ├── page.tsx       # Datasource list
│   │       └── [id]/
│   │           ├── page.tsx   # Datasource detail
│   │           └── columns/
│   │               └── page.tsx  # Column editor
│   ├── api/                   # API route handlers
│   │   ├── databases/
│   │   │   └── route.ts       # GET /api/databases
│   │   ├── databases/[dbName]/[tableName]/
│   │   │   └── route.ts       # GET rows (paginated, sorted)
│   │   ├── cron/tasks/
│   │   │   ├── route.ts       # GET/POST tasks
│   │   │   └── [id]/route.ts  # PUT/DELETE task
│   │   ├── cron/schedules/
│   │   │   ├── route.ts       # GET schedules
│   │   │   └── [id]/route.ts  # PUT/DELETE/toggle schedule
│   │   ├── cron/executions/
│   │   │   └── route.ts       # GET execution history
│   │   ├── datasources/
│   │   │   ├── route.ts       # GET/POST datasources
│   │   │   └── [id]/
│   │   │       ├── route.ts   # GET/PUT/DELETE datasource
│   │   │       └── columns/
│   │   │           └── route.ts  # GET/PUT columns
│   │   └── stats/
│   │       └── route.ts       # GET aggregated stats for charts
│   ├── lib/
│   │   ├── db.ts              # better-sqlite3 connection manager
│   │   ├── schema.ts          # TypeScript types for all tables
│   │   └── utils.ts           # Pagination, sorting helpers
│   └── components/
│       ├── nav.tsx            # Sidebar navigation
│       ├── data-table.tsx     # Reusable sortable/paginated table
│       ├── echarts-wrapper.tsx # ECharts client component wrapper
│       └── flash.tsx          # Toast/notification component
└── tests/
    ├── api/
    │   ├── databases.test.ts
    │   ├── cron.test.ts
    │   └── datasources.test.ts
    └── components/
        └── data-table.test.tsx
```

**Structure Decision**: Next.js App Router at `dashboard/` (repo root, not under `mcp/` — it's a standalone web app, not an MCP server). Server Components for data fetching (reads SQLite directly), Client Components only where interactivity needed (ECharts, forms). API routes for mutations. better-sqlite3 is synchronous and fast — perfect for Server Components that read on each request.

## Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| US1: Database Viewer | ✅ Done | `/databases`, browse any table with pagination/sort |
| US2: Cron Management | ✅ Done | `/cron` with ECharts (execution history bar + schedule pie) |
| US3: Datasource Columns | ✅ Done | `/datasources`, auto-seeded from existing DBs, `/datasources/:id/columns` |
| US4: Page Skill | ✅ Done | `/dashboard-page` skill at `.claude/skills/dashboard-page/SKILL.md` |
| Tailwind CSS | ✅ Done | Sidebar nav, responsive layout |
| Seed datasources | ✅ Done | Auto-discovers columns from daas.db, leader_mcp.db, cron.db |

## Complexity Tracking

> No violations. All gates pass.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| N/A | N/A | N/A |
