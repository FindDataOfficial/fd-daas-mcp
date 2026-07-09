import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

interface RouteCtx {
  params: Promise<{ name: string; indicator: string }>;
}

// POST /api/indicators/collections/[name]/items/[indicator]/score
//   body: { score: number | null }
//   score = null clears the per-item override (item inherits the indicator's
//   default score, which itself inherits the datasource default when NULL).
export async function POST(req: NextRequest, ctx: RouteCtx) {
  const { name, indicator } = await ctx.params;
  const collection_name = decodeURIComponent(name);
  const indicator_name = decodeURIComponent(indicator);
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  let score: number | null | undefined;
  if (body?.score === null || body?.score === undefined) {
    score = null; // clear override
  } else if (typeof body.score === 'number' && Number.isFinite(body.score)) {
    score = body.score;
  } else if (typeof body.score === 'string' && body.score.trim() !== '' && Number.isFinite(Number(body.score))) {
    score = Number(body.score);
  } else {
    return NextResponse.json(
      { error: 'score must be a number or null' },
      { status: 400 },
    );
  }

  const result = await runPythonCli(
    'collection_writer.py',
    'set-indicator-collection-item-score',
    { collection_name, indicator_name, score },
  );
  if (!result.ok) {
    const err = result.error ?? '';
    const status = /not found|not in collection/.test(err) ? 404 : 500;
    return NextResponse.json({ error: err }, { status });
  }

  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
