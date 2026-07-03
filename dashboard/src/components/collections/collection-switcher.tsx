'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';

interface CollectionSummary {
  id: number;
  name: string;
  item_count: number;
}

interface Props {
  collections: CollectionSummary[];
  activeName: string | null;
}

export default function CollectionSwitcher({ collections, activeName }: Props) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState('');
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function go(toName: string) {
    router.push(`/collections/${encodeURIComponent(toName)}`);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = name.trim();
    if (!trimmed) return;
    const res = await fetch('/api/collections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: trimmed }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body?.error ?? `HTTP ${res.status}`);
      return;
    }
    setName('');
    setCreating(false);
    startTransition(() => {
      router.refresh();
      go(trimmed);
    });
  }

  async function handleRename(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!activeName) return;
    const trimmed = name.trim();
    if (!trimmed || trimmed === activeName) {
      setRenaming(false);
      return;
    }
    const res = await fetch(`/api/collections/${encodeURIComponent(activeName)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: trimmed }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body?.error ?? `HTTP ${res.status}`);
      return;
    }
    setRenaming(false);
    setName('');
    startTransition(() => {
      router.refresh();
      go(trimmed);
    });
  }

  async function handleDelete() {
    if (!activeName) return;
    if (!confirm(`Delete collection "${activeName}"? Its items will be removed (datasources themselves are untouched).`)) {
      return;
    }
    const res = await fetch(`/api/collections/${encodeURIComponent(activeName)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body?.error ?? `HTTP ${res.status}`);
      return;
    }
    startTransition(() => {
      router.push('/collections');
      router.refresh();
    });
  }

  return (
    <div className="border-b bg-white px-4 py-2 flex items-center gap-3 flex-wrap">
      <span className="text-xs uppercase tracking-wide text-gray-500">Collection</span>
      {creating ? (
        <form onSubmit={handleCreate} className="flex items-center gap-2 flex-1">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New collection name"
            className="text-sm border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button type="submit" disabled={pending} className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700">
            Create
          </button>
          <button type="button" onClick={() => { setCreating(false); setName(''); setError(null); }} className="text-xs text-gray-500 hover:underline">
            Cancel
          </button>
        </form>
      ) : renaming ? (
        <form onSubmit={handleRename} className="flex items-center gap-2 flex-1">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New name"
            className="text-sm border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button type="submit" disabled={pending} className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700">
            Rename
          </button>
          <button type="button" onClick={() => { setRenaming(false); setName(''); setError(null); }} className="text-xs text-gray-500 hover:underline">
            Cancel
          </button>
        </form>
      ) : (
        <>
          <select
            value={activeName ?? ''}
            onChange={(e) => {
              if (e.target.value) go(e.target.value);
              else router.push('/collections');
            }}
            className="text-sm border rounded px-2 py-1 max-w-xs"
          >
            <option value="">— pick a collection —</option>
            {collections.map((c) => (
              <option key={c.id} value={c.name}>
                {c.name} ({c.item_count})
              </option>
            ))}
          </select>
          <button onClick={() => { setCreating(true); setName(''); setError(null); }} className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700">
            + New
          </button>
          {activeName && (
            <>
              <button onClick={() => { setRenaming(true); setName(activeName); setError(null); }} className="text-xs text-gray-600 hover:underline">
                Rename
              </button>
              <button onClick={handleDelete} className="text-xs text-red-600 hover:underline">
                Delete
              </button>
            </>
          )}
        </>
      )}
      {error && (
        <span className="text-xs text-red-600 ml-auto">
          {error}
          <button onClick={() => setError(null)} className="ml-1 text-red-500 hover:text-red-700">×</button>
        </span>
      )}
    </div>
  );
}
