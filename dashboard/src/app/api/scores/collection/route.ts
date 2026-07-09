import { NextRequest, NextResponse } from 'next/server';
import { loadCollectionScores } from '@/lib/scores';

// GET: return one collection's items with per-item score override + the
// datasource default + the resolved effective score. Used by the /scores
// page's collection picker (client-side fetch on picker change).
//   ?name=<collection name>
export async function GET(req: NextRequest) {
  const name = req.nextUrl.searchParams.get('name') ?? '';
  if (!name.trim()) {
    return NextResponse.json({ error: 'name is required' }, { status: 400 });
  }
  const detail = await loadCollectionScores(name);
  if (!detail) {
    return NextResponse.json(
      { error: `Collection '${name}' not found` },
      { status: 404 },
    );
  }
  return NextResponse.json(detail);
}
