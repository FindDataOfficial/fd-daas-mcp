// @ts-nocheck
import { NextRequest, NextResponse } from 'next/server';
import { callTool } from '@/lib/mcp-call';
import { invalidateDb } from '@/lib/db';

export const maxDuration = 120;

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
  if (!body.name || !body.source_table || !body.text_column || !body.schema) {
    return NextResponse.json(
      { error: 'name, source_table, text_column, and schema are required' },
      { status: 400 },
    );
  }

  try {
    const result = await callTool('daas-mcp', 'create_rule', {
      name: body.name,
      source_table: body.source_table,
      text_column: body.text_column,
      schema: body.schema,
      prompt: body.prompt,
      model: body.model,
      max_chars: Number(body.max_chars) || 12000,
      datasource: body.datasource,
      enabled: body.enabled ?? true,
    });
    // create_rule wrote via daas-mcp (separate process); drop the cached
    // sql.js handle so the next render re-reads the file.
    invalidateDb('daas');
    return NextResponse.json({ ok: true, result });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}
