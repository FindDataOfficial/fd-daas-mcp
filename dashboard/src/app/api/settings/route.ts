// @ts-nocheck
import { getDb, saveDb } from '@/lib/db';
import { NextRequest, NextResponse } from 'next/server';
import { syncKeyToEnv, removeKeyFromEnv } from '@/lib/env-sync';

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, scope, key, value, category, description } = body;

    if (!key || value === undefined) {
      return NextResponse.json({ error: 'key and value are required' }, { status: 400 });
    }

    const db = await getDb('daas');
    const effectiveScope = scope || 'global';
    const effectiveCategory = category || 'runtime';

    if (id) {
      // Update existing
      db.run(
        "UPDATE settings SET scope = ?, key = ?, value = ?, category = ?, description = ?, updated_at = datetime('now') WHERE id = ?",
        [effectiveScope, key, value, effectiveCategory, description || '', id]
      );
    } else {
      // Upsert by scope+key
      const existing = db.prepare(
        'SELECT id FROM settings WHERE scope = ? AND key = ?'
      );
      existing.bind([effectiveScope, key]);
      let existingId = null;
      if (existing.step()) {
        const row = existing.getAsObject();
        existingId = row.id;
      }
      existing.free();

      if (existingId) {
        db.run(
          "UPDATE settings SET value = ?, category = ?, description = ?, updated_at = datetime('now') WHERE id = ?",
          [value, effectiveCategory, description || '', existingId]
        );
      } else {
        db.run(
          "INSERT INTO settings (scope, key, value, category, description, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
          [effectiveScope, key, value, effectiveCategory, description || '']
        );
      }
    }

    saveDb('daas');

    // Sync every managed key through to the real .env file(s): globals → root
    // .env, per-MCP overrides → mcp/<scope>/.env. MCPs load .env only at
    // startup, so any change is restart-required.
    syncKeyToEnv(effectiveScope, key, value);

    return NextResponse.json({ ok: true, restartRequired: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json({ error: 'id query parameter is required' }, { status: 400 });
    }

    const db = await getDb('daas');

    // Read the row's scope + key before deleting so we can remove the matching
    // line from the relevant .env file.
    const stmt = db.prepare('SELECT scope, key FROM settings WHERE id = ?');
    stmt.bind([id]);
    let row: any = null;
    if (stmt.step()) row = stmt.getAsObject();
    stmt.free();

    db.run('DELETE FROM settings WHERE id = ?', [id]);
    saveDb('daas');

    if (row?.key) {
      removeKeyFromEnv(row.scope || 'global', row.key);
    }

    return NextResponse.json({ ok: true, restartRequired: !!row?.key });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
