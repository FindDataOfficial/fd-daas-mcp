// @ts-nocheck
'use client';

import { useState } from 'react';

interface Props {
  /** Initial root .env contents (read server-side). */
  initialContent: string;
}

export default function EnvEditor({ initialContent }: Props) {
  const [content, setContent] = useState(initialContent);
  const [saving, setSaving] = useState(false);
  const [restartMsg, setRestartMsg] = useState(false);
  const [error, setError] = useState('');
  const [savedAt, setSavedAt] = useState('');

  async function handleSave() {
    setSaving(true);
    setError('');
    setRestartMsg(false);
    try {
      const res = await fetch('/api/settings/env', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const data = await res.json();
      if (res.ok) {
        setRestartMsg(true);
        setSavedAt(new Date().toLocaleTimeString());
      } else {
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    setSaving(true);
    setError('');
    try {
      const res = await fetch('/api/settings/env');
      const data = await res.json();
      if (res.ok) {
        setContent(data.content || '');
        setRestartMsg(false);
      } else {
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Network error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded text-sm mb-3">
        Saving here overwrites dashboard-managed lines. The structured table above re-syncs
        managed lines on its next save. MCPs load <code>.env</code> only at startup — restart
        affected services for changes to take effect.
      </div>

      {restartMsg && (
        <div className="bg-amber-100 border border-amber-300 text-amber-900 px-4 py-2 rounded text-sm mb-3">
          Saved. <strong>Restart MCPs</strong> for changes to take effect. {savedAt && `(at ${savedAt})`}
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded text-sm mb-3">
          {error}
        </div>
      )}

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={24}
        className="w-full border rounded px-3 py-2 text-xs font-mono"
        spellCheck={false}
      />

      <div className="flex gap-2 mt-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onClick={handleReset}
          disabled={saving}
          className="px-4 py-2 rounded text-sm font-medium bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
        >
          Reset from disk
        </button>
      </div>
    </div>
  );
}
