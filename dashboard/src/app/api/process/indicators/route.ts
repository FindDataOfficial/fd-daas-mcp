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
  if (!body.name || !body.datasource || !body.source_table || !body.date_column || !body.value_column || !body.op) {
    return NextResponse.json(
      { error: 'name, datasource, source_table, date_column, value_column, and op are required' },
      { status: 400 },
    );
  }

  try {
    const result = await callTool('daas-mcp', 'create_indicator', {
      name: body.name,
      datasource: body.datasource,
      source_table: body.source_table,
      date_column: body.date_column,
      value_column: body.value_column,
      op: body.op,
      params: body.params,
      function_name: body.function_name,
      indicator_name: body.indicator_name,
      enabled: body.enabled ?? true,
    });
    invalidateDb('daas');
    return NextResponse.json({ ok: true, result });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ?? String(e) },
      { status: 500 },
    );
  }
}
