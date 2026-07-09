// @ts-nocheck
import { NextRequest, NextResponse } from 'next/server';
import { callTool } from '@/lib/mcp-call';
import { getDb, queryAll, invalidateDb } from '@/lib/db';

export const maxDuration = 120;

interface Ctx {
  params: Promise<{ name: string }>;
}

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

  try {
    if (action === 'run') {
      const result = await callTool('daas-mcp', 'run_rule', { name });
      invalidateDb('daas');
      return NextResponse.json({ ok: true, result });
    }

    if (action === 'delete') {
      const result = await callTool('daas-mcp', 'delete_rule', { name });
      invalidateDb('daas');
      return NextResponse.json({ ok: true, result });
    }

    if (action === 'toggle') {
      const db = await getDb('daas');
      const rows = queryAll(
        db,
        'SELECT enabled FROM process_rules WHERE name = ? LIMIT 1',
        [name],
      );
      if (!rows[0]) {
        return NextResponse.json({ error: `rule not found: ${name}` }, { status: 404 });
      }
      const current = !!rows[0].enabled;
      const result = await callTool('daas-mcp', 'update_rule', {
        name,
        enabled: !current,
      });
      invalidateDb('daas');
      return NextResponse.json({ ok: true, result });
    }

    if (action === 'update') {
      const result = await callTool('daas-mcp', 'update_rule', {
        name,
        source_table: body.source_table,
        text_column: body.text_column,
        schema: body.schema,
        prompt: body.prompt,
        model: body.model,
        max_chars: Number(body.max_chars) || 12000,
        datasource: body.datasource,
        enabled: body.enabled ?? true,
      });
      invalidateDb('daas');
      return NextResponse.json({ ok: true, result });
    }

    return NextResponse.json({ error: `unknown action: ${action}` }, { status: 400 });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}
