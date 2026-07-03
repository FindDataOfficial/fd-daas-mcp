import { NextRequest, NextResponse } from 'next/server';
import { loadCollections } from '@/lib/collections';
import { runPythonCli } from '@/lib/py-cli';

export async function GET() {
  try {
    const items = await loadCollections();
    return NextResponse.json({ collections: items });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  let body: any;
  try { body = await req.json(); } catch { body = {}; }
  const name = String(body?.name ?? '').trim();
  if (!name) return NextResponse.json({ error: 'name is required' }, { status: 400 });

  const description = typeof body?.description === 'string' ? body.description : null;
  const result = await runPythonCli('collection_writer.py', 'create', { name, description });
  if (!result.ok) {
    const status = /already exists/.test(result.error ?? '') ? 409 : 500;
    return NextResponse.json({ error: result.error }, { status });
  }
  return NextResponse.json(result.data);
}
