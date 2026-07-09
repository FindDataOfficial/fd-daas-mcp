'use client';

import { useState } from 'react';
import type {
  IndicatorCollectionDetail,
  IndicatorCollectionScoreItem,
  IndicatorCollectionChangeRow,
} from '@/lib/schema';

interface Props {
  collection: IndicatorCollectionDetail;
  initialHistory: IndicatorCollectionChangeRow[];
  indicatorNames: { id: number; name: string }[];
}

function fmt(n: number | null): string {
  return n == null ? '—' : String(n);
}

export default function IndicatorCollectionDetail({
  collection,
  initialHistory,
  indicatorNames,
}: Props) {
  const [items, setItems] = useState<IndicatorCollectionScoreItem[]>(collection.items);
  const [history, setHistory] = useState<IndicatorCollectionChangeRow[]>(initialHistory);
  const [historyFilter, setHistoryFilter] = useState<'all' | 'add_in' | 'remove_out'>('all');
  const [addName, setAddName] = useState('');
  const [addScore, setAddScore] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    // Re-fetch the detail + history via the read API (GET collections list +
    // GET detail through the same sql.js path). Simplest: reload the page.
    window.location.reload();
  }

  async function addItem(e: React.FormEvent) {
    e.preventDefault();
    const indicator_name = addName.trim();
    if (!indicator_name) return;
    setBusy(true);
    setError(null);
    const args: { indicator_name: string; score?: number } = { indicator_name };
    if (addScore.trim() !== '') args.score = Number(addScore);
    const res = await fetch(
      `/api/indicators/collections/${encodeURIComponent(collection.name)}/items`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      },
    );
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) {
      setError(data.error ?? `failed (${res.status})`);
      return;
    }
    setAddName('');
    setAddScore('');
    refresh();
  }

  async function removeItem(indicator_name: string) {
    if (!confirm(`Remove "${indicator_name}" from ${collection.name}?`)) return;
    const res = await fetch(
      `/api/indicators/collections/${encodeURIComponent(collection.name)}/items`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ indicator_name }),
      },
    );
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      setError(d.error ?? `failed (${res.status})`);
      return;
    }
    refresh();
  }

  async function move(indicator_name: string, dir: -1 | 1) {
    const ordered = items.map((it) => it.item_id);
    const idx = items.findIndex((it) => it.indicator_name === indicator_name);
    const target = idx + dir;
    if (idx < 0 || target < 0 || target >= ordered.length) return;
    [ordered[idx], ordered[target]] = [ordered[target], ordered[idx]];
    setBusy(true);
    const res = await fetch(
      `/api/indicators/collections/${encodeURIComponent(collection.name)}/items`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ordered_item_ids: ordered }),
      },
    );
    setBusy(false);
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      setError(d.error ?? `failed (${res.status})`);
      return;
    }
    // Optimistic local reorder of the displayed items.
    const next = [...items];
    [next[idx], next[target]] = [next[target], next[idx]];
    next.forEach((it, i) => (it.sort_order = i));
    setItems(next);
  }

  async function deleteCollection() {
    if (!confirm(`Delete collection "${collection.name}"? This cascades to its items + history.`)) return;
    const res = await fetch(
      `/api/indicators/collections/${encodeURIComponent(collection.name)}`,
      { method: 'DELETE' },
    );
    if (res.ok) {
      window.location.href = '/process/indicators/collections';
    } else {
      const d = await res.json().catch(() => ({}));
      setError(d.error ?? `failed (${res.status})`);
    }
  }

  const availableNames = indicatorNames
    .map((n) => n.name)
    .filter((n) => !items.some((it) => it.indicator_name === n));

  const filteredHistory =
    historyFilter === 'all'
      ? history
      : history.filter((h) => h.action === historyFilter);

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded text-sm">
          {error}
        </div>
      )}

      {/* Items table */}
      <div className="border rounded-lg bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="px-4 py-2 w-8"></th>
              <th className="px-4 py-2">Indicator</th>
              <th className="px-4 py-2">Item score</th>
              <th className="px-4 py-2 text-xs text-gray-500">Indicator default</th>
              <th className="px-4 py-2 text-xs text-gray-500">Datasource default</th>
              <th className="px-4 py-2">Effective</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={it.item_id} className="border-t hover:bg-gray-50">
                <td className="px-4 py-2 text-xs text-gray-400">
                  <div className="flex flex-col">
                    <button
                      type="button"
                      disabled={busy || i === 0}
                      onClick={() => move(it.indicator_name, -1)}
                      className="hover:text-gray-700 disabled:opacity-30"
                      title="Move up"
                    >▲</button>
                    <button
                      type="button"
                      disabled={busy || i === items.length - 1}
                      onClick={() => move(it.indicator_name, 1)}
                      className="hover:text-gray-700 disabled:opacity-30"
                      title="Move down"
                    >▼</button>
                  </div>
                </td>
                <td className="px-4 py-2 font-medium">{it.indicator_name}</td>
                <td className="px-4 py-2">
                  <ItemScoreInput
                    collectionName={collection.name}
                    itemName={it.indicator_name}
                    initialScore={it.item_score}
                    indicatorDefault={it.indicator_default_score}
                    sourceDefault={it.source_default_score}
                  />
                </td>
                <td className="px-4 py-2 text-xs text-gray-500 font-mono">{fmt(it.indicator_default_score)}</td>
                <td className="px-4 py-2 text-xs text-gray-500 font-mono">{fmt(it.source_default_score)}</td>
                <td className="px-4 py-2 font-mono">{fmt(it.score)}</td>
                <td className="px-4 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => removeItem(it.indicator_name)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No indicators in this collection yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Add indicator */}
      <div className="border rounded-lg bg-white p-4">
        <h3 className="text-sm font-medium mb-2">Add indicator</h3>
        <form onSubmit={addItem} className="flex items-end gap-2 flex-wrap">
          <div className="flex flex-col">
            <label className="text-xs text-gray-500 mb-1">Indicator</label>
            <select
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              className="px-2 py-1.5 border rounded text-sm"
              disabled={busy || availableNames.length === 0}
            >
              <option value="">— pick an indicator —</option>
              {availableNames.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-xs text-gray-500 mb-1">Score (optional)</label>
            <input
              type="number"
              step="any"
              value={addScore}
              onChange={(e) => setAddScore(e.target.value)}
              placeholder="inherit"
              className="w-28 px-2 py-1.5 border rounded text-sm"
              disabled={busy}
            />
          </div>
          <button
            type="submit"
            disabled={busy || !addName}
            className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-1.5 rounded"
          >
            Add
          </button>
        </form>
        {availableNames.length === 0 && indicatorNames.length > 0 && (
          <p className="text-xs text-gray-400 mt-2">All indicators are already in this collection.</p>
        )}
        {indicatorNames.length === 0 && (
          <p className="text-xs text-gray-400 mt-2">No indicator rules exist yet — create one first.</p>
        )}
      </div>

      {/* History */}
      <div className="border rounded-lg bg-white p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">History (add-in / remove-out)</h3>
          <div className="flex gap-1 text-xs">
            {(['all', 'add_in', 'remove_out'] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setHistoryFilter(f)}
                className={`px-2 py-0.5 rounded ${historyFilter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}
              >
                {f === 'all' ? 'all' : f === 'add_in' ? 'add_in' : 'remove_out'}
              </button>
            ))}
          </div>
        </div>
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-gray-500 sticky top-0 bg-white">
              <tr>
                <th className="px-2 py-1">When</th>
                <th className="px-2 py-1">Action</th>
                <th className="px-2 py-1">Indicator</th>
                <th className="px-2 py-1">Source</th>
                <th className="px-2 py-1">Reason</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((h) => (
                <tr key={h.id} className="border-t">
                  <td className="px-2 py-1 text-gray-400">{h.changed_at ?? '—'}</td>
                  <td className="px-2 py-1">
                    <span className={`px-1.5 py-0.5 rounded ${h.action === 'add_in' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {h.action}
                    </span>
                  </td>
                  <td className="px-2 py-1 font-mono">{h.indicator_name}</td>
                  <td className="px-2 py-1 text-gray-500">{h.source}</td>
                  <td className="px-2 py-1 text-gray-500">{h.reason || '—'}</td>
                </tr>
              ))}
              {filteredHistory.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-2 py-6 text-center text-gray-400">No history.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border-t pt-4">
        <button
          type="button"
          onClick={deleteCollection}
          className="text-sm text-red-600 hover:underline"
        >
          Delete this collection
        </button>
      </div>
    </div>
  );
}

