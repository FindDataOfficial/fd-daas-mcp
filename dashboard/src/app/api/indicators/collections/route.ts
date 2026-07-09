import { NextRequest, NextResponse } from 'next/server';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';
import { loadIndicatorCollections } from '@/lib/indicator-scores';

// GET /api/indicators/collections — list all indicator collections (sql.js read).
export async function GET() {
  try {
    const collections = await loadIndicatorCollections();
    return NextResponse.json({ collections });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}

// POST /api/indicators/collections — create an indicator collection.
//   body: { name: string, description?: string }
export async function POST(req: NextRequest) {
  let body: any;
  try { body = await req.json(); } catch { body = {}; }
  const name = String(body?.name ?? '').trim();
  if (!name) return NextResponse.json({ error: 'name is required' }, { status: 400 });
  const description =
    typeof body?.description === 'string' ? body.description : null;

  const args: { name: string; description?: string } = { name };
  if (description !== null) args.description = description;

  const result = await runPythonCli(
    'collection_writer.py',
    'create-indicator-collection',
    args,
  );
  if (!result.ok) {
    const status = /already exists/.test(result.error ?? '') ? 409 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
