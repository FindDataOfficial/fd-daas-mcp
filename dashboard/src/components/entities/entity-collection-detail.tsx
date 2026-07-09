// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import MemberPicker from './member-picker';
import HistoryPanel from './history-panel';

interface Member {
  item_id: number;
  entity_id: number;
  sort_order: number;
  added_at: string | null;
  added_reason: string | null;
  entity_type: string | null;
  code: string | null;
  name: string | null;
  ticker: string | null;
  exchange: string | null;
  country_code: string | null;
}

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
  collection: {
    id: number;
    name: string;
    description: string | null;
    rule: Record<string, any> | null;
    created_at: string | null;
    updated_at: string | null;
    members: Member[];
  };
  initialHistory: ChangeRow[];
}

export default function EntityCollectionDetail({ collection, initialHistory }: Props) {
  const router = useRouter();
  const [removing, setRemoving] = useState<number | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [syncSummary, setSyncSummary] = useState<string | null>(null);

  async function removeMember(m: Member) {
    if (!confirm(`Remove ${m.name} (${m.code}) from this collection?`)) return;
    setRemoving(m.entity_id);
    setError('');
    try {
      const res = await fetch(`/api/entities/${encodeURIComponent(collection.name)}/items`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_id: m.entity_id, reason: 'manual remove' }),
      });
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (!res.ok) {
        setError(data.error || `Failed (${res.status})`);
      } else {
        router.refresh();
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setRemoving(null);
    }
  }

  async function syncNow() {
    setSyncing(true);
    setError('');
    setSyncSummary(null);
    try {
      const res = await fetch(`/api/entities/${encodeURIComponent(collection.name)}/sync`, {
        method: 'POST',
      });
      const data = await res.json().catch(() => ({ error: 'Request failed' }));
      if (!res.ok) {
        setError(data.error || `Failed (${res.status})`);
      } else {
        const a = (data.added || []).length;
        const r = (data.removed || []).length;
        const u = data.unchanged ?? 0;
        setSyncSummary(`synced: +${a} added, −${r} removed, ${u} unchanged`);
        router.refresh();
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setSyncing(false);
    }
  }

  async function deleteCollection() {
    if (!confirm(`Delete collection "${collection.name}"? This removes all members and history.`)) return;
    setDeleting(true);
    setError('');
    try {
      const res = await fetch(`/api/entities/${encodeURIComponent(collection.name)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        router.push('/entities');
        router.refresh();
      } else {
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setDeleting(false);
    }
  }

  const isRuleBased = !!collection.rule;

  return (
    <div>
      <Link href="/entities" className="text-blue-600 hover:underline text-sm mb-2 inline-block">
        ← Back to entity collections
      </Link>

      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">{collection.name}</h1>
          <p className="text-sm text-gray-500">
            {collection.description || 'no description'}
          </p>
          <div className="text-xs text-gray-400 mt-1">
            {isRuleBased ? (
              <span>
                rule-based ·{' '}
                <code className="font-mono">{JSON.stringify(collection.rule)}</code>
              </span>
            ) : (
              <span>manual collection</span>
            )}
            {' · '}updated {collection.updated_at || collection.created_at || '—'}
          </div>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/entities/${encodeURIComponent(collection.name)}/edit`}
            className="text-sm px-3 py-1.5 rounded bg-gray-100 hover:bg-gray-200"
          >
            Edit
          </Link>
          {isRuleBased && (
            <button
              type="button"
              disabled={syncing}
              onClick={syncNow}
              className="text-sm px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {syncing ? 'Syncing…' : 'Sync now'}
            </button>
          )}
          <button
            type="button"
            disabled={deleting}
            onClick={deleteCollection}
            className="text-sm px-3 py-1.5 rounded bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded text-sm mb-4">
          {error}
        </div>
      )}
      {syncSummary && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-2 rounded text-sm mb-4">
          {syncSummary}
        </div>
      )}

      <MemberPicker collectionName={collection.name} />

      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2">Code</th>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Exchange</th>
              <th className="px-4 py-2">Added</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {collection.members.map((m) => (
              <tr key={m.item_id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-xs">{m.code}</td>
                <td className="px-4 py-2 font-medium">{m.name}</td>
                <td className="px-4 py-2 text-xs text-gray-600">{m.entity_type}</td>
                <td className="px-4 py-2 text-xs text-gray-600">{m.exchange || '—'}</td>
                <td className="px-4 py-2 text-xs text-gray-500">{m.added_at || '—'}</td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    disabled={removing === m.entity_id}
                    onClick={() => removeMember(m)}
                    className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50"
                  >
                    {removing === m.entity_id ? 'removing…' : 'remove'}
                  </button>
                </td>
              </tr>
            ))}
            {collection.members.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No members yet. Add one above{isRuleBased ? ' or click "Sync now"' : ''}.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <HistoryPanel collectionName={collection.name} initialChanges={initialHistory} />
    </div>
  );
}