// Inline-editable per-item score override. Empty = clear (inherit the
// indicator's default score).
function ItemScoreInput({
  collectionName,
  itemName,
  initialScore,
  indicatorDefault,
  sourceDefault,
}: {
  collectionName: string;
  itemName: string;
  initialScore: number | null;
  indicatorDefault: number | null;
  sourceDefault: number | null;
}) {
  const [draft, setDraft] = useState<string>(initialScore == null ? '' : String(initialScore));
  const [saving, setSaving] = useState(false);
  const [current, setCurrent] = useState<number | null>(initialScore);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setErr(null);
    const raw = draft.trim();
    const score = raw === '' ? null : Number(raw);
    if (raw !== '' && !Number.isFinite(score)) {
      setErr(`"${raw}" is not a valid number`);
      setSaving(false);
      return;
    }
    const res = await fetch(
      `/api/indicators/collections/${encodeURIComponent(collectionName)}/items/${encodeURIComponent(itemName)}/score`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ score }),
      },
    );
    const data = await res.json().catch(() => ({}));
    setSaving(false);
    if (!res.ok) {
      setErr(data.error ?? `failed (${res.status})`);
      return;
    }
    setCurrent(data.item_score ?? null);
  }

  const effective =
    current != null ? current : indicatorDefault != null ? indicatorDefault : sourceDefault;

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-1">
        <input
          type="number"
          step="any"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="—"
          className="w-20 px-1.5 py-0.5 text-xs border rounded font-mono"
          disabled={saving}
        />
        <button
          onClick={save}
          disabled={saving}
          className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-2 py-0.5 rounded"
        >
          {saving ? '…' : 'Save'}
        </button>
      </div>
      {err && <div className="text-[10px] text-red-600">{err}</div>}
      <div className="text-[10px] text-gray-400">
        effective: <span className="font-mono">{fmt(effective)}</span>
      </div>
    </div>
  );
}
