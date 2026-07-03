'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface CollectionSummary {
  id: number;
  name: string;
  description: string | null;
}

interface Props {
  mode: 'create' | 'edit';
  collection?: CollectionSummary; // required for edit
  onClose: () => void;
}

/**
 * Modal dialog for creating or editing a datasource collection.
 * - create → POST /api/collections { name, description? }
 * - edit   → PATCH /api/collections/[name] { new_name?, description? }
 *           (only changed fields are sent; clearing the description sends "")
 */
export default function CollectionEditDialog({ mode, collection, onClose }: Props) {
  const router = useRouter();
  const [name, setName] = useState(mode === 'edit' && collection ? collection.name : '');
  const [description, setDescription] = useState(
    mode === 'edit' && collection ? collection.description ?? '' : '',
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Name is required');
      return;
    }
    setSaving(true);
    try {
      if (mode === 'create') {
        const body: Record<string, string> = { name: trimmedName };
        if (description.trim()) body.description = description.trim();
        const res = await fetch('/api/collections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const b = await res.json().catch(() => ({}));
          setError(b?.error ?? `HTTP ${res.status}`);
          return;
        }
      } else {
        if (!collection) return;
        const body: Record<string, string> = {};
        if (trimmedName !== collection.name) body.new_name = trimmedName;
        // Treat null and "" as equal so clearing-then-reverting is a no-op;
        // an actual clear ("x" → "") sends "" to PATCH.
        const cur = collection.description ?? '';
        if (description !== cur) body.description = description;
        if (Object.keys(body).length === 0) {
          onClose();
          return;
        }
        const res = await fetch(
          `/api/collections/${encodeURIComponent(collection.name)}`,
          {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          },
        );
        if (!res.ok) {
          const b = await res.json().catch(() => ({}));
          setError(b?.error ?? `HTTP ${res.status}`);
          return;
        }
      }
      onClose();
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  const title = mode === 'create' ? 'New collection' : `Edit “${collection?.name ?? ''}”`;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-lg shadow-xl w-full max-w-md p-4 flex flex-col gap-3"
      >
        <h3 className="text-sm font-semibold">{title}</h3>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-600">Name</span>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Collection name"
            className="text-sm border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-gray-600">Description (optional)</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this collection for?"
            rows={3}
            className="text-sm border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
          />
        </label>
        {error && (
          <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-gray-600 hover:underline px-2 py-1"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : mode === 'create' ? 'Create' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
}
