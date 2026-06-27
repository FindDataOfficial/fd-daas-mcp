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
      "UPDATE tasks SET command = ?, description = ?, timeout = ?, updated_at = datetime('now') WHERE id = ?",
      [body.command ?? '', body.description ?? '', body.timeout ?? 60, id]
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
    const rows = db.prepare('SELECT name FROM tasks WHERE id = ?');
    rows.bind([id]);
    let taskName = '';
    if (rows.step()) taskName = rows.getAsObject().name;
    rows.free();

    if (taskName) {
      db.run('DELETE FROM schedules WHERE task_name = ?', [taskName]);
    }
    db.run('DELETE FROM tasks WHERE id = ?', [id]);
    saveDb('daas');
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
