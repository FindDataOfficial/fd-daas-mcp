// @ts-nocheck
// Schema managed by mcp/models/models.py.
import { getDb, queryAll, getTableColumns } from '@/lib/db';
import path from 'path';

const DB_PATH = process.env.DAAS_DATABASE_URL?.replace('sqlite:///', '')
  || path.join(process.cwd(), '..', 'mcp', 'daas.db');

export async function seedDatasources() {
  const db = await getDb('daas');

  const existing = queryAll(db, 'SELECT COUNT(*) as cnt FROM datasources');
  const cnt = Number(existing[0]?.cnt ?? 0);
  if (cnt > 0) return;

  const sources = [
    { name: 'daas', db_type: 'sqlite', connection: DB_PATH, description: 'Main DAAS database', readonly: 1 },
  ];

  for (const s of sources) {
    db.run(
      'INSERT INTO datasources (name, db_type, connection_string, description, is_readonly) VALUES (?, ?, ?, ?, ?)',
      [s.name, s.db_type, s.connection, s.description, s.readonly]
    );
    const result = queryAll(db, 'SELECT last_insert_rowid() as id');
    const dsId = result[0]?.id;

    // Scan tables in daas.db and populate column metadata
    const tables = queryAll(db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
    for (const t of tables) {
      const tName = String(t.name);
      const cols = getTableColumns(db, tName);
      for (const c of cols) {
        db.run(
          'INSERT OR IGNORE INTO datasource_columns (datasource_id, table_name, column_name, column_type, is_primary_key, is_nullable, description) VALUES (?, ?, ?, ?, ?, ?, ?)',
          [dsId, tName, c.name, c.type, c.pk, c.notnull ? 0 : 1, '']
        );
      }
    }
  }
}
