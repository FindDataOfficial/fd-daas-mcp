'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import CollectionEditDialog from './collection-edit-dialog';
import type { DatasourceCollectionRow } from '@/lib/schema';

type Collection = DatasourceCollectionRow & { item_count: number };

interface Props {
  collections: Collection[];
}

type DialogTarget =
  | { mode: 'create' }
  | { mode: 'edit'; collection: Collection }
  | null;

/**
 * NotebookLM-style "notebooks home": a grid of every datasource collection
 * with create / rename / edit-description / delete actions, and a link into
 * each collection's three-pane workspace at /collections/[name].
 */
export default function CollectionManager({ collections }: Props) {
  const router = useRouter();
  const [dialog, setDialog] = useState<DialogTarget>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function handleDelete(c: Collection) {
    if (
      !confirm(
        `Delete collection “${c.name}”? Its items will be removed (datasources themselves are untouched).`,
      )
    ) {
      return;
    }
    setBusyId(c.id);
    setError(null);
    try {
      const res = await fetch(`/api/collections/${encodeURIComponent(c.name)}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        setError(b?.error ?? `HTTP ${res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="border-b bg-white px-4 py-3 flex items-center gap-3">
        <div className="flex-1">
          <h2 className="text-sm font-semibold">Datasource Collections</h2>
          <p className="text-xs text-gray-500">
            {collections.length} collection{collections.length === 1 ? '' : 's'}
          </p>
        </div>
        <button
          onClick={() => { setError(null); setDialog({ mode: 'create' }); }}
          className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
        >
          + New collection
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-xs text-red-700 flex items-start gap-2">
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">×</button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
        {collections.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="max-w-sm text-center">
              <h3 className="text-sm font-semibold mb-1">No collections yet</h3>
              <p className="text-xs text-gray-500 mb-3">
                Create your first datasource collection to group datasources and sections,
                then chat against them.
              </p>
              <button
                onClick={() => setDialog({ mode: 'create' })}
                className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
              >
                + New collection
              </button>
            </div>
          </div>
        ) : (
          <div
            className="grid gap-3"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}
          >
            {collections.map((c) => (
              <div key={c.id} className="bg-white border rounded-md shadow-sm flex flex-col">
                <div className="px-3 pt-3 pb-2 flex-1">
                  <div className="text-sm font-semibold truncate">{c.name}</div>
                  <div className="text-xs text-gray-600 mt-1 min-h-[2rem]">
                    {c.description ? (
                      <span className="line-clamp-2">{c.description}</span>
                    ) : (
                      <span className="text-gray-400 italic">No description</span>
                    )}
                  </div>
                </div>
                <div className="px-3 py-1.5 text-xs text-gray-500 flex items-center justify-between border-t bg-gray-50/50">
                  <span>{c.item_count} item{c.item_count === 1 ? '' : 's'}</span>
                  {c.updated_at && (
                    <span title={c.updated_at}>{formatDate(c.updated_at)}</span>
                  )}
                </div>
                <div className="px-3 py-2 border-t flex items-center gap-3">
                  <Link
                    href={`/collections/${encodeURIComponent(c.name)}`}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Open
                  </Link>
                  <button
                    onClick={() => { setError(null); setDialog({ mode: 'edit', collection: c }); }}
                    className="text-xs text-gray-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(c)}
                    disabled={busyId === c.id}
                    className="text-xs text-red-600 hover:underline ml-auto disabled:opacity-50"
                  >
                    {busyId === c.id ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {dialog && (
        <CollectionEditDialog
          mode={dialog.mode}
          collection={dialog.mode === 'edit' ? dialog.collection : undefined}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

function formatDate(s: string): string {
  if (!s) return '';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  // YYYY-MM-DD (UTC) — stable, no locale drift in SSR
  return d.toISOString().slice(0, 10);
}
