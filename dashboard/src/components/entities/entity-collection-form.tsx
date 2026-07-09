// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Props {
  mode: 'create' | 'edit';
  initial: {
    name: string;
    description: string;
    rule: string; // JSON string or ''
  };
}

export default function EntityCollectionForm({ mode, initial }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initial.name || '');
  const [description, setDescription] = useState(initial.description || '');
  const [rule, setRule] = useState(initial.rule || '');
  const [clearRule, setClearRule] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    // Validate rule JSON if provided.
    let ruleToSend: string | undefined = rule.trim();
    if (ruleToSend) {
      try {
        const parsed = JSON.parse(ruleToSend);
        if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
          setError('rule must be a JSON object');
          return;
        }
      } catch {
        setError('rule is not valid JSON');
        return;
      }
    } else {
      ruleToSend = undefined;
    }

    setSaving(true);
    try {
      if (mode === 'create') {
        const body: any = { name };
        if (description) body.description = description;
        if (ruleToSend) body.rule = ruleToSend;
        const res = await fetch('/api/entities', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        if (res.ok) {
          router.push(`/entities/${encodeURIComponent(name)}`);
          router.refresh();
        } else {
          setError(data.error || `Failed (${res.status})`);
        }
      } else {
        // edit
        const body: any = {};
        if (name && name !== initial.name) body.new_name = name;
        if (description !== (initial.description || '')) body.description = description;
        if (clearRule) body.clear_rule = true;
        else if (ruleToSend && ruleToSend !== (initial.rule || '')) body.rule = ruleToSend;
        if (Object.keys(body).length === 0) {
          setError('nothing to change');
          setSaving(false);
          return;
        }
        const res = await fetch(`/api/entities/${encodeURIComponent(initial.name)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        if (res.ok) {
          const targetName = body.new_name || initial.name;
          router.push(`/entities/${encodeURIComponent(targetName)}`);
          router.refresh();
        } else {
          setError(data.error || `Failed (${res.status})`);
        }
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded text-sm">{error}</div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="w-full border rounded px-3 py-2 text-sm font-mono"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Description (optional)</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full border rounded px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Membership rule (optional JSON)</label>
        <textarea
          value={rule}
          onChange={(e) => { setRule(e.target.value); setClearRule(false); }}
          rows={4}
          placeholder='e.g. {"entity_type":"stock","exchange":"SSE"}'
          className="w-full border rounded px-3 py-2 text-sm font-mono"
        />
        <p className="text-xs text-gray-400 mt-1">
          Keys (AND-combined): <code>entity_type</code>, <code>exchange</code>,{' '}
          <code>country_code</code>, <code>codes</code> (list), <code>name_regex</code>.
          When set, a scheduled sync re-derives members and records add-in / remove-out.
          Leave empty for a manual collection.
        </p>
        {mode === 'edit' && initial.rule && (
          <label className="flex items-center gap-2 text-sm mt-2">
            <input
              type="checkbox"
              checked={clearRule}
              onChange={(e) => { setClearRule(e.target.checked); if (e.target.checked) setRule(''); }}
            />
            clear rule (make this a manual collection)
          </label>
        )}
      </div>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : mode === 'create' ? 'Create collection' : 'Save changes'}
        </button>
        <Link
          href={mode === 'edit' ? `/entities/${encodeURIComponent(initial.name)}` : '/entities'}
          className="px-4 py-2 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
