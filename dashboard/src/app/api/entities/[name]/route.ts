import { NextRequest, NextResponse } from 'next/server';
import { loadEntityCollectionDetail } from '@/lib/entity-collections';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// GET /api/entities/[name] — collection detail + current members.
export async function GET(_req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  try {
    const coll = await loadEntityCollectionDetail(decodeURIComponent(name));
    if (!coll) return NextResponse.json({ error: 'not found' }, { status: 404 });
    return NextResponse.json(coll);
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}

// PATCH /api/entities/[name] — partial update of name and/or description and/or rule.
//   body: { new_name?: string, description?: string, rule?: string (JSON), clear_rule?: bool }
export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const currentName = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const newName = typeof body?.new_name === 'string' ? body.new_name.trim() : '';
  const hasDescription = typeof body?.description === 'string';
  const hasRule = typeof body?.rule === 'string';
  const clearRule = !!body?.clear_rule;
  if (!newName && !hasDescription && !hasRule && !clearRule) {
    return NextResponse.json(
      { error: 'at least one of new_name, description, rule, or clear_rule is required' },
      { status: 400 },
    );
  }

  const args: { name: string; new_name?: string; description?: string; rule?: string; clear_rule?: boolean } = {
    name: currentName,
  };
  if (newName) args.new_name = newName;
  if (hasDescription) args.description = body.description;
  if (hasRule) args.rule = body.rule;
  if (clearRule) args.clear_rule = true;

  const result = await runPythonCli(
    'collection_writer.py',
    'update-entity-collection',
    args,
  );
  if (!result.ok) {
    const err = result.error ?? '';
    const status =
      /already exists/.test(err) ? 409 :
      /not found/.test(err) ? 404 :
      /at least one/i.test(err) ? 400 :
      500;
    return NextResponse.json({ error: err }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}

// DELETE /api/entities/[name] — delete the collection (cascades to items + changes).
export async function DELETE(_req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const target = decodeURIComponent(name);
  const result = await runPythonCli(
    'collection_writer.py',
    'delete-entity-collection',
    { name: target },
  );
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
