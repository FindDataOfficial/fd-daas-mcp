---
name: fd-daas-visualize
description: Scaffold a new ECharts-powered visualization page in the MCP Dashboard project (dashboard/). Generates Next.js 15 App Router pages with Server Components for data fetching, Client Components with ECharts charts, and optional API routes.
---

# FD-DAAS Visualize

Generate a new ECharts visualization page in the `dashboard/` project.

## Project Scope

This skill operates within `dashboard/` at the repo root — a Next.js 15 App Router project with TypeScript, Tailwind CSS, better-sqlite3, and echarts-for-react. All generated files go under `dashboard/src/`.

## Prerequisites

- Dashboard project exists at `dashboard/` (Next.js 15, TypeScript, Tailwind, better-sqlite3, echarts-for-react)
- SQLite databases at `mcp/*.db` (daas.db, leader_mcp.db, cron.db, dashboard.db)
- ECharts wrapper component at `dashboard/src/components/echarts-wrapper.tsx`

## What You Generate

For each new visualization page, create 2-3 files:

1. **`dashboard/src/app/<page>/page.tsx`** — Server Component that reads from SQLite and passes data to the chart
2. **`dashboard/src/app/<page>/chart.tsx`** — `'use client'` component wrapping EChartsWrapper with the chart config
3. **`dashboard/src/api/<page>/route.ts`** — API route (optional, only if client-side refresh needed)

## Workflow

### Step 1: Gather Requirements

Ask the user these questions (one at a time):

1. **Page name**: URL-safe slug (e.g., `function-stats`, `observation-trends`). Becomes route `/function-stats`.
2. **Database**: Which SQLite database? Options: `daas`, `leader_mcp`, `cron`, `dashboard`, or a custom path relative to `mcp/`.
3. **SQL query**: The SELECT query. Use `?` for parameters if needed.
4. **Chart type**: `bar`, `line`, `pie`, `scatter`, `area`, or describe custom ECharts config.
5. **Title**: Display title for the page and chart.

### Step 2: Generate the Files

#### File 1: `dashboard/src/app/<page>/page.tsx` (Server Component)

```tsx
import { getDb } from '@/lib/db';
import PageChart from './chart';

export const dynamic = 'force-dynamic';

export default async function GeneratedPage() {
  const db = getDb('<database>');
  const data = db.prepare('<SQL query>').all() as Record<string, unknown>[];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6"><Title></h1>
      <div className="bg-white border rounded-lg p-4">
        <PageChart data={data} />
      </div>
    </div>
  );
}
```

#### File 2: `dashboard/src/app/<page>/chart.tsx` (Client Component)

```tsx
'use client';

import EChartsWrapper from '@/components/echarts-wrapper';
import type { EChartsOption } from 'echarts';

interface Props { data: Record<string, unknown>[]; }

export default function PageChart({ data }: Props) {
  const option: EChartsOption = {
    title: { text: '<Title>', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    // ... chart-specific config
  };
  return <EChartsWrapper option={option} />;
}
```

#### File 3: `dashboard/src/api/<page>/route.ts` (API Route, optional)

```ts
import { getDb } from '@/lib/db';
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const db = getDb('<database>');
  const data = db.prepare('<SQL query>').all();
  return NextResponse.json(data);
}
```

### Step 3: Register in Navigation

Ask: "Add this page to the sidebar?" If yes, update `dashboard/src/components/nav.tsx`.

## Chart Type Templates

### Bar Chart
```ts
const option: EChartsOption = {
  xAxis: { type: 'category', data: data.map(d => String(d.label)) },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: data.map(d => Number(d.value)) }],
};
```

### Pie Chart
```ts
const option: EChartsOption = {
  series: [{
    type: 'pie', radius: ['40%', '70%'],
    data: data.map(d => ({ name: String(d.label), value: Number(d.value) })),
  }],
};
```

### Line Chart
```ts
const option: EChartsOption = {
  xAxis: { type: 'category', data: data.map(d => String(d.label)) },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: data.map(d => Number(d.value)), smooth: true }],
};
```

### Time-Series
```ts
const option: EChartsOption = {
  xAxis: { type: 'category', data: data.map(d => String(d.date)), axisLabel: { rotate: 45 } },
  yAxis: { type: 'value' },
  series: [
    { name: 'Series 1', type: 'line', data: data.map(d => Number(d.value1)) },
    { name: 'Series 2', type: 'line', data: data.map(d => Number(d.value2)) },
  ],
};
```

## Rules

- `'use client'` on chart components — ECharts needs DOM
- `export const dynamic = 'force-dynamic'` on Server Components reading SQLite
- Pass data as props: Server Component → Client Component (no fetch in client)
- Use existing `EChartsWrapper` from `@/components/echarts-wrapper`
- All SQLite access via `getDb()` from `@/lib/db`
- Format dates with `.slice(0, 10)`
- Chart height: 400px (wrapper default)
