'use client';

import { useState } from 'react';
import type {
  SourceScoreRow,
  CollectionScoreItem,
  DatasourceCollectionRow,
} from '@/lib/schema';

interface Props {
  sourceScores: SourceScoreRow[];
  collections: Pick<DatasourceCollectionRow, 'id' | 'name'>[];
  initialCollection: { id: number; name: string; items: CollectionScoreItem[] } | null;
}

interface CollectionDetail {
  id: number;
  name: string;
  items: CollectionScoreItem[];
}

function fmtScore(n: number | null): string {
  return n == null ? '—' : String(n);
}

export default function ScoresManager({
  sourceScores,
  collections,
  initialCollection,
}: Props) {
  const [sources, setSources] = useState<SourceScoreRow[]>(sourceScores);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [collection, setCollection] = useState<CollectionDetail | null>(
    initialCollection
      ? { id: initialCollection.id, name: initialCollection.name, items: initialCollection.items }
      : null,
  );
  const [itemDrafts, setItemDrafts] = useState<Record<number, string>>({});
  const [itemSaving, setItemSaving] = useState<number | null>(null);
  const [itemError, setItemError] = useState<string | null>(null);

  // ── Default score save ──────────────────────────────────────────
  async function saveSourceScore(name: string) {
    setSaving(name);
    setError(null);
    const raw = (drafts[name] ?? '').trim();
    // Empty input = clear (null); explicit number = set.
    const score = raw === '' ? null : Number(raw);
    if (raw !== '' && !Number.isFinite(score)) {
      setError(`"${raw}" is not a valid number`);
      setSaving(null);
      return;
    }
    const res = await fetch('/api/scores/source', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, score }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.error ?? `failed (${res.status})`);
      setSaving(null);
      return;
    }
    setSources((prev) =>
      prev.map((s) => (s.name === name ? { ...s, score: data.score ?? null } : s)),
    );
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
    // If the changed source is in the active collection, refresh its default too.
    if (collection?.items.some((it) => it.source_name === name)) {
      await refreshCollection(collection.name);
    }
    setSaving(null);
  }

  // ── Collection score save ───────────────────────────────────────
  async function pickCollection(name: string) {
    setItemError(null);
    const res = await fetch(`/api/scores/collection?name=${encodeURIComponent(name)}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setItemError(data.error ?? `failed (${res.status})`);
      return;
    }
    setCollection({ id: data.id, name: data.name, items: data.items });
    setItemDrafts({});
  }

  async function refreshCollection(name: string) {
    const res = await fetch(`/api/scores/collection?name=${encodeURIComponent(name)}`);
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      setCollection({ id: data.id, name: data.name, items: data.items });
    }
  }

  async function saveItemScore(itemId: number) {
    if (!collection) return;
    const item = collection.items.find((i) => i.item_id === itemId);
    if (!item) return;
    setItemSaving(itemId);
    setItemError(null);
    const raw = (itemDrafts[itemId] ?? '').trim();
    const score = raw === '' ? null : Number(raw);
    if (raw !== '' && !Number.isFinite(score)) {
      setItemError(`"${raw}" is not a valid number`);
      setItemSaving(null);
      return;
    }
    const res = await fetch('/api/scores/item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection_name: collection.name,
        source_name: item.source_name,
        section_name: item.section_name,
        score,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setItemError(data.error ?? `failed (${res.status})`);
      setItemSaving(null);
      return;
    }
    setCollection((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.map((it) =>
              it.item_id === itemId
                ? {
                    ...it,
                    item_score: data.item_score ?? null,
                    score: data.score ?? null,
                  }
                : it,
            ),
          }
        : prev,
    );
    setItemDrafts((prev) => {
      const next = { ...prev };
      delete next[itemId];
      return next;
    });
    setItemSaving(null);
  }

  return (
    <div className="p-6 space-y-10">
      <header>
        <h1 className="text-2xl font-bold">Scores</h1>
        <p className="text-sm text-gray-600 mt-1">
          Manage a default priority/quality weight for each datasource, and an
          optional per-collection override. An override wins over the default;
          leave blank to clear (inherit the default).
        </p>
      </header>

      {/* ── Default scores ─────────────────────────────────────── */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Default scores</h2>
        {error && (
          <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </div>
        )}
        <div className="border rounded-lg bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Label</th>
                <th className="px-3 py-2 w-40">Default score</th>
                <th className="px-3 py-2 w-24"></th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => {
                const val =
                  drafts[s.name] ?? (s.score == null ? '' : String(s.score));
                return (
                  <tr key={s.name} className="border-t">
                    <td className="px-3 py-2 font-mono">{s.name}</td>
                    <td className="px-3 py-2 text-gray-700">{s.label}</td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        step="any"
                        value={val}
                        placeholder="—"
                        onChange={(e) =>
                          setDrafts((p) => ({ ...p, [s.name]: e.target.value }))
                        }
                        className="w-32 border rounded px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <button
                        disabled={saving === s.name}
                        onClick={() => saveSourceScore(s.name)}
                        className="px-3 py-1 text-xs rounded bg-blue-600 text-white disabled:opacity-50"
                      >
                        {saving === s.name ? 'Saving…' : 'Save'}
                      </button>
                    </td>
                  </tr>
                );
              })}
              {sources.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-4 text-center text-gray-500">
                    No datasources.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Collection scores ──────────────────────────────────── */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Collection scores</h2>
        {itemError && (
          <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            {itemError}
          </div>
        )}
        <div className="mb-4 flex items-center gap-3">
          <label className="text-sm text-gray-700">Collection:</label>
          <select
            value={collection?.name ?? ''}
            onChange={(e) => pickCollection(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          >
            {collections.length === 0 && <option value="">(no collections)</option>}
            {collections.map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {collection && (
          <div className="border rounded-lg bg-white overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-100 text-left">
                <tr>
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Section</th>
                  <th className="px-3 py-2 w-32">Default</th>
                  <th className="px-3 py-2 w-40">Override</th>
                  <th className="px-3 py-2 w-24">Resolved</th>
                  <th className="px-3 py-2 w-24"></th>
                </tr>
              </thead>
              <tbody>
                {collection.items.map((it) => {
                  const val =
                    itemDrafts[it.item_id] ??
                    (it.item_score == null ? '' : String(it.item_score));
                  const overriding = it.item_score != null;
                  return (
                    <tr key={it.item_id} className="border-t">
                      <td className="px-3 py-2 font-mono">{it.source_name}</td>
                      <td className="px-3 py-2 text-gray-700">
                        {it.section_name ?? <span className="text-gray-400">(whole)</span>}
                      </td>
                      <td className="px-3 py-2 text-gray-500">
                        {fmtScore(it.source_default_score)}
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          step="any"
                          value={val}
                          placeholder="—"
                          onChange={(e) =>
                            setItemDrafts((p) => ({
                              ...p,
                              [it.item_id]: e.target.value,
                            }))
                          }
                          className="w-32 border rounded px-2 py-1 text-sm"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`font-mono ${
                            overriding ? 'text-blue-700 font-semibold' : 'text-gray-600'
                          }`}
                        >
                          {fmtScore(it.score)}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <button
                          disabled={itemSaving === it.item_id}
                          onClick={() => saveItemScore(it.item_id)}
                          className="px-3 py-1 text-xs rounded bg-blue-600 text-white disabled:opacity-50"
                        >
                          {itemSaving === it.item_id ? 'Saving…' : 'Save'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {collection.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-4 text-center text-gray-500">
                      This collection has no items.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <p className="px-3 py-2 text-xs text-gray-500 border-t bg-gray-50">
              Override wins over default. Leave the override field blank to clear
              it (inherit the default). &ldquo;Resolved&rdquo; is what consumers
              will see.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
