import { getDb, saveDb } from '@/lib/db';
import { NextRequest, NextResponse } from 'next/server';

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();

  try {
    const db = await getDb('daas');
    db.run(
      "UPDATE schedules SET cron_expr = ?, enabled = ?, timezone = ?, updated_at = datetime('now') WHERE id = ?",
      [body.cron_expr ?? '', body.enabled ?? 1, body.timezone ?? 'UTC', id]
    );
    saveDb('daas');
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const db = await getDb('daas');
    db.run('DELETE FROM executions WHERE schedule_id = ?', [id]);
    db.run('DELETE FROM schedules WHERE id = ?', [id]);
    saveDb('daas');
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
