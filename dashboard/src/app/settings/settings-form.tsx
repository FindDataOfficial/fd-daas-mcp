'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface Props {
  scope: string;
  keyName: string;
  currentValue: string;
  category: string;
  description: string;
  existingId?: number;
  buttonLabel?: string;
}

export function SettingsForm({ scope, keyName, currentValue, category, description, existingId, buttonLabel }: Props) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(currentValue);
  const [saving, setSaving] = useState(false);
  const [restartMsg, setRestartMsg] = useState(false);
  const router = useRouter();

  const label = buttonLabel || 'Edit';

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setRestartMsg(false);

    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: existingId,
          scope,
          key: keyName,
          value,
          category,
          description,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        if (data.restartRequired) {
          setRestartMsg(true);
          router.refresh();
          // ponytail: keep modal open so user sees the restart warning
        } else {
          setOpen(false);
          router.refresh();
        }
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    if (!existingId) return;
    setSaving(true);
    try {
      await fetch(`/api/settings?id=${existingId}`, { method: 'DELETE' });
      setOpen(false);
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-blue-600 hover:underline text-xs"
      >
        {label}
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setOpen(false)}>
          <div className="bg-white rounded-lg shadow-xl p-6 w-96 max-w-[90vw]" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-2">
              {existingId ? 'Edit' : 'Set'} {scope === 'global' ? '' : scope + ' '}{keyName}
            </h3>
            <p className="text-xs text-gray-500 mb-4">{description}</p>

            <form onSubmit={handleSave}>
              <input
                type="text"
                value={value}
                onChange={e => setValue(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm font-mono mb-3"
                placeholder="Enter value (leave empty to unset)"
                autoFocus
              />

              <div className="flex gap-2 justify-end">
                {existingId && (
                  <button
                    type="button"
                    onClick={handleClear}
                    disabled={saving}
                    className="px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded"
                  >
                    Clear
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>

              {restartMsg && (
                <div className="mt-3">
                  <p className="text-xs text-amber-700 bg-amber-50 p-2 rounded mb-2">
                    Saved to .env. Restart required: all MCP servers + dashboard.
                  </p>
                  <button
                    type="button"
                    onClick={() => { setOpen(false); setRestartMsg(false); }}
                    className="px-3 py-1.5 text-xs bg-gray-200 rounded hover:bg-gray-300 w-full"
                  >
                    OK
                  </button>
                </div>
              )}
            </form>
          </div>
        </div>
      )}
    </>
  );
}
