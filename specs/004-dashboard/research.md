# Research: MCP Dashboard

**Feature**: 004-dashboard | **Date**: 2025-06-25

## R1: Web Framework Choice

**Decision**: Next.js 15 with App Router, TypeScript.

**Rationale**:
- User explicitly requested Next.js.
- App Router gives us Server Components for data-heavy pages (zero client JS for table browsing), API routes for mutations.
- better-sqlite3 is synchronous — perfect for Server Components that read SQLite directly without async overhead.
- One project (`dashboard/`) — no separate backend. Next.js IS the backend.

**Alternatives considered**:
- Flask (previous plan): Dropped per user request.
- Next.js Pages Router: App Router is the modern default, better for RSC/streaming.
- Remix/SvelteKit: Good but user asked for Next.js specifically.

## R2: Database Strategy

**Decision**: Three SQLite databases accessed via better-sqlite3.

**Rationale**:
- `leader_mcp.db` — **read-only**. Existing unified registry.
- `cron.db` — **read-write**. Existing scheduler data.
- `dashboard.db` — **read-write**. New. Stores datasource definitions and column metadata.
- better-sqlite3 is synchronous, fast, and works natively in Node.js Server Components.
- Each DB gets its own connection via a connection manager (`lib/db.ts`).

**Alternatives considered**:
- Prisma/Drizzle ORM: Overkill for reading existing schemas we don't control. Raw SQL with better-sqlite3 is simpler.
- sql.js (WASM): Slower, async-only, more complex.

## R3: ECharts Integration

**Decision**: echarts-for-react in Client Components, data fetched via API routes.

**Rationale**:
- ECharts needs a DOM — must be a Client Component (`'use client'`).
- Data flows: Server Component → API route (fetch on client) → echarts-for-react → rendered chart.
- echarts-for-react handles lifecycle (init, resize, dispose) cleanly.
- Charts register on demand to keep bundle small: `echarts/core` + needed components.

**Alternatives considered**:
- Raw echarts init in useEffect: More boilerplate, harder to clean up.
- Recharts/Nivo: Simpler but less capable for complex financial/time-series charts.
- ECharts CDN + vanilla JS: Works but harder to type and test in TypeScript.

## R4: Skill for Dashboard Page Scaffolding

**Decision**: Create a skill (`dashboard-page`) that generates Next.js page + API route + ECharts component.

**Rationale**:
- Follows project pattern of skills under `.claude/skills/`.
- Skill will: (1) prompt for page name, SQL query, chart type, (2) generate `src/app/<page>/page.tsx` (Server Component), (3) generate `src/app/<page>/chart.tsx` (Client Component with ECharts), (4) generate `src/api/<page>/route.ts` (data endpoint).
- Generated files follow the same patterns as existing dashboard pages.

**Alternatives considered**:
- Code generation CLI: Less interactive, harder to guide through chart type selection.
- Manual creation: Defeats the purpose.

## R5: Project Structure

**Decision**: `dashboard/` at repo root — a standalone Next.js project, not under `mcp/`.

**Rationale**:
- Next.js is its own project with its own `package.json`, `node_modules`, config files.
- `mcp/` is for Python MCP servers — different runtime, different dependency manager.
- Keeps Node.js and Python worlds cleanly separated.
- DB paths resolve via `../../mcp/` relative to the Next.js project root, or via `DASHBOARD_DB_DIR` env var.

## R6: Testing Strategy

**Decision**: vitest for unit/integration, testing-library for components.

**Rationale**:
- vitest is the standard for Next.js/Vite projects.
- API routes tested via `next` test helpers (invoke handlers directly).
- Components tested with @testing-library/react.
- Test fixtures: temporary SQLite copies created per test suite.

## R7: Styling

**Decision**: Tailwind CSS.

**Rationale**:
- Zero-config with Next.js (`create-next-app` default).
- Utility-first means no separate CSS files for each component.
- Dark mode built in (prefers-color-scheme).
- No design system needed for 5-page admin dashboard.

**Alternatives considered**:
- CSS Modules: More boilerplate per component.
- shadcn/ui: Nice but adds dependency overhead for a simple admin UI.
