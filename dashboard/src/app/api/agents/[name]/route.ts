// @ts-nocheck
import { NextRequest, NextResponse } from 'next/server';
import { getMCPTools } from '@/lib/mcp-client';
import { unwrap } from '@/lib/mcp-call';
import { getDb, queryAll, invalidateDb } from '@/lib/db';

export const maxDuration = 120;

interface Ctx {
  params: Promise<{ name: string }>;
}

async function getTools() {
  try {
    const tools = await getMCPTools('leader-mcp');
    return { tools, error: null };
  } catch (e: any) {
    return { tools: null, error: `leader-mcp unavailable: ${e?.message ?? String(e)}` };
  }
}

/**
 * POST /api/agents/[name] — update or toggle a specialist agent.
 *
 * Body: { action: "update", role?, goal?, backstory?, model?, enabled?, upstream? }
 *    OR { action: "toggle" }
 *
 * For `update`, only the fields present in the body are forwarded to
 * `update_specialist_agent` (omitted fields are unchanged). `model: null` is a
 * present field meaning "clear the override"; `model` omitted means "unchanged".
 * For `toggle`, the current `enabled` is read from daas.db via sql.js and
 * flipped. Soft errors (unknown agent, bad upstream, delete-refused) → 400;
 * leader-mcp down → 502.
 */
export async function POST(req: NextRequest, ctx: Ctx) {
  const { name: rawName } = await ctx.params;
  const name = decodeURIComponent(rawName);

  let body: any;
  try {
    body = await req.json();
  } catch {
    body = {};
  }
  const action = body?.action;

  const { tools, error: toolsError } = await getTools();
  if (toolsError) {
    return NextResponse.json({ error: toolsError }, { status: 502 });
  }

  const updateTool = tools.update_specialist_agent;
  if (!updateTool || typeof updateTool.execute !== 'function') {
    return NextResponse.json(
      { error: "tool 'update_specialist_agent' not exposed by leader-mcp" },
      { status: 502 },
    );
  }

  try {
    if (action === 'toggle') {
      // Read the current enabled state directly from daas.db (no leader-mcp
      // spawn for the read), then flip it via update_specialist_agent.
      const db = await getDb('daas');
      const rows = queryAll(
        db,
        'SELECT enabled FROM specialist_agents WHERE name = ? LIMIT 1',
        [name],
      );
      if (!rows[0]) {
        return NextResponse.json({ error: `agent not found: ${name}` }, { status: 404 });
      }
      const current = !!rows[0].enabled;
      const raw = await updateTool.execute({ name, enabled: !current });
      const { data, error } = unwrap(raw);
      if (error) return NextResponse.json({ error }, { status: 400 });
      invalidateDb('daas');
      return NextResponse.json({ ok: true, result: data });
    }

    if (action === 'update') {
      // Forward only present fields. `undefined` is dropped by JSON
      // stringification → leader-mcp sees them omitted → unchanged. `null` is
      // forwarded → for `model`, clears the override.
      const args: any = { name };
      if (body.role !== undefined) args.role = body.role;
      if (body.goal !== undefined) args.goal = body.goal;
      if (body.backstory !== undefined) args.backstory = body.backstory;
      if (body.model !== undefined) args.model = body.model;
      if (body.enabled !== undefined) args.enabled = body.enabled;
      if (body.upstream !== undefined) args.upstream = body.upstream;

      const raw = await updateTool.execute(args);
      const { data, error } = unwrap(raw);
      if (error) return NextResponse.json({ error }, { status: 400 });
      invalidateDb('daas');
      return NextResponse.json({ ok: true, result: data });
    }

    return NextResponse.json({ error: `unknown action: ${action}` }, { status: 400 });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}

/**
 * DELETE /api/agents/[name] — delete a specialist agent via leader-mcp.
 *
 * leader-mcp refuses the delete (400) when a `workflow_steps.agent` row still
 * references the agent; the error names the referencing workflow(s) verbatim.
 */
export async function DELETE(_req: NextRequest, ctx: Ctx) {
  const { name: rawName } = await ctx.params;
  const name = decodeURIComponent(rawName);

  const { tools, error: toolsError } = await getTools();
  if (toolsError) {
    return NextResponse.json({ error: toolsError }, { status: 502 });
  }

  const tool = tools.delete_specialist_agent;
  if (!tool || typeof tool.execute !== 'function') {
    return NextResponse.json(
      { error: "tool 'delete_specialist_agent' not exposed by leader-mcp" },
      { status: 502 },
    );
  }

  try {
    const raw = await tool.execute({ name });
    const { data, error } = unwrap(raw);
    if (error) return NextResponse.json({ error }, { status: 400 });
    invalidateDb('daas');
    return NextResponse.json({ ok: true, result: data });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}
