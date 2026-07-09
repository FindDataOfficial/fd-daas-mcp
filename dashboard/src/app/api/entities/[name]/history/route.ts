import { NextRequest, NextResponse } from 'next/server';
import { loadEntityCollectionHistory } from '@/lib/entity-collections';

interface RouteCtx {
  params: Promise<{ name: string }>;
}

// GET /api/entities/[name]/history — the add-in / remove-out audit log,
// newest first. Optional `?action=add_in|remove_out` and `?limit=N`.
export async function GET(req: NextRequest, ctx: RouteCtx) {
  const { name } = await ctx.params;
  const collectionName = decodeURIComponent(name);
  const sp = req.nextUrl.searchParams;
  const action = sp.get('action');
  const limitRaw = sp.get('limit');
  const limit = limitRaw ? Number(limitRaw) : 100;
  const validAction =
    action === 'add_in' || action === 'remove_out' ? action : null;
  try {
    const changes = await loadEntityCollectionHistory(
      collectionName,
      validAction,
      limit,
    );
    return NextResponse.json({ changes, count: changes.length });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? String(e) }, { status: 500 });
  }
}
