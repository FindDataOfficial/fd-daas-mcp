// @ts-nocheck
import { NextRequest, NextResponse } from 'next/server';
import { getMCPTools } from '@/lib/mcp-client';
import { unwrap } from '@/lib/mcp-call';
import { invalidateDb } from '@/lib/db';

export const maxDuration = 120;

/**
 * POST /api/agents — create a specialist agent via leader-mcp.
 *
 * Body: { action: "create", name, upstream, role, goal, backstory?, model?, enabled? }
 *
 * `model` may be a string (LEADER_MODELS name), `null` (shared LLM_* fallback),
 * or omitted (same as null for create). leader-mcp validates the upstream and
 * rejects duplicate names; those soft errors come back as 400. If leader-mcp
 * cannot start, returns 502.
 */
export async function POST(req: NextRequest) {
  let body: any;
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  if (body?.action !== 'create') {
    return NextResponse.json({ error: 'expected action: "create"' }, { status: 400 });
  }
  if (!body.name || !body.upstream || !body.role || !body.goal) {
    return NextResponse.json(
      { error: 'name, upstream, role, and goal are required' },
      { status: 400 },
    );
  }

  let tools: Record<string, any>;
  try {
    tools = await getMCPTools('leader-mcp');
  } catch (e: any) {
    return NextResponse.json(
      { error: `leader-mcp unavailable: ${e?.message ?? String(e)}` },
      { status: 502 },
    );
  }

  const tool = tools.create_specialist_agent;
  if (!tool || typeof tool.execute !== 'function') {
    return NextResponse.json(
      { error: "tool 'create_specialist_agent' not exposed by leader-mcp" },
      { status: 502 },
    );
  }

  // Only forward optional keys when present (undefined is dropped by JSON
  // stringification, so leader-mcp sees them omitted → tool default). `model:
  // null` IS forwarded (distinct from omitted) so create treats it as the
  // shared-fallback choice — same as omitting for create.
  const args: any = {
    name: body.name,
    upstream: body.upstream,
    role: body.role,
    goal: body.goal,
  };
  if (body.backstory !== undefined) args.backstory = body.backstory;
  if (body.model !== undefined) args.model = body.model;
  if (body.enabled !== undefined) args.enabled = body.enabled;

  try {
    const raw = await tool.execute(args);
    const { data, error } = unwrap(raw);
    if (error) {
      return NextResponse.json({ error }, { status: 400 });
    }
    // create_specialist_agent wrote via leader-mcp (separate process); drop the
    // cached sql.js handle so the next render re-reads the file.
    invalidateDb('daas');
    return NextResponse.json({ ok: true, result: data });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}
