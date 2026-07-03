import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// POST: add an item to the collection (drag-drop from catalog).
//   body: { source_name: string, section_name?: string | null }
export async function POST(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }
  const source_name = String(body?.source_name ?? '').trim();
  if (!source_name) {
    return NextResponse.json({ error: 'source_name is required' }, { status: 400 });
  }
  const section_name =
    typeof body?.section_name === 'string' && body.section_name.length > 0
      ? body.section_name
      : null;

  const result = await runPythonCli('collection_writer.py', 'add-item', {
    collection_name,
    source_name,
    section_name,
  });
  if (!result.ok) {
    const err = result.error ?? '';
    const status =
      /already in collection/.test(err) ? 409 :
      /not found/.test(err) ? 404 :
      500;
    return NextResponse.json({ error: err }, { status });
  }
  return NextResponse.json(result.data);
}

// DELETE: remove an item.
//   body: { source_name: string, section_name?: string | null }
export async function DELETE(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }
  const source_name = String(body?.source_name ?? '').trim();
  if (!source_name) {
    return NextResponse.json({ error: 'source_name is required' }, { status: 400 });
  }
  const section_name =
    typeof body?.section_name === 'string' && body.section_name.length > 0
      ? body.section_name
      : null;

  const result = await runPythonCli('collection_writer.py', 'remove-item', {
    collection_name,
    source_name,
    section_name,
  });
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  return NextResponse.json(result.data);
}

// PATCH: reorder items.
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
  const result = await runPythonCli('collection_writer.py', 'reorder', {
    collection_name,
    ordered_item_ids: ordered,
  });
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 400;
    return NextResponse.json({ error: result.error }, { status });
  }
  return NextResponse.json(result.data);
}
