// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface Props {
  collectionName: string;
}

interface EntityHit {
  id: number;
  entity_type: string;
  code: string;
  name: string;
  ticker: string | null;
  exchange: string | null;
}

export default function MemberPicker({ collectionName }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<EntityHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<number | null>(null);
  const [error, setError] = useState('');

  async function runSearch(q: string) {
    setQuery(q);
    if (q.trim().length < 1) {
      setHits([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      // Reuse the sql.js read path via a GET to the items route is not available;
      // do the search server-side via the lib through a tiny RPC. We hit the
      // collection detail's search by querying /api/entities?q=... — but that
      // route doesn't exist. Instead, do a direct fetch to a search endpoint:
      const res = await fetch(`/api/entities/search?q=${encodeURIComponent(q)}`, { cache: 'no-store' });
      if (!res.ok) {
        setHits([]);
        return;
      }
      const data = await res.json();
      setHits(data.entities || []);
    } catch {
      setHits([]);
    } finally {
      setLoading(false);
    }
  }

  async function add(entityId: number) {
    setAdding(entityId);
    setError('');
    try {
      const res = await fetch(`/api/entities/${encodeURIComponent(collectionName)}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: entityId }),
      });
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (!res.ok) {
        setError(data.error || `Failed (${res.status})`);
      } else {
        setQuery('');
        setHits([]);
        router.refresh();
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setAdding(null);
    }
  }

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium mb-1">Add member</label>
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => runSearch(e.target.value)}
          placeholder="search by name, ticker, or code…"
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
      </div>
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      {loading && <p className="text-xs text-gray-400 mt-1">searching…</p>}
      {hits.length > 0 && (
        <ul className="border rounded mt-1 max-h-56 overflow-auto bg-white text-sm">
          {hits.map((h) => (
            <li
              key={h.id}
              className="flex items-center justify-between px-3 py-1.5 hover:bg-gray-50 border-b last:border-b-0"
            >
              <div>
                <span className="font-mono text-xs text-gray-500">{h.code}</span>{' '}
                <span className="font-medium">{h.name}</span>{' '}
                <span className="text-xs text-gray-400">
                  {h.exchange || h.entity_type}
                </span>
              </div>
              <button
                type="button"
                disabled={adding === h.id}
                onClick={() => add(h.id)}
                className="text-xs px-2 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {adding === h.id ? 'adding…' : 'add'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
