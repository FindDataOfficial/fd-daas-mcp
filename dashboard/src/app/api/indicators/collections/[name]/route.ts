import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// DELETE /api/indicators/collections/[name] — delete a collection (cascades to items + changes).
export async function DELETE(_req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);

  const result = await runPythonCli(
    'collection_writer.py',
    'delete-indicator-collection',
    { name: collection_name },
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}

// PATCH /api/indicators/collections/[name] — update name/description.
//   body: { new_name?: string, description?: string }
export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const args: { name: string; new_name?: string; description?: string } = { name: collection_name };
  if (typeof body?.new_name === 'string' && body.new_name.trim()) args.new_name = body.new_name.trim();
  if (typeof body?.description === 'string') args.description = body.description;

  const result = await runPythonCli(
    'collection_writer.py',
    'update-indicator-collection',
    args,
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
