// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface Props {
  /** 'rules' or 'indicators' — selects the API path. */
  kind: 'rules' | 'indicators';
  name: string;
  enabled: boolean;
}

export default function EnabledToggle({ kind, name, enabled }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function handleToggle() {
    setBusy(true);
    setError('');
    try {
      const res = await fetch(`/api/process/${kind}/${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle' }),
      });
      if (res.ok) {
        router.refresh();
      } else {
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={handleToggle}
        disabled={busy}
        className={`text-xs px-2 py-0.5 rounded ${
          enabled
            ? 'bg-green-100 text-green-800 hover:bg-green-200'
            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
        } disabled:opacity-50`}
        title={enabled ? 'Click to disable' : 'Click to enable'}
      >
        {busy ? '…' : enabled ? 'on' : 'off'}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}
