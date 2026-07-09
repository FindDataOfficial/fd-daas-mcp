import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

const DAAS_DB = 'daas.db';

// POST: set or clear an indicator's default score.
//   body: { name: string, score: number | null }
//   score = null clears the default (indicator inherits the datasource's sources.score).
export async function POST(req: NextRequest) {
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const name = String(body?.name ?? '').trim();
  if (!name) {
    return NextResponse.json({ error: 'name is required' }, { status: 400 });
  }

  let score: number | null | undefined;
  if (body?.score === null || body?.score === undefined) {
    score = null; // clear
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

  const result = await runPythonCli('collection_writer.py', 'set-indicator-score', {
    name,
    score,
  });
  if (!result.ok) {
    const err = result.error ?? '';
    const status = /not found/.test(err) ? 404 : 500;
    return NextResponse.json({ error: err }, { status });
  }

  invalidateDb(DAAS_DB);
  return NextResponse.json(result.data);
}
