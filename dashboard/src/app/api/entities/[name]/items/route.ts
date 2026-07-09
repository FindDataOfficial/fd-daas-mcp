import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// POST /api/entities/[name]/items — add a member (records add_in).
//   body: { entity_id?: number, entity_type?: string, code?: string, reason?: string }
export async function POST(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const args: { collection_name: string; entity_id?: number; entity_type?: string; code?: string; reason?: string } = {
    collection_name,
  };
  if (body?.entity_id != null) args.entity_id = Number(body.entity_id);
  if (typeof body?.entity_type === 'string') args.entity_type = body.entity_type;
  if (typeof body?.code === 'string') args.code = body.code;
  if (typeof body?.reason === 'string') args.reason = body.reason;

  if (args.entity_id == null && (!args.entity_type || !args.code)) {
    return NextResponse.json(
      { error: 'provide entity_id, or both entity_type and code' },
      { status: 400 },
    );
  }

  const result = await runPythonCli(
    'collection_writer.py',
    'add-entity-item',
    args,
  );
  if (!result.ok) {
    const err = result.error ?? '';
    const status =
      /not found/.test(err) ? 404 :
      500;
    return NextResponse.json({ error: err }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}

// DELETE /api/entities/[name]/items — remove a member (records remove_out).
//   body: { entity_id?: number, entity_type?: string, code?: string, reason?: string }
export async function DELETE(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const args: { collection_name: string; entity_id?: number; entity_type?: string; code?: string; reason?: string } = {
    collection_name,
  };
  if (body?.entity_id != null) args.entity_id = Number(body.entity_id);
  if (typeof body?.entity_type === 'string') args.entity_type = body.entity_type;
  if (typeof body?.code === 'string') args.code = body.code;
  if (typeof body?.reason === 'string') args.reason = body.reason;

  if (args.entity_id == null && (!args.entity_type || !args.code)) {
    return NextResponse.json(
      { error: 'provide entity_id, or both entity_type and code' },
      { status: 400 },
    );
  }

  const result = await runPythonCli(
    'collection_writer.py',
    'remove-entity-item',
    args,
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}

// PATCH /api/entities/[name]/items — reorder members.
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
    'reorder-entity-items',
    { collection_name, ordered_item_ids: ordered },
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 400;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
