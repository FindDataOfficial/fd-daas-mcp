import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

const DAAS_DB = 'daas.db';

// POST: set or clear a per-collection item score override.
//   body: { collection_name: string, source_name: string, section_name?: string | null, score: number | null }
//   score = null clears the override (item falls back to the datasource default).
export async function POST(req: NextRequest) {
  let body: any;
  try { body = await req.json(); } catch { body = {}; }

  const collection_name = String(body?.collection_name ?? '').trim();
  const source_name = String(body?.source_name ?? '').trim();
  if (!collection_name || !source_name) {
    return NextResponse.json(
      { error: 'collection_name and source_name are required' },
      { status: 400 },
    );
  }
  const section_name =
    typeof body?.section_name === 'string' && body.section_name.length > 0
      ? body.section_name
      : null;

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

  const result = await runPythonCli('collection_writer.py', 'set-item-score', {
    collection_name,
    source_name,
    section_name,
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
