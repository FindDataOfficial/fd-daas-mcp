// @ts-nocheck
import Link from 'next/link';
import { loadIndicatorCollections } from '@/lib/indicator-scores';

export const dynamic = 'force-dynamic';

export default async function IndicatorCollectionsPage() {
  let collections: any[] = [];
  let dbAvailable = true;
  try {
    collections = await loadIndicatorCollections();
  } catch {
    dbAvailable = false;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Indicator Collections</h1>
        <Link
          href="/process/indicators/collections/new"
          className="text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded"
        >
          New collection
        </Link>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Named groups of indicators — reusable bundles where each member can carry a per-collection
        score override. Effective score = item override → indicator default → datasource default.
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
              <th className="px-4 py-2">Items</th>
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2">Updated</th>
            </tr>
          </thead>
          <tbody>
            {collections.map((c) => (
              <tr key={c.id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">
                  <Link
                    href={`/process/indicators/collections/${encodeURIComponent(c.name)}`}
                    className="text-blue-600 hover:underline"
                  >
                    {c.name}
                  </Link>
                </td>
                <td className="px-4 py-2">{c.item_count}</td>
                <td className="px-4 py-2 text-gray-600">{c.description || '—'}</td>
                <td className="px-4 py-2 text-xs text-gray-500">{c.updated_at || c.created_at || '—'}</td>
              </tr>
            ))}
            {collections.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                  No indicator collections yet — click <span className="text-blue-600">New collection</span> to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
