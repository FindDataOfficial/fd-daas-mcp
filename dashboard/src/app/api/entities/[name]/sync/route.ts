import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// POST /api/entities/[name]/sync — run sync_entity_collection(name) in-process
// via the writer sidecar. Returns the {added, removed, unchanged} summary.
export async function POST(_req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const target = decodeURIComponent(name);
  const result = await runPythonCli(
    'collection_writer.py',
    'sync-entity-collection',
    { name: target },
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
