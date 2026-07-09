'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function NewIndicatorCollectionPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError('name is required');
      return;
    }
    setSaving(true);
    setError(null);
    const res = await fetch('/api/indicators/collections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: trimmed, description: description || undefined }),
    });
    const data = await res.json().catch(() => ({}));
    setSaving(false);
    if (!res.ok) {
      setError(data.error ?? `failed (${res.status})`);
      return;
    }
    router.push(`/process/indicators/collections/${encodeURIComponent(trimmed)}`);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">New Indicator Collection</h1>
        <Link
          href="/process/indicators/collections"
          className="text-sm text-gray-600 hover:underline"
        >
          ← Back
        </Link>
      </div>

      <form onSubmit={submit} className="max-w-lg space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="momentum"
            className="w-full px-3 py-2 border rounded text-sm"
            disabled={saving}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="RSI + momentum indicators"
            className="w-full px-3 py-2 border rounded text-sm"
            rows={3}
            disabled={saving}
          />
        </div>
        {error && <div className="text-sm text-red-600">{error}</div>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={saving}
            className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded"
          >
            {saving ? 'Creating…' : 'Create collection'}
          </button>
          <Link
            href="/process/indicators/collections"
            className="text-sm px-4 py-2 border rounded hover:bg-gray-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
