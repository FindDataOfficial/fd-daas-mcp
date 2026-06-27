// @ts-nocheck
import { getDashboardDb, getDb, getTableColumns, queryAll } from '@/lib/db';
import type { DatasourceColumnRow, DatasourceRow } from '@/lib/schema';
import { notFound } from 'next/navigation';

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ColumnsPage({ params }: Props) {
  const { id } = await params;
  const db = await getDashboardDb();

  const dsRow = queryAll(db, 'SELECT * FROM datasources WHERE id = ?', [Number(id)]);
  if (!dsRow.length) notFound();
  const ds = dsRow[0] as unknown as DatasourceRow;

  const columns = queryAll(
    db,
    'SELECT * FROM datasource_columns WHERE datasource_id = ? ORDER BY table_name, column_name',
    [Number(id)]
  ) as unknown as DatasourceColumnRow[];

  // Group by table
  const byTable = new Map<string, DatasourceColumnRow[]>();
  for (const c of columns) {
    if (!byTable.has(c.table_name)) byTable.set(c.table_name, []);
    byTable.get(c.table_name)!.push(c);
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 text-sm text-gray-500">
        <a href="/datasources" className="hover:text-blue-600">Datasources</a>
        <span>/</span>
        <span className="font-medium text-gray-900">{ds.name}</span>
        <span>/</span>
        <span>columns</span>
      </div>
      <h1 className="text-2xl font-bold mb-2">{ds.name}</h1>
      <p className="text-sm text-gray-500 mb-6">{ds.db_type} — {ds.connection_string}</p>

      {[...byTable.entries()].map(([table, cols]) => (
        <div key={table} className="mb-6">
          <h2 className="text-lg font-semibold mb-2">{table}</h2>
          <div className="border rounded-lg bg-white overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-100 text-left">
                <tr>
                  <th className="px-4 py-2">Column</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Source Field</th>
                  <th className="px-4 py-2">Unit</th>
                  <th className="px-4 py-2">Semantic</th>
                  <th className="px-4 py-2">PK</th>
                  <th className="px-4 py-2">Nullable</th>
                  <th className="px-4 py-2">Description</th>
                </tr>
              </thead>
              <tbody>
                {cols.map((c) => (
                  <tr key={c.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-xs">{c.column_name}</td>
                    <td className="px-4 py-2 text-xs">{c.column_type}</td>
                    <td className="px-4 py-2 text-xs font-mono text-blue-600">{c.source_field}</td>
                    <td className="px-4 py-2 text-xs">{c.unit}</td>
                    <td className="px-4 py-2 text-xs">{c.semantic_type}</td>
                    <td className="px-4 py-2">{c.is_primary_key ? '✓' : ''}</td>
                    <td className="px-4 py-2">{c.is_nullable ? '✓' : ''}</td>
                    <td className="px-4 py-2 text-gray-500">{c.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {columns.length === 0 && (
        <p className="text-gray-400">No columns defined. Add datasource columns to document the schema.</p>
      )}
    </div>
  );
}
