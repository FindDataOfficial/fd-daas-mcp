'use client';

import { useState } from 'react';

interface Props {
  name: string;
  initialScore: number | null;
  datasourceDefaultScore: number | null;
  effectiveDefaultScore: number | null;
}

function fmt(n: number | null): string {
  return n == null ? '' : String(n);
}

// Inline-editable indicator default score. Empty input = clear (inherit the
// datasource's sources.score). Shows the datasource default for reference and
// the resolved effective score (own score if set, else datasource default).
export default function IndicatorScoreInput({
  name,
  initialScore,
  datasourceDefaultScore,
  effectiveDefaultScore,
}: Props) {
  const [draft, setDraft] = useState<string>(fmt(initialScore));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<number | null>(initialScore);

  async function save() {
    setSaving(true);
    setError(null);
    const raw = draft.trim();
    const score = raw === '' ? null : Number(raw);
    if (raw !== '' && !Number.isFinite(score)) {
      setError(`"${raw}" is not a valid number`);
      setSaving(false);
      return;
    }
    const res = await fetch('/api/indicators/score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, score }),
    });
    const data = await res.json().catch(() => ({}));
    setSaving(false);
    if (!res.ok) {
      setError(data.error ?? `failed (${res.status})`);
      return;
    }
    setCurrent(data.score ?? null);
  }

  const effective =
    current != null ? current : effectiveDefaultScore != null ? effectiveDefaultScore : null;

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
      <div className="text-[10px] text-gray-400">
        ds default: <span className="font-mono">{fmt(datasourceDefaultScore) || '—'}</span>
        {' · '}
        effective: <span className="font-mono">{fmt(effective) || '—'}</span>
      </div>
      {error && <div className="text-[10px] text-red-600">{error}</div>}
    </div>
  );
}
