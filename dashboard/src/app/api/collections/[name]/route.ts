import { NextRequest, NextResponse } from 'next/server';
import { loadCollection } from '@/lib/collections';
import { runPythonCli } from '@/lib/py-cli';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

export async function GET(_req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  try {
    const coll = await loadCollection(decodeURIComponent(name));
    if (!coll) return NextResponse.json({ error: 'not found' }, { status: 404 });
    return NextResponse.json(coll);
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const currentName = decodeURIComponent(name);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  // Partial update of name and/or description. At least one is required.
  // `{ new_name }`-only callers (the workspace rename control) keep working —
  // the `update` writer subcommand is a superset of `rename`.
  const newName =
    typeof body?.new_name === 'string' ? body.new_name.trim() : '';
  const hasDescription = typeof body?.description === 'string';
  if (!newName && !hasDescription) {
    return NextResponse.json(
      { error: 'at least one of new_name or description is required' },
      { status: 400 },
    );
  }

  // `undefined` values are dropped by JSON.stringify, so the writer sees
  // `args.get(...)` as None. An explicit empty description string clears it.
  const args: { name: string; new_name?: string; description?: string } = {
    name: currentName,
  };
  if (newName) args.new_name = newName;
  if (hasDescription) args.description = body.description;

  const result = await runPythonCli('collection_writer.py', 'update', args);
  if (!result.ok) {
    const err = result.error ?? '';
    const status =
      /already exists/.test(err) ? 409 :
      /not found/.test(err) ? 404 :
      /at least one/i.test(err) ? 400 :
      500;
    return NextResponse.json({ error: err }, { status });
  }
  return NextResponse.json(result.data);
}

export async function DELETE(_req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const target = decodeURIComponent(name);
  const result = await runPythonCli('collection_writer.py', 'delete', { name: target });
  if (!result.ok) {
    const status = /not found/.test(result.error ?? '') ? 404 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  return NextResponse.json(result.data);
}
