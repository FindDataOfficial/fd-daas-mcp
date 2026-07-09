import { NextRequest, NextResponse } from 'next/server';
import { searchEntitiesForPicker } from '@/lib/entity-collections';

// GET /api/entities/search?q=<query>&limit=<n>
// Live entity search for the "Add member" picker (name / ticker / code).
export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const q = sp.get('q') ?? '';
  const limit = sp.get('limit') ? Number(sp.get('limit')) : 20;
  try {
    const entities = await searchEntitiesForPicker(q, limit);
    return NextResponse.json({ entities, count: entities.length });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}
