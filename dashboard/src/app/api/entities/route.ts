import { NextRequest, NextResponse } from 'next/server';
import { loadEntityCollections } from '@/lib/entity-collections';
import { runPythonCli } from '@/lib/py-cli';
import { invalidateDb } from '@/lib/db';

// GET /api/entities — list all entity collections (sql.js read).
export async function GET() {
  try {
    const collections = await loadEntityCollections();
    return NextResponse.json({ collections });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}

// POST /api/entities — create an entity collection.
//   body: { name: string, description?: string, rule?: string (JSON) }
export async function POST(req: NextRequest) {
  let body: any;
  try { body = await req.json(); } catch { body = {}; }
  const name = String(body?.name ?? '').trim();
  if (!name) return NextResponse.json({ error: 'name is required' }, { status: 400 });
  const description =
    typeof body?.description === 'string' ? body.description : null;
  const rule =
    typeof body?.rule === 'string' && body.rule.length > 0 ? body.rule : null;

  const args: { name: string; description?: string; rule?: string } = { name };
  if (description !== null) args.description = description;
  if (rule !== null) args.rule = rule;

  const result = await runPythonCli(
    'collection_writer.py',
    'create-entity-collection',
    args,
  );
  if (!result.ok) {
    const status = /already exists/.test(result.error ?? '') ? 409 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  invalidateDb('daas.db');
  return NextResponse.json(result.data);
}
