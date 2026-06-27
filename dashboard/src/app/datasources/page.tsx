// @ts-nocheck
import { getDb, queryAll, getTableColumns } from '@/lib/db';
import Link from 'next/link';

const DB_PATH = process.env.DAAS_DATABASE_URL?.replace('sqlite:///', '') || path.join(process.cwd(), '..', 'mcp', 'daas.db');

async function ensureSeed() {
  const db = await getDb('daas');
  const existing = queryAll(db, 'SELECT COUNT(*) as cnt FROM datasources');
  const cnt = Number(existing[0]?.cnt ?? 0);
  if (cnt > 0) return;

  // Only daas.db is the single source of truth now
  db.run('INSERT INTO datasources (name, db_type, connection_string, description, is_readonly) VALUES (?, ?, ?, ?, ?)',
    ['daas', 'sqlite', DB_PATH, 'Single DAAS database for all MCPs and dashboard', 1]);
  const result = queryAll(db, 'SELECT last_insert_rowid() as id');
  const dsId = result[0]?.id;
  const tables = queryAll(db, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
  for (const t of tables) {
    const tName = String(t.name);
    const cols = getTableColumns(db, tName);
    for (const c of cols) {
      db.run('INSERT OR IGNORE INTO datasource_columns (datasource_id, table_name, column_name, column_type, is_primary_key, is_nullable, description) VALUES (?, ?, ?, ?, ?, ?, ?)',
        [dsId, tName, c.name, c.type, c.pk, c.notnull ? 0 : 1, '']);
    }
  }
}

export default async function DatasourcesPage() {
  await ensureSeed();
  const db = await getDb('daas');
  const rows = queryAll(db, 'SELECT * FROM datasources ORDER BY name');

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Datasources</h1>
      </div>
      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Connection</th>
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((ds) => (
              <tr key={ds.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">{ds.name}</td>
                <td className="px-4 py-2">{ds.db_type}</td>
                <td className="px-4 py-2 font-mono text-xs max-w-xs truncate">{ds.connection_string}</td>
                <td className="px-4 py-2 text-gray-500">{ds.description}</td>
                <td className="px-4 py-2">
                  <Link href={`/datasources/${ds.id}/columns`} className="text-blue-600 hover:underline text-xs">
                    Columns
                  </Link>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No datasources yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
