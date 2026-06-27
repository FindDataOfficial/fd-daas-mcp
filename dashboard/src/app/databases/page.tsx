// @ts-nocheck
import { getDb, listTables } from '@/lib/db';
import Link from 'next/link';
import type { DatabaseInfo } from '@/lib/schema';

const KNOWN_DBS = [
  { name: 'daas', readonly: true },
  { name: 'leader_mcp', readonly: true },
  { name: 'cron', readonly: false },
  { name: 'dashboard', readonly: false },
];

export default async function DatabasesPage() {
  const databases: (DatabaseInfo & { exists: boolean })[] = [];

  for (const { name, readonly } of KNOWN_DBS) {
    try {
      const db = await getDb(name);
      const tables = listTables(db);
      databases.push({ name, tables, readonly, exists: true });
    } catch {
      databases.push({ name, tables: [], readonly, exists: false });
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Databases</h1>
      <div className="grid gap-4">
        {databases.map((db) => (
          <div key={db.name} className="border rounded-lg bg-white p-4">
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-lg font-semibold">{db.name}.db</h2>
              {db.readonly && (
                <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">read-only</span>
              )}
              {!db.exists && (
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">not found</span>
              )}
            </div>
            {db.exists ? (
              <div className="flex flex-wrap gap-2">
                {db.tables.map((t) => (
                  <Link
                    key={t}
                    href={`/databases/${db.name}/${t}`}
                    className="px-3 py-1 bg-gray-100 hover:bg-blue-100 rounded text-sm"
                  >
                    {t}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">Database file not found at mcp/{db.name}.db</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
