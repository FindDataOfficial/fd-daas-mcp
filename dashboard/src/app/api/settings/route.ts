// @ts-nocheck
import { getDb, saveDb } from '@/lib/db';
import { REPO_ROOT } from '@/lib/paths';
import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const ROOT_ENV = path.join(REPO_ROOT, '.env');

function syncToEnv(key: string, value: string) {
  let content = '';
  if (fs.existsSync(ROOT_ENV)) {
    content = fs.readFileSync(ROOT_ENV, 'utf-8');
  }

  const regex = new RegExp(`^${key}=.*$`, 'm');
  const line = `${key}=${value}`;

  if (regex.test(content)) {
    content = content.replace(regex, line);
  } else {
    content = content.trimEnd() + '\n' + line + '\n';
  }

  fs.writeFileSync(ROOT_ENV, content, 'utf-8');
}

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

    // Bootstrap vars: sync to root .env
    let restartRequired = false;
    if (effectiveCategory === 'bootstrap' && effectiveScope === 'global') {
      syncToEnv(key, value);
      restartRequired = true;
    }

    return NextResponse.json({ ok: true, restartRequired });
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
    db.run('DELETE FROM settings WHERE id = ?', [id]);
    saveDb('daas');

    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
