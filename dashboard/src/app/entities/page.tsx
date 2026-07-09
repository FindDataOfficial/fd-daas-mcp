// @ts-nocheck
import Link from 'next/link';
import { loadEntityCollections } from '@/lib/entity-collections';

export const dynamic = 'force-dynamic';

export default async function EntitiesHomePage() {
  let collections: any[] = [];
  let dbAvailable = true;
  try {
    collections = await loadEntityCollections();
  } catch {
    dbAvailable = false;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Entity Collections</h1>
        <Link
          href="/entities/new"
          className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded"
        >
          New collection
        </Link>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Named groups of entities (stocks + countries) — watchlists / portfolios.
        Every add and remove is recorded in an add-in / remove-out audit log.
      </p>

      {!dbAvailable && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded text-sm mb-4">
          daas.db not reachable — create it by starting daas-mcp once.
        </div>
      )}

      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Members</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {collections.map((c) => (
              <tr key={c.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">
                  <Link
                    href={`/entities/${encodeURIComponent(c.name)}`}
                    className="text-blue-600 hover:underline"
                  >
                    {c.name}
                  </Link>
                </td>
                <td className="px-4 py-2">{c.item_count}</td>
                <td className="px-4 py-2 text-xs">
                  {c.rule ? (
                    <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">rule-based</span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">manual</span>
                  )}
                </td>
                <td className="px-4 py-2 text-gray-600">{c.description || '—'}</td>
                <td className="px-4 py-2 text-xs text-gray-500">{c.updated_at || c.created_at || '—'}</td>
              </tr>
            ))}
            {collections.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  No entity collections yet — click <span className="text-blue-600">New collection</span> to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
