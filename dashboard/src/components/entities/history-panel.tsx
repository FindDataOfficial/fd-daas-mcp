// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface ChangeRow {
  id: number;
  collection_name: string | null;
  entity_id: number | null;
  entity_code: string | null;
  entity_name: string | null;
  action: 'add_in' | 'remove_out';
  source: 'manual' | 'cron';
  reason: string | null;
  changed_at: string | null;
}

interface Props {
  collectionName: string;
  initialChanges: ChangeRow[];
}

export default function HistoryPanel({ collectionName, initialChanges }: Props) {
  const router = useRouter();
  const [filter, setFilter] = useState<'all' | 'add_in' | 'remove_out'>('all');
  const [changes, setChanges] = useState<ChangeRow[]>(initialChanges);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function applyFilter(f: 'all' | 'add_in' | 'remove_out') {
    setFilter(f);
    setLoading(true);
    setError('');
    try {
      const qs = f === 'all' ? '' : `?action=${f}`;
      const res = await fetch(
        `/api/entities/${encodeURIComponent(collectionName)}/history${qs}`,
        { cache: 'no-store' },
      );
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (res.ok) {
        setChanges(data.changes || []);
      } else {
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold">History</h2>
        <div className="flex gap-1 text-xs">
          {(['all', 'add_in', 'remove_out'] as const).map((f) => (
            <button
              key={f}
              type="button"
              disabled={loading}
              onClick={() => applyFilter(f)}
              className={`px-2 py-1 rounded ${
                filter === f ? 'bg-gray-800 text-white' : 'bg-gray-100 hover:bg-gray-200'
              }`}
            >
              {f === 'all' ? 'all' : f === 'add_in' ? 'add-in' : 'remove-out'}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-xs text-red-600 mb-1">{error}</p>}
      <div className="border rounded bg-white max-h-80 overflow-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 text-left sticky top-0">
            <tr>
              <th className="px-3 py-1.5">When</th>
              <th className="px-3 py-1.5">Entity</th>
              <th className="px-3 py-1.5">Action</th>
              <th className="px-3 py-1.5">Source</th>
              <th className="px-3 py-1.5">Reason</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((c) => (
              <tr key={c.id} className="border-t">
                <td className="px-3 py-1.5 text-gray-500 whitespace-nowrap">
                  {c.changed_at || '—'}
                </td>
                <td className="px-3 py-1.5">
                  <span className="font-mono text-gray-500">{c.entity_code || '—'}</span>{' '}
                  {c.entity_name || ''}
                </td>
                <td className="px-3 py-1.5">
                  <span
                    className={`px-1.5 py-0.5 rounded ${
                      c.action === 'add_in'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {c.action === 'add_in' ? 'add-in' : 'remove-out'}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-gray-500">{c.source}</td>
                <td className="px-3 py-1.5 text-gray-600">{c.reason || '—'}</td>
              </tr>
            ))}
            {changes.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-gray-400">
                  No changes recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
