import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// POST /api/indicators/collections/[name]/items — add an indicator (records add_in).
//   body: { indicator_name: string, score?: number, reason?: string }
export async function POST(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const indicator_name = String(body?.indicator_name ?? '').trim();
  if (!indicator_name) {
    return NextResponse.json({ error: 'indicator_name is required' }, { status: 400 });
  }
  const args: { collection_name: string; indicator_name: string; score?: number; reason?: string } = {
    collection_name,
    indicator_name,
  };
  if (body?.score != null) args.score = Number(body.score);
  if (typeof body?.reason === 'string') args.reason = body.reason;

  const result = await runPythonCli('collection_writer.py', 'add-indicator-item', args);
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}

// DELETE /api/indicators/collections/[name]/items — remove an indicator (records remove_out).
//   body: { indicator_name: string, reason?: string }
export async function DELETE(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const indicator_name = String(body?.indicator_name ?? '').trim();
  if (!indicator_name) {
    return NextResponse.json({ error: 'indicator_name is required' }, { status: 400 });
  }
  const args: { collection_name: string; indicator_name: string; reason?: string } = {
    collection_name,
    indicator_name,
  };
  if (typeof body?.reason === 'string') args.reason = body.reason;

  const result = await runPythonCli('collection_writer.py', 'remove-indicator-item', args);
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}

// PATCH /api/indicators/collections/[name]/items — reorder items.
//   body: { ordered_item_ids: number[] }
export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }
  const ordered = body?.ordered_item_ids;
  if (!Array.isArray(ordered) || ordered.some((n) => !Number.isInteger(n))) {
    return NextResponse.json(
      { error: 'ordered_item_ids must be an array of integers' },
      { status: 400 },
    );
  }
  const result = await runPythonCli(
    'collection_writer.py',
    'reorder-indicator-items',
    { collection_name, ordered_item_ids: ordered },
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 400;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
