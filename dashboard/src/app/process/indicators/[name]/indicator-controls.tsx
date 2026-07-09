// @ts-nocheck
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Props {
  indicatorName: string;
  enabled: boolean;
}

export default function IndicatorControls({ indicatorName, enabled }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  async function postAction(action: string) {
    setBusy(action);
    setError('');
    try {
      const res = await fetch(`/api/process/indicators/${encodeURIComponent(indicatorName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        if (action === 'delete') {
          router.push('/process/indicators');
        } else {
          router.refresh();
        }
      } else {
        const data = await res.json().catch(() => ({ error: 'Request failed' }));
        setError(data.error || `Failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error');
    } finally {
      setBusy('');
    }
  }

  async function handleRun() {
    await postAction('run');
  }

  async function handleToggle() {
    await postAction('toggle');
  }

  async function handleDelete() {
    if (!confirm(`Delete indicator "${indicatorName}"?`)) return;
    await postAction('delete');
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={handleRun}
        disabled={busy !== ''}
        className="px-3 py-1.5 rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
      >
        {busy === 'run' ? 'Running…' : 'Run indicator'}
      </button>
      <button
        onClick={handleToggle}
        disabled={busy !== ''}
        className="px-3 py-1.5 rounded text-xs font-medium bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
      >
        {busy === 'toggle' ? '…' : enabled ? 'Disable' : 'Enable'}
      </button>
      <Link
        href={`/process/indicators/${encodeURIComponent(indicatorName)}/edit`}
        className="px-3 py-1.5 rounded text-xs font-medium bg-gray-100 hover:bg-gray-200"
      >
        Edit
      </Link>
      <button
        onClick={handleDelete}
        disabled={busy !== ''}
        className="px-3 py-1.5 rounded text-xs font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
      >
        {busy === 'delete' ? 'Deleting…' : 'Delete'}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}
